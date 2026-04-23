import asyncio
import json
import re as _re
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from starlette.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oxygent import MAS, Config, oxy

from app.profile import _update_user_profile_async
from app.cold_start import (
    COLD_START_ROUNDS,
    MAX_COLD_START_ROUNDS,
    _check_cold_start_complete,
    _build_initial_vector,
    _save_cold_start_result,
)
from app.confidence import compute_confidence, should_stop, MAX_QUESTIONS
from app.config import settings
from core.database import init_db, shutdown_db, get_db
from models.session import SessionEvent, UserProfile
from agents.generator_agent import build_generator_agent
from agents.item_qa_agent import build_item_qa_agent
from agents.user_observer_agent import build_user_observer_agent
from agents.grading_agent import build_grading_agent
from agents.memory_mgmt_agent import build_memory_mgmt_agent
from agents.master_agent import build_master_agent
from agents.thinking_coordinator import build_thinking_coordinator

_mas_instance = None


def get_mas_instance():
    return _mas_instance


_session_states: dict[str, dict] = {}


def _get_session_state(session_id: str) -> dict:
    if session_id not in _session_states:
        _session_states[session_id] = {
            "round": 0,
            "current_question": None,
            "current_item_id": None,
            "qa_retries": 0,
            "history": [],
            "thinking_steps": [],
            "answers": [],
            "stop_decision": None,
            "user_id": None,
            "cold_start": {
                "active": False,
                "round": 0,
                "collected": set(),
                "explicit_data": {},
                "answers": [],
                "initial_vector": None,
            },
        }
    return _session_states[session_id]


session_router = APIRouter(prefix="/api/v1")


@session_router.post("/sessions")
async def create_session(
    user_id: str,
    session: AsyncSession = Depends(get_db),
):
    profile = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = profile.scalars().first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        session.add(profile)
        await session.flush()

    sid = str(_uuid.uuid4())
    await session.commit()
    # Store user_id in session state for async profile updates
    state = _get_session_state(sid)
    state["user_id"] = user_id

    # Check if cold start is needed
    needs_cold_start = (
        not profile.skill_levels
        or not any(profile.skill_levels.values())
    )
    if needs_cold_start:
        state["cold_start"]["active"] = True
        state["cold_start"]["round"] = 0
        state["cold_start"]["collected"] = set()
        state["cold_start"]["explicit_data"] = {}
        state["cold_start"]["answers"] = []
        state["cold_start"]["initial_vector"] = None

    return {
        "session_id": sid,
        "user_id": user_id,
        "hsk_level": profile.hsk_level,
        "needs_cold_start": needs_cold_start,
    }


@session_router.get("/sessions/{session_id}/thinking")
async def get_thinking(session_id: str):
    """Get the thinking steps collected for the last action."""
    mas = get_mas_instance()
    if mas is None:
        raise HTTPException(status_code=503, detail="MAS not initialized")

    state = _get_session_state(session_id)
    question = state.get("current_question", {})
    if not question:
        return {"steps": []}

    qtype = question.get("question_type", "")
    # Determine which agents to run in parallel
    if state.get("last_action") == "answer":
        # After answering: grading + observer (memory_mgmt removed — runs only at end_session)
        agent_names = ["grading_agent", "user_observer_agent"]
        query = (
            f"用户作答：{state.get('last_answer', '')}\n"
            f"题目：{question.get('question_text', '')}\n"
            f"题型：{qtype}\n"
            f"请从语法、词汇、语用角度评估。"
        )
    else:
        # After question generation: generator + QA
        agent_names = ["generator_agent", "item_qa_agent"]
        query = (
            f"题目类型：{qtype}\n"
            f"题目内容：{question.get('question_text', '')}\n"
            f"请对出题过程和质检结果进行总结。"
        )

    # Run agents in parallel using asyncio.gather (same fan-out as ParallelAgent, but preserves individual outputs)
    results = await asyncio.gather(*[
        mas.call(name, {"query": query})
        for name in agent_names
    ], return_exceptions=True)

    agent_labels = {
        "generator_agent": "出题智能体",
        "item_qa_agent": "质检智能体",
        "user_observer_agent": "行为观察智能体",
        "grading_agent": "评分智能体",
        "memory_mgmt_agent": "记忆管理智能体",
    }

    steps = []
    for name, result in zip(agent_names, results):
        output = str(result) if not isinstance(result, Exception) else f"调用失败: {result}"
        steps.append({
            "agent": agent_labels.get(name, name),
            "agent_key": name,
            "output": output,
        })

    state["thinking_steps"] = steps
    return {"steps": steps}


@session_router.get("/sessions/{session_id}/cold_start")
async def cold_start(session_id: str):
    """SSE endpoint for cold start rounds with thinking steps."""
    mas = get_mas_instance()
    if mas is None:
        raise HTTPException(status_code=503, detail="MAS not initialized")

    state = _get_session_state(session_id)
    cs = state.get("cold_start", {})
    if not cs.get("active"):
        raise HTTPException(status_code=400, detail="Cold start not needed or already complete")

    cs["round"] += 1
    round_idx = cs["round"] - 1

    if round_idx >= len(COLD_START_ROUNDS):
        # Cold start complete — finalize (return as SSE event)
        async def event_generator_done():
            try:
                yield ": \n\n"
                initial_vector = _build_initial_vector(cs)
                cs["initial_vector"] = initial_vector

                # Save to user profile asynchronously
                user_id = state.get("user_id")
                if user_id:
                    from core.database import get_session_factory
                    factory = get_session_factory()
                    async def _save():
                        async with factory() as db_session:
                            await _save_cold_start_result(user_id, initial_vector, db_session)
                    asyncio.create_task(_save())

                cs["active"] = False
                yield f"event: question\ndata: {json.dumps({'cold_start_complete': True, 'initial_vector': initial_vector})}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            event_generator_done(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    round_data = COLD_START_ROUNDS[round_idx]

    async def event_generator():
        try:
            yield ": \n\n"

            # Build context from previous rounds
            prev_answers = cs.get("answers", [])
            context = ""
            if prev_answers:
                context = "用户在之前轮次的回答：\n"
                for a in prev_answers:
                    context += f"- 第{a['round']}轮（{a.get('label', '')}）：{a['answer'][:200]}\n"

            if round_idx == 0:
                # Round 1: use pre-defined prompt, no LLM needed
                gen_output = round_data["prompt"]
                thinking_label = "开始冷启动流程，收集用户背景信息。"
                state["thinking_steps"] = [
                    {"agent": "Master Agent", "agent_key": "master_agent", "output": thinking_label},
                ]
            else:
                # Round 2+: generate open-ended conversational question based on context (1 LLM call)
                gen_prompt = (
                    f"你是中文水平评测系统，现在是冷启动第{cs['round']}轮，目标：{round_data['label']}。\n"
                    f"{context}\n"
                    f"请根据以上用户信息，生成一个与此相关的开放式中文问答题。\n"
                    f"重要规则：\n"
                    f"1. 必须100%使用中文书写，绝不允许出现任何英文单词、字母或其他非中文字符。\n"
                    f"2. 必须是一个开放式问题（不是选择题、不是判断题、不是填空题），引导用户用自己的话回答。\n"
                    f"3. 使用自然的中文口语化表达，像老师跟学生聊天一样。\n"
                    f"4. 问题必须与用户之前提到的学习目的或背景相关。\n"
                    f"5. 在问题最后加上一句鼓励用户作答的话，比如'请简单说说你的想法'。\n"
                    f"6. 只输出问题本身，不要任何其他说明。"
                )
                try:
                    gen_output = await mas.call("generator_agent", {"query": gen_prompt})
                except Exception:
                    # Fallback to master agent if generator fails
                    gen_output = round_data["prompt"]

                # Quick thinking summary (just a one-liner)
                thinking_label = f"基于用户背景信息（{context[:100]}），生成本轮评测问题。"
                state["thinking_steps"] = [
                    {"agent": "出题智能体", "agent_key": "generator_agent", "output": thinking_label},
                ]

            # Stream thinking
            yield f"event: thinking\ndata: {json.dumps({'agent': 'master_agent', 'label': 'Master Agent', 'output': thinking_label})}\n\n: \n\n"

            q_data = json.dumps({
                "cold_start": True,
                "round": cs["round"],
                "label": round_data["label"],
                "question": gen_output,
            })
            yield f"event: question\ndata: {q_data}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@session_router.post("/sessions/{session_id}/cold_start_answer")
async def cold_start_answer(session_id: str, request: Request):
    """Handle user answer during cold start. Records response_time and extracts implicit data."""
    mas = get_mas_instance()
    if mas is None:
        raise HTTPException(status_code=503, detail="MAS not initialized")

    body = await request.json()
    answer = body.get("answer", "")
    response_time = body.get("response_time", 0)  # milliseconds from frontend

    state = _get_session_state(session_id)
    cs = state.get("cold_start", {})
    round_idx = cs.get("round", 1) - 1
    round_data = COLD_START_ROUNDS[round_idx] if round_idx < len(COLD_START_ROUNDS) else None

    # Record answer
    answer_record = {
        "round": cs.get("round", 1),
        "answer": answer,
        "answer_length": len(answer),
        "response_time": response_time / 1000 if response_time else 0,
        "label": round_data["label"] if round_data else "unknown",
    }
    cs["answers"].append(answer_record)
    state["answers"].append({"is_correct": True, "score": None, "item_id": cs.get("round", 1)})

    # Extract explicit data from round 1
    if cs.get("round") == 1 and len(answer) > 5:
        # Store raw answer for later LLM extraction
        cs["explicit_data"]["raw_answer_1"] = answer

    # Run thinking steps: User Observer + grading analysis (2 LLM calls via direct mas.call)
    async def event_generator():
        try:
            yield ": \n\n"

            # Phase 1: User Observer analyzes user answer (direct call bypasses Master Agent ES crash)
            observer_prompt = (
                f"冷启动评测第{cs.get('round', 1)}轮，用户作答：\n{answer}\n\n"
                f"请一句话分析：句式复杂度、词汇水平、母语痕迹、反应时间。"
            )
            try:
                observer_output = await mas.call("user_observer_agent", {"query": observer_prompt})
            except Exception:
                observer_output = "用户作答已记录，待后续进一步观察。"

            # Stream thinking 1
            yield f"event: thinking\ndata: {json.dumps({'agent': 'user_observer_agent', 'label': '行为观察智能体', 'output': observer_output})}\n\n: \n\n"

            # Phase 2: Grading Agent evaluates (direct call)
            grade_prompt = (
                f"评估冷启动第{cs.get('round', 1)}轮用户作答：\n{answer}\n\n"
                f"用一句话给出水平评估。"
            )
            try:
                grade_output = await mas.call("grading_agent", {"query": grade_prompt})
            except Exception:
                grade_output = "用户作答已记录，待后续进一步评估。"

            # Stream thinking 2
            yield f"event: thinking\ndata: {json.dumps({'agent': 'grading_agent', 'label': '评分智能体', 'output': grade_output})}\n\n: \n\n"

            state["thinking_steps"] = [
                {"agent": "行为观察智能体", "agent_key": "user_observer_agent", "output": observer_output},
                {"agent": "评分智能体", "agent_key": "grading_agent", "output": grade_output},
            ]

            # Check if cold start is complete
            is_complete = _check_cold_start_complete(cs)
            result_data = {
                "cold_start_complete": is_complete,
                "feedback": f"第{cs.get('round', 1)}轮作答已记录。",
                "observer_output": observer_output,
                "grade_output": grade_output,
            }
            if is_complete:
                initial_vector = _build_initial_vector(cs)
                cs["initial_vector"] = initial_vector
                result_data["initial_vector"] = initial_vector

                # Save profile async
                user_id = state.get("user_id")
                if user_id:
                    from core.database import get_session_factory
                    factory = get_session_factory()
                    async def _save():
                        async with factory() as db_session:
                            await _save_cold_start_result(user_id, initial_vector, db_session)
                    asyncio.create_task(_save())

                cs["active"] = False
                result_data["message"] = "冷启动评测完成，即将进入正式评测。"

            yield f"event: answer\ndata: {json.dumps(result_data)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@session_router.get("/sessions/{session_id}/question")
async def get_question(session_id: str):
    """SSE endpoint: streams thinking steps as agents complete, then sends the question."""
    mas = get_mas_instance()
    if mas is None:
        raise HTTPException(status_code=503, detail="MAS not initialized")

    state = _get_session_state(session_id)
    state["round"] += 1
    state["qa_retries"] = 0
    state["last_action"] = "question"
    state["thinking_steps"] = []
    item_id = state["round"]

    question_types = ["multiple_choice", "true_false", "fill_in_blank"]
    if state["history"]:
        last_type = state["history"][-1].get("question_type", "")
        others = [t for t in question_types if t != last_type]
        qtype = others[item_id % len(others)]
    else:
        qtype = question_types[item_id % len(question_types)]

    scenes = ["电力设备巡检", "工作场景", "学校生活", "日常生活", "医院就诊", "购物消费"]
    scene = scenes[item_id % len(scenes)]
    grammar_points = ["把字句", "被字句", "比较句", "条件句", "因果复句", "时间顺序"]
    grammar = grammar_points[item_id % len(grammar_points)]
    levels = ["HSK 3", "HSK 4", "HSK 5"]
    level = levels[(item_id - 1) % len(levels)]

    prompt = (
        f"生成一道{qtype}类型的中文评测题目，场景为{scene}，考察语法点为{grammar}，难度{level}。\n\n"
        "严格规则：所有题目内容（题干、选项、填空文本等）必须100%使用中文汉字书写。\n"
        "绝不允许出现任何英文单词、字母或其他非中文字符（除标点符号外）。\n"
        "只输出JSON，不要任何其他文字。格式如下：\n"
    )

    if qtype == "multiple_choice":
        prompt += (
            '{"question_type":"multiple_choice","scene":"...","grammar_focus":"...","target_level":"...",'
            '"question_text":"完整的中文题干（不能含英文字母）",'
            '"options":[{"index":"A","text":"中文选项A"},{"index":"B","text":"中文选项B"},'
            '{"index":"C","text":"中文选项C"},{"index":"D","text":"中文选项D"}],'
            '"correct_answer":"A","expected_duration_seconds":60}\n\n'
            "注意：correct_answer 必须是一个大写字母（A/B/C/D），对应正确选项的 index。\n"
            "选项内容必须是完整的中文句子，绝不能包含任何英文单词或字母。"
        )
    elif qtype == "true_false":
        prompt += (
            '{"question_type":"true_false","scene":"...","grammar_focus":"...","target_level":"...",'
            '"question_text":"陈述句","correct_answer":true,'
            '"expected_duration_seconds":30}'
        )
    else:
        prompt += (
            '{"question_type":"fill_in_blank","scene":"...","grammar_focus":"...","target_level":"...",'
            '"question_text":"包含______标记的完整中文题干","blank_count":1,'
            '"expected_duration_seconds":90}\n\n'
            "注意：question_text 必须是一句完整的中文句子，用______标记需要填空的位置。"
        )

    async def event_generator():
        """Raw SSE with explicit flushing. Summaries run in parallel with next step's LLM call."""
        try:
            yield ": \n\n"  # flush marker

            # Phase 1: Master Agent planning (may fail internally if ES is not configured)
            master_summary = "出题决策已生成"
            try:
                master_prompt = (
                    f"请作为评测系统的出题决策者，根据以下参数规划题目：\n"
                    f"题型：{qtype} | 场景：{scene} | 语法：{grammar} | 难度：{level}\n"
                    f"请简短说明出题意图（一句话）。"
                )
                master_resp = await mas.chat_with_agent(payload={"query": master_prompt})
                master_output = master_resp.output if hasattr(master_resp, "output") else str(master_resp)
                # Check for internal errors returned as output text
                if "TypeError" in str(master_output) or "NoneType" in str(master_output) or not str(master_output).strip():
                    master_summary_task = asyncio.sleep(0, result="出题决策已生成（跳过ES历史查询）")
                else:
                    master_summary_task = asyncio.create_task(_summarize_thinking(master_output, mas))
            except Exception:
                master_summary_task = asyncio.sleep(0, result="出题决策已生成（跳过ES历史查询）")

            # Phase 2: Generator (retry until valid JSON with question_type)
            output = ""
            gen_prompt = prompt
            for attempt in range(3):
                response = await mas.chat_with_agent(payload={"query": gen_prompt})
                output = response.output if hasattr(response, "output") else str(response)
                if _extract_json(output):
                    break  # Valid JSON found
                # Not JSON, retry with stronger instruction
                gen_prompt = gen_prompt + "\n\n注意：你之前的回复不是JSON格式。请严格按JSON格式输出题目，不要任何额外文字。"

            # Kick off summary in background (runs parallel to Phase 3)
            gen_summary_task = asyncio.create_task(_summarize_thinking(output, mas))

            # Wait for master summary (may have already finished)
            master_summary = await master_summary_task
            yield f"event: thinking\ndata: {json.dumps({'agent': 'master_agent', 'label': 'Master Agent', 'output': master_summary})}\n\n: \n\n"

            # Phase 3: QA check (runs parallel to generator summary)
            qa_prompt = f"请对以下中文评测题目进行质检（一句话总结是否通过及原因）：\n{output}"
            qa_resp = await mas.chat_with_agent(payload={"query": qa_prompt})
            qa_output = qa_resp.output if hasattr(qa_resp, "output") else str(qa_resp)
            qa_summary_task = asyncio.create_task(_summarize_thinking(qa_output, mas))

            # Wait for generator summary
            gen_summary = await gen_summary_task
            yield f"event: thinking\ndata: {json.dumps({'agent': 'generator_agent', 'label': '出题智能体', 'output': gen_summary})}\n\n: \n\n"

            # Phase 4: Comprehensive analysis (runs parallel to QA summary)
            try:
                coord_resp = await mas.chat_with_agent(payload={
                    "query": (
                        f"题目：{output}\n"
                        f"请从用户行为观察、评分、记忆管理三个维度各用一句话评估这道题。"
                    )
                })
                coord_output = coord_resp.output if hasattr(coord_resp, "output") else str(coord_resp)
                coord_summary_task = asyncio.create_task(_summarize_thinking(coord_output, mas))
            except Exception:
                coord_summary_task = asyncio.sleep(0, result=None)

            # Wait for QA summary
            qa_summary = await qa_summary_task
            yield f"event: thinking\ndata: {json.dumps({'agent': 'item_qa_agent', 'label': '质检智能体', 'output': qa_summary})}\n\n: \n\n"

            # Wait for coordinator summary
            coord_summary = await coord_summary_task
            if coord_summary:
                yield f"event: thinking\ndata: {json.dumps({'agent': 'thinking_coordinator', 'label': '综合分析', 'output': coord_summary})}\n\n: \n\n"

            # Collect all thinking steps for session state
            state["thinking_steps"] = [
                {"agent": "Master Agent", "agent_key": "master_agent", "output": master_summary},
                {"agent": "出题智能体", "agent_key": "generator_agent", "output": gen_summary},
                {"agent": "质检智能体", "agent_key": "item_qa_agent", "output": qa_summary},
            ]
            if coord_summary:
                state["thinking_steps"].append({"agent": "综合分析", "agent_key": "thinking_coordinator", "output": coord_summary})

            # Send final question
            item_data = _extract_json(output)
            if item_data and item_data.get("question_type"):
                if "options" in item_data and isinstance(item_data["options"], list):
                    item_data["options"] = [
                        {"index": opt.get("index", chr(65 + i)), "text": opt.get("text", str(opt))}
                        for i, opt in enumerate(item_data["options"])
                    ]

                # Knowledge fence check: validate vocabulary difficulty
                try:
                    from services.fence_service import check_question_vocabulary
                    target_level = int(item_data.get("target_level", "3").replace("HSK ", ""))
                    fence_result = await check_question_vocabulary(
                        item_data.get("question_text", ""),
                        user_hsk_level=target_level,
                    )
                    item_data["fence_check"] = fence_result
                except Exception:
                    pass  # Fence check is optional, don't fail the whole flow

                state["current_question"] = item_data
                state["current_item_id"] = item_id
                state["history"].append(item_data)

            q_data = json.dumps({
                "item_id": item_id,
                "question": item_data or {"question_type": "unknown", "question_text": output},
            })
            yield f"event: question\ndata: {q_data}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@session_router.post("/sessions/{session_id}/answer")
async def submit_answer(session_id: str, request: Request):
    """Submit user answer. Returns evaluation feedback."""
    mas = get_mas_instance()
    if mas is None:
        raise HTTPException(status_code=503, detail="MAS not initialized")

    body = await request.json()
    answer = body.get("answer", "")
    state = _get_session_state(session_id)
    question = state.get("current_question", {})
    item_id = state.get("current_item_id", 0)

    if not question:
        raise HTTPException(status_code=400, detail="No active question")

    state["last_action"] = "answer"
    state["last_answer"] = answer
    state["thinking_steps"] = []

    qtype = question.get("question_type", "unknown")
    qtext = question.get("question_text", "")

    if qtype in ("multiple_choice", "true_false"):
        if qtype == "multiple_choice":
            correct = question.get("correct_answer", "")
            is_correct = str(answer).strip().upper() == str(correct).strip().upper()
            feedback = "回答正确！" if is_correct else f"回答不正确。正确答案是 {correct}。"
        else:
            correct = question.get("correct_answer", False)
            user_bool = str(answer).strip() in ("正确", "True", "true", "对")
            is_correct = user_bool == correct
            feedback = "回答正确！" if is_correct else f"回答不正确。正确答案是{'正确' if correct else '错误'}。"

        # Record result
        state["answers"].append({"is_correct": is_correct, "score": None, "item_id": item_id})
        result = {"item_id": item_id, "is_correct": is_correct, "feedback": feedback}
    else:
        # For fill-in-blank and subjective answers, compute TTR and vocabulary profile
        try:
            from services.ttr_engine import compute_ttr, compute_vocabulary_profile
            ttr_result = compute_ttr(answer)
            vocab_profile = compute_vocabulary_profile(answer)
            ttr_info = {
                "ttr": ttr_result["ttr"],
                "type_count": ttr_result["type_count"],
                "token_count": ttr_result["token_count"],
                "weighted_level": vocab_profile["weighted_level"],
                "known_rate": vocab_profile["known_rate"],
            }
        except Exception:
            ttr_info = {"ttr": None, "message": "TTR 计算失败"}

        grade_prompt = (
            f"请评估以下中文作答。题目：{qtext}\n"
            f"用户作答：{answer}\n"
            f"词汇多样性 (TTR): {ttr_info.get('ttr', 'N/A')}\n"
            f"词汇等级: 加权 HSK {ttr_info.get('weighted_level', 'N/A')}\n\n"
            f"请从以下维度评分（0-100），返回JSON：\n"
            '{"score": 数字, "feedback": "具体评价", "is_correct": true/false}'
        )
        try:
            response = await mas.chat_with_agent(payload={"query": grade_prompt})
            output = response.output if hasattr(response, "output") else str(response)
            grade_data = _extract_json(output)
            score = grade_data.get("score", 50) if grade_data else 50
            is_correct = grade_data.get("is_correct", False) if grade_data else False
            feedback = grade_data.get("feedback", output) if grade_data else output

            # Record result
            state["answers"].append({"is_correct": is_correct, "score": score, "item_id": item_id})
            result = {"item_id": item_id, "score": score, "is_correct": is_correct, "feedback": feedback}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"评分失败: {e}")

    # Confidence check and adaptive stop
    stop_decision = should_stop(state["answers"])
    state["stop_decision"] = stop_decision
    if stop_decision:
        result["auto_stop"] = True
        result["stop_reason"] = stop_decision["reason"]
        result["confidence"] = stop_decision["confidence"]
        result["accuracy"] = stop_decision["accuracy"]
    else:
        # Always return current confidence stats
        stats = compute_confidence(state["answers"])
        result["confidence"] = stats["confidence"]
        result["accuracy"] = stats["accuracy"]

    # Trigger async profile update in background — ZERO latency impact
    user_id = state.get("user_id")
    if user_id:
        asyncio.create_task(_update_user_profile_async(user_id, state["history"], state["answers"]))

    return result


@session_router.get("/sessions/{session_id}/confidence")
async def get_confidence(session_id: str):
    """Get current confidence stats and stop decision."""
    state = _get_session_state(session_id)
    answers = state.get("answers", [])
    stats = compute_confidence(answers)
    stop = state.get("stop_decision")
    return {
        **stats,
        "should_stop": stop["should_stop"] if stop else False,
        "stop_reason": stop.get("reason", "") if stop else "",
        "remaining": MAX_QUESTIONS - len(answers),
    }


@session_router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str, session: AsyncSession = Depends(get_db)):
    """Get user's current skill level profile."""
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalars().first()
    if not profile:
        return {
            "user_id": user_id,
            "hsk_level": 1,
            "skill_levels": {"hsk": 0, "vocabulary": 0, "grammar": 0, "reading": 0},
        }
    return {
        "user_id": user_id,
        "hsk_level": profile.hsk_level or 1,
        "skill_levels": profile.skill_levels or {"hsk": 0, "vocabulary": 0, "grammar": 0, "reading": 0},
        "native_language": profile.native_language,
        "stubborn_errors": profile.stubborn_errors or [],
        "strengths": profile.strengths or [],
        "next_focus": profile.next_focus or [],
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


@session_router.post("/sessions/{session_id}/end")
async def end_session(session_id: str):
    """End the evaluation session: batch-update memory from all session data."""
    mas = get_mas_instance()
    if mas is None:
        raise HTTPException(status_code=503, detail="MAS not initialized")

    state = _get_session_state(session_id)
    history = state.get("history", [])
    total = len(history)

    # Batch memory update: run all memory agents once with full session context
    session_summary_text = " | ".join(
        f"第{i+1}题 [{q.get('question_type', '?')}] {q.get('question_text', '')[:50]}"
        for i, q in enumerate(history)
    )

    try:
        # Memory management: batch update mid-term and long-term memory
        mem_resp = await mas.chat_with_agent(payload={"query": (
            f"本次评测包含 {total} 道题目：{session_summary_text}\n"
            f"请总结本次评测的记忆更新内容，包括：\n"
            f"1. 中期情景记忆：精彩句子、顽固错误、兴趣领域\n"
            f"2. 长期能力画像：HSK等级是否需要调整、顽固语法点更新\n"
            f"3. 下一步建议\n"
            f"请简明扼要地总结（不超过300字）。"
        )})
        mem_output = mem_resp.output if hasattr(mem_resp, "output") else str(mem_resp)
    except Exception as e:
        mem_output = f"记忆更新失败: {e}"

    # Clean up session state
    if session_id in _session_states:
        del _session_states[session_id]

    return {
        "session_id": session_id,
        "summary": {
            "total_items": total,
            "memory_update": mem_output,
            "message": f"本次评测共 {total} 道题目，记忆已统一更新。",
        },
    }


@session_router.get("/sessions/{session_id}/events")
async def get_session_events(session_id: str, session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(SessionEvent)
        .where(SessionEvent.session_id == session_id)
        .order_by(SessionEvent.created_at)
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "item_id": e.item_id,
            "turn_id": e.turn_id,
            "event_type": e.event_type,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


# ---------- 知识围栏与 TTR 相关端点 ----------

@session_router.get("/vocabulary/level/{level}")
async def get_vocabulary_level(level: int):
    """获取指定 HSK 等级的词汇统计信息。"""
    from services.fence_service import get_vocabulary_for_level
    return await get_vocabulary_for_level(level)


@session_router.post("/vocabulary/check")
async def check_vocabulary(request: Request):
    """检查文本中的词汇是否在指定等级范围内。"""
    body = await request.json()
    text = body.get("text", "")
    max_level = body.get("max_level", 99)
    from services.fence_service import check_words_in_vocabulary
    return await check_words_in_vocabulary(text, max_level)


@session_router.post("/ttr/compute")
async def compute_ttr(request: Request):
    """计算文本的 TTR（词汇多样性）。"""
    body = await request.json()
    text = body.get("text", "")
    from services.ttr_engine import compute_ttr, compute_mtld, compute_vocabulary_profile

    result = compute_ttr(text)
    mtld = compute_mtld(text)
    profile = compute_vocabulary_profile(text)

    return {
        **result,
        "mtld": mtld["mtld"],
        "mtld_segments": mtld["segments"],
        "level_profile": profile["level_profile"],
        "known_rate": profile["known_rate"],
        "weighted_level": profile["weighted_level"],
    }


async def _summarize_thinking(raw_output: str, mas) -> str:
    """Use LLM to condense raw agent output into 1-2 sentences for user display."""
    try:
        summary_prompt = (
            f"请将以下内容浓缩为一两句简洁的中文总结，只保留核心结论，不要详细分析：\n\n{raw_output}"
        )
        resp = await mas.chat_with_agent(payload={"query": summary_prompt})
        output = resp.output if hasattr(resp, "output") else str(resp)
        return output.strip()[:200]
    except Exception:
        # Fallback: truncate
        return raw_output.strip()[:150]


def _contains_english(data: dict) -> bool:
    """Check if any text field in the question data contains English letters."""
    pattern = _re.compile(r'[A-Za-z]')
    for key in ("question_text",):
        val = data.get(key, "")
        if isinstance(val, str) and pattern.search(val):
            return True
    for opt in data.get("options", []):
        text = opt.get("text", "")
        if isinstance(text, str) and pattern.search(text):
            return True
    return False


def _extract_json(text: str) -> dict | None:
    """Extract first JSON object from text."""
    if not text:
        return None
    json_match = text.replace("```json", "").replace("```", "").strip()
    json_match = json_match[json_match.find("{"):] if "{" in json_match else ""
    if not json_match:
        return None
    depth = 0
    end = 0
    for i, c in enumerate(json_match):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    try:
        return json.loads(json_match[:end])
    except json.JSONDecodeError:
        return None


async def main() -> None:
    global _mas_instance

    Config.set_agent_llm_model("default_llm")

    # Configure Elasticsearch for oxygent MAS
    Config.set_es_config({
        "hosts": [f"{settings.es_host}:{settings.es_port}"],
        "user": "",
        "password": "",
    })

    oxy_space = [
        oxy.HttpLLM(
            name="default_llm",
            api_key=settings.default_llm_api_key,
            base_url=settings.default_llm_base_url,
            model_name=settings.default_llm_model_name,
        ),
        *build_generator_agent(),
        *build_item_qa_agent(),
        *build_user_observer_agent(),
        *build_grading_agent(),
        *build_memory_mgmt_agent(),
        *build_thinking_coordinator(),
        *build_master_agent(),
    ]

    await init_db()

    async with MAS(oxy_space=oxy_space) as mas:
        _mas_instance = mas
        try:
            await mas.start_web_service(
                first_query="你好，我是中文水平评测系统。我将根据你的水平进行能力评估，请认真作答。",
                routers=[session_router],
                host=settings.host,
                port=settings.port,
            )
        finally:
            await shutdown_db()


if __name__ == "__main__":
    asyncio.run(main())

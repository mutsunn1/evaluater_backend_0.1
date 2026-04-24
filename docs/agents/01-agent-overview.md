# 智能体总览

## 1. Agent 角色与职责

| Agent | 类型 | 核心职责 | 调用方式 |
|-------|------|---------|---------|
| Master Agent | ReActAgent (is_master) | 冷启动总控、出题决策、演化裁决 | `mas.chat_with_agent()` |
| Generator Agent | ChatAgent | 无状态语料生产，生成四类型题目 | `mas.call()` 直接调用 |
| Item QA Agent | ChatAgent | 题目质检：超纲/违禁词/语法考察点 | `mas.call()` 直接调用 |
| User Observer Agent | ChatAgent | 行为观察：答题时间分析、水平归因 | `mas.call()` 直接调用 |
| Grading Agent | ReActAgent | 四维度评分：字/词/句/语用 | `mas.call()` 直接调用 |
| Memory Mgmt Agent | ReActAgent | 中长期记忆 CRUD | 仅在 Session 结束时调用 |
| Thinking Coordinator | ParallelAgent | 并行执行所有子 Agent 并汇总 | 可选，用于批量分析 |

## 2. Agent 注册

所有 Agent 通过工厂函数注册到 `oxy_space`：

```python
# app/main.py
oxy_space = [
    oxy.HttpLLM(name="default_llm", ...),
    *build_generator_agent(),
    *build_item_qa_agent(),
    *build_user_observer_agent(),
    *build_grading_agent(),
    *build_memory_mgmt_agent(),
    *build_thinking_coordinator(),
    *build_master_agent(),
]

async with MAS(oxy_space=oxy_space) as mas:
    _mas_instance = mas
    await mas.start_web_service(routers=[session_router])
```

## 3. 通信模式

| 模式 | 方法 | 特点 | 使用场景 |
|------|------|------|---------|
| 直接调用 | `mas.call(name, args)` | 绕过 Master Agent，同步返回 | 出题、评分、观察 |
| 路由调用 | `mas.chat_with_agent(payload)` | 通过 Master Agent 路由 | 冷启动规划、Master 决策 |
| 并行调用 | `asyncio.gather(*[mas.call(...)])` | 并发执行多个 Agent | 冷启动答案评估 |

## 4. 短记忆配置

所有子 Agent 设置 `short_memory_size=0`，绕过 ES 历史查询，避免在 ES 未配置时崩溃。Master Agent 保留默认配置以支持路由逻辑。

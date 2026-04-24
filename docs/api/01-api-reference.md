# API 端点参考

## 1. Session 管理

### POST `/api/v1/sessions`
创建评测 Session
- **参数**: `user_id` (query)
- **返回**: `{session_id, user_id, hsk_level, needs_cold_start}`

### GET `/api/v1/sessions/{id}/cold_start`
SSE 冷启动问题推送
- **事件**: `thinking` → `question`
- **返回**: `{cold_start: true, round, label, question}` 或 `{cold_start_complete: true}`

### POST `/api/v1/sessions/{id}/cold_start_answer`
SSE 冷启动答案评估
- **请求**: `{answer: string, response_time: number}`
- **事件**: `thinking` × 2 → `answer`
- **返回**: `{cold_start_complete, feedback, observer_output, grade_output}`

### GET `/api/v1/sessions/{id}/question`
SSE 正式评测题目推送
- **事件**: `thinking` × 3-4 → `question`
- **返回**: `{item_id, question: {...}}`

### POST `/api/v1/sessions/{id}/answer`
提交答案
- **请求**: `{answer: string}`
- **返回**: `{item_id, is_correct, feedback, confidence, accuracy, auto_stop?, stop_reason?}`

### POST `/api/v1/sessions/{id}/end`
结束 Session
- **返回**: `{session_id, summary: {total_items, memory_update, message}}`

### GET `/api/v1/sessions/{id}/confidence`
获取置信度统计
- **返回**: `{accuracy, ci_lower, ci_upper, confidence, sample_size, should_stop, stop_reason, remaining}`

### GET `/api/v1/sessions/{id}/events`
获取 Session 事件流
- **返回**: `[{id, item_id, turn_id, event_type, payload, created_at}]`

## 2. 用户画像

### GET `/api/v1/users/{user_id}/profile`
获取用户能力画像
- **返回**: `{user_id, hsk_level, skill_levels, native_language, stubborn_errors, strengths, next_focus, updated_at}`

## 3. 知识围栏

### GET `/api/v1/vocabulary/level/{level}`
获取指定等级词汇统计
- **返回**: `{level, word_count, cumulative_count, sample_words[]}`

### POST `/api/v1/vocabulary/check`
检查文本词汇难度
- **请求**: `{text, max_level}`
- **返回**: `{violations[], known_words[], unknown_words[], vocab_coverage, max_level}`

## 4. TTR 计算

### POST `/api/v1/ttr/compute`
计算文本词汇多样性
- **请求**: `{text}`
- **返回**: `{ttr, type_count, token_count, mtld, mtld_segments, level_profile, known_rate, weighted_level}`

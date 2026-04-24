# 冷启动机制

## 1. 触发条件

`createSession` 端点检查 `user_profiles.skill_levels`：
- 为空或所有值为 0 → `needs_cold_start = true`
- 已有数据 → 跳过冷启动，进入正常评测

## 2. 回合定义

定义在 `app/cold_start.py` 的 `COLD_START_ROUNDS`：

| 轮次 | 标签 | 目标 |
|------|------|------|
| 1 | 背景了解 | 母语、学习时长、学习目标 |
| 2 | 场景表达 | 根据第1轮回答动态生成场景题 |
| 3 | 难度探测（基础） | 因果复句等基础语法 |
| 4 | 难度探测（进阶） | 逻辑连接词 + 紧急语境 |

最多 5 轮，最少 3 轮。

## 3. 动态生成

- **第1轮**：使用预定义 prompt（不走 LLM）
- **第2轮起**：调用 `mas.call("generator_agent", {...})` 动态生成
  - 传入前几轮用户回答作为上下文
  - 强制要求 100% 中文书写
  - 开放式问题，非选择题/判断题

## 4. 答案评估

每轮用户作答后：
1. 行为观察 Agent 分析句式、词汇、母语痕迹
2. 评分 Agent 评估水平
3. 记录答案到 `cs["answers"]`

## 5. 收敛条件

`_check_cold_start_complete()`:
- 最少 3 轮
- 已获得母语 + 学习目标（显性数据）
- 至少 2 轮有效答题记录（隐性数据）
- 或达到 5 轮上限

## 6. Initial_Vector

```json
{
  "language_family": "英语",
  "domain_knowledge": "HSK考试",
  "initial_difficulty": 3,
  "input_stability": "normal",
  "skill_levels": { "hsk": 50.0, "vocabulary": 40.0, "grammar": 37.5, "reading": 35.0 },
  "hsk_level": 3,
  "cold_start_complete": true
}
```

异步写入 `user_profiles` 表。

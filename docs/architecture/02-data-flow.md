# 数据流转

## 1. 冷启动流程

```
用户登录
  ↓
createSession → 检查 skill_levels 是否为空
  ↓ (needs_cold_start = true)
  ↓
第1轮: 背景了解 (预定义 prompt)
  → 收集母语、学习时长、学习目标
  ↓
第2轮: 场景表达 (动态生成)
  → 根据第1轮回答生成场景相关问题
  ↓
第3轮: 难度探测（基础）
  → 因果复句等语法探测
  ↓
第4轮: 难度探测（进阶）
  → 逻辑连接词 + 紧急语境探测
  ↓
每轮后检查收敛条件 (最少3轮，最多5轮)
  ↓
生成 Initial_Vector
  → 异步写入 user_profiles
  ↓
转入正式评测
```

## 2. 正式出题流程

```
前端请求 /sessions/{id}/question
  ↓
Master Agent 规划出题意图 (SSE: thinking)
  ↓ (并行运行思考摘要)
Generator Agent 生成题目 (SSE: thinking)
  ↓ (并行运行思考摘要)
Item QA 质检题目 (SSE: thinking)
  ↓ (并行运行思考摘要)
Thinking Coordinator 综合分析 (SSE: thinking)
  ↓
知识围栏检查 (check_question_vocabulary)
  → 词汇难度是否适合用户水平
  ↓
推送题目到前端 (SSE: question)
```

## 3. 答题与评分流程

```
用户提交答案
  ↓
选择题/判断题: 直接判分 (零延迟)
填空题: MAS 评分
  ↓
计算 TTR + 词汇等级分布
  → 作为 LLM 评分的输入参数
  ↓
行为观察 + 评分 Agent 分析 (SSE: thinking)
  ↓
返回评分结果 + 置信度统计
  ↓
异步更新用户画像 (后台任务，不阻塞响应)
  ↓
检查自适应停止条件
  → 达标 → 前端提示评测完成
  → 未达标 → 获取下一题
```

## 4. Session 结束流程

```
用户点击"结束评测" 或 自适应停止触发
  ↓
汇总所有答题记录
  ↓
MAS 批量记忆更新
  → 中期情景记忆 (ES: mid_term_memory)
  → 长期能力画像 (PostgreSQL: user_profiles)
  ↓
返回评测总结
  ↓
清理 Session 状态
```

## 5. 数据存储

| 存储 | 索引/表 | 写入时机 | 内容 |
|------|---------|---------|------|
| PostgreSQL | session_events | 每轮实时 | 题目、作答、评分、分析 |
| PostgreSQL | user_profiles | 冷启动 + Session 结束 | HSK 等级、技能维度、顽固错误 |
| PostgreSQL | hsk_words | 一次性导入 | HSK 1-9 词库 (11,000 词) |
| Elasticsearch | app_prompt | 启动时 | Agent prompt 持久化 |
| Elasticsearch | app_trace | 每次 MAS 调用 | 调用追踪 |
| Elasticsearch | app_node | 每次 Agent 执行 | 节点日志 |
| Elasticsearch | mid_term_memory | Session 结束时 | 精彩句子、顽固错误、兴趣领域 |
| Redis | (内部使用) | SSE 消息缓冲 | 流式消息队列 |

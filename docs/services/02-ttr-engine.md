# TTR 词汇多样性引擎

## 1. 概述

基于 HSK 词库的 TTR（Type-Token Ratio）计算服务，用于评估用户作答的词汇多样性。

## 2. 核心算法

### 2.1 分词
基于 HSK 词库的最长匹配正向分词：
- 从左到右扫描文本
- 优先匹配最长词（最多 6 字）
- 未匹配的单字单独成词

### 2.2 标准 TTR
```
TTR = 不同词数 / 总词数
```
- 值越接近 1：词汇越丰富
- 值越接近 0：重复越多

### 2.3 MTLD (Moving Average TLR)
比标准 TTR 更稳定，不受文本长度影响：
- 从左到右累加 token
- 每当 TTR 降至 0.72 以下时开始新的 segment
- 最终取 segments 的平均值

### 2.4 词汇等级分布
- 统计各 HSK 等级词汇的数量占比
- 计算加权难度等级
- 评估文本难度级别

## 3. API 端点

### POST `/api/v1/ttr/compute`
```json
// 请求
{"text": "因为机器坏了，所以我们不能工作了。"}

// 返回
{
  "ttr": 0.8182,
  "type_count": 18,
  "token_count": 22,
  "mtld": 1.54,
  "mtld_segments": 1,
  "level_profile": {...},
  "known_rate": 100.0,
  "weighted_level": 1.8
}
```

## 4. 集成点

在 `submit_answer` 端点中，对主观题作答自动计算：
- TTR 值
- 词汇等级分布
- 加权难度
- 已知率

这些数据作为 LLM 评分的输入参数，帮助更准确地评估用户水平。

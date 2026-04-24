# 知识围栏服务

## 1. 概述

基于 HSK 词库（11,000 词）的词汇过滤系统，防止 Agent 在出题时使用超纲词汇。

## 2. 核心功能

### 2.1 词汇检查
```python
await check_words_in_vocabulary(text, max_level=3)
```
- 基于最长匹配正向分词
- 返回已知词、未知词、覆盖率

### 2.2 题目词汇验证
```python
await check_question_vocabulary(question_text, user_hsk_level=3)
```
- 允许高 2 级以内的词汇（合理挑战）
- 超过 2 个超纲词则不通过

### 2.3 等级词汇统计
```python
await get_vocabulary_for_level(level=3)
```
- 返回指定等级及以下的词汇总数和示例

## 3. 缓存策略

使用 `@lru_cache` 缓存词库查询结果，避免重复数据库查询：
- `_get_all_words(level)`: 指定等级及以下的所有词
- `_get_word_set(level)`: 同上，返回 set
- `_get_level_word_set(level)`: 精确等级的词

## 4. API 端点

| 端点 | 说明 |
|------|------|
| `GET /vocabulary/level/{level}` | 获取等级词汇统计 |
| `POST /vocabulary/check` | 检查文本词汇难度 |

## 5. 集成点

- `get_question` 端点在出题后自动调用 `check_question_vocabulary`
- 结果附加到 `item_data["fence_check"]`
- 不阻塞出题流程，仅作为额外信息

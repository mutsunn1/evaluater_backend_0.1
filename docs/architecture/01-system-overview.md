# 系统架构总览

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                              │
│  UserProfileSidebar │ ChatView │ QuestionRenderer │ Thinking    │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI (oxygent 内置)                         │
│                                                                 │
│  ┌───────────────────┐  ┌───────────────────────────────────┐  │
│  │  oxygent 内置路由   │  │         自定义 API 路由            │  │
│  │ /chat, /health,   │  │ /api/v1/sessions/*                │  │
│  │ /sse/chat, /call  │  │ /api/v1/users/*/profile           │  │
│  │ /feedback         │  │ /api/v1/vocabulary/*              │  │
│  │ /rating           │  │ /api/v1/ttr/*                     │  │
│  └───────────────────┘  └───────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    MAS 多智能体系统                          │  │
│  │                                                           │  │
│  │              Master Agent (总控)                           │  │
│  │          ┌──────┬──────┬──────┬──────┬──────┐             │  │
│  │          ▼      ▼      ▼      ▼      ▼      ▼             │  │
│  │     Generator ItemQA Observer Grading Memory Thinking     │  │
│  │       出题    质检   观察    评分   记忆   协调            │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
             ┌───────────────┼───────────────┐
             ▼               ▼               ▼
      PostgreSQL        Elasticsearch      Redis
      session_events    prompt 存储        SSE 消息队列
      user_profiles     trace 追踪         多实例同步
      hsk_words         中期记忆
```

## 2. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| MAS 框架 | oxygent 1.0.13 | 多智能体编排、Agent 生命周期管理 |
| Web 框架 | FastAPI (oxygent 内置) | REST API + SSE 流式推送 |
| 数据库 | PostgreSQL 18 + asyncpg | 主存储：事件流、用户画像、词库 |
| 搜索引擎 | Elasticsearch 8.15 | Agent prompt 持久化、中期记忆 |
| 缓存/队列 | Redis 7 | SSE 消息缓冲、多实例同步 |
| ORM | SQLAlchemy 2.0 (异步) | PostgreSQL 异步数据访问 |
| 词汇服务 | 自建 HSK 词库 (11,000 词) | 知识围栏 + TTR 计算 |

## 3. 核心设计原则

### 3.1 异步并行
- 所有 LLM 调用通过 `asyncio.create_task()` 并行化
- 思考摘要与下一阶段的 Agent 执行并行运行
- 用户画像更新通过后台异步任务完成，零延迟影响

### 3.2 SSE 流式推送
- 所有 Agent 输出通过 `StreamingResponse` 以 SSE 格式推送
- 前端实时渲染 thinking 气泡，感知延迟显著降低
- flush marker (`: \n\n`) 确保代理不缓冲输出

### 3.3 知识围栏
- 基于 11,000 词 HSK 词库的最长匹配正向分词
- 出题时自动检查词汇难度（允许高 2 级以内）
- TTR 词汇多样性分析集成到主观题评分

## 4. 目录结构

```
evaluater_backend_0.1/
├── app/                    # 应用层
│   ├── main.py             # 入口：MAS 初始化 + 路由注册
│   ├── config.py           # pydantic-settings 配置
│   ├── cold_start.py       # 冷启动回合定义 + Initial_Vector
│   ├── confidence.py       # Wilson 置信区间 + 自适应停止
│   └── profile.py          # 用户画像异步更新
├── agents/                 # 智能体工厂
│   ├── generator_agent.py  # 出题智能体 (ChatAgent)
│   ├── item_qa_agent.py    # 质检智能体 (ChatAgent)
│   ├── user_observer_agent.py # 行为观察 (ChatAgent)
│   ├── grading_agent.py    # 评分智能体 (ReActAgent)
│   ├── memory_mgmt_agent.py# 记忆管理 (ReActAgent)
│   ├── master_agent.py     # Master 总控 (ReActAgent)
│   └── thinking_coordinator.py # 思考协调器 (ParallelAgent)
├── models/                 # 数据模型
│   ├── session.py          # SessionEvent, UserProfile
│   └── vocabulary.py       # HSKWord (词表)
├── core/                   # 基础设施
│   └── database.py         # 异步 SQLAlchemy (惰性初始化)
├── services/               # 业务服务
│   ├── fence_service.py    # 知识围栏 (词汇检查)
│   └── ttr_engine.py       # TTR 计算 (词汇多样性)
├── hsk_vocabulary/         # HSK 词库 (11,000 词)
├── docs/                   # 开发文档 (本文件夹)
├── tests/                  # 测试
├── docker-compose.yml      # ES + Redis 部署
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
└── research.md             # 技术研究报告
```

# Evaluater Backend 0.1 — 中文水平评测多智能体系统

基于 [oxygent](https://github.com/jd-opensource/oxygent) MAS 框架的中文水平评测后端，服务于"感知-决策-执行-质检"闭环的辅助学习系统。

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Master Agent (导演)                        │
│   上下文聚合 → 路径规划 → 参数化指令 → 演化裁决 → 冷启动总控         │
└───────┬──────────┬──────────┬───────────┬──────────┬────────────┘
        │          │          │           │          │
        ▼          ▼          ▼           ▼          ▼
  ┌──────────┐ ┌──────┐ ┌────────┐  ┌────────┐  ┌──────────────┐
  │Generator │ │ItemQA│ │Observer│  │Grading │  │ Memory Mgmt  │
  │出题智能体 │ │质检  │ │行为观察│  │评分    │  │ 记忆管理     │
  └──────────┘ └──────┘ └────────┘  └────────┘  └──────────────┘
```

### 工作流程

1. **冷启动阶段**（新用户首次登录）
   - 第1轮：收集显性信息（母语、学习时长、学习目标）
   - 第2~5轮：根据用户背景动态生成场景题，探测语言水平
   - 完成后生成 Initial_Vector 写入用户画像

2. **正式评测阶段**
   - 出题 → 用户作答 → 评分 → 记忆更新 → 循环
   - 每道题附带置信度评估，达到阈值自动结束

3. **Session 结束**
   - 批量更新中期情景记忆和长期能力画像

---

## 二、工程目录结构

```
evaluater_backend_0.1/
├── app/
│   ├── main.py              # 入口：MAS 初始化 + API 路由注册
│   ├── config.py             # pydantic-settings 配置加载
│   ├── cold_start.py         # 冷启动：回合定义 + Initial_Vector 构建
│   ├── confidence.py         # 置信度计算 + 自适应停止判断
│   └── profile.py            # 用户水平评估 + 异步后台更新
├── agents/
│   ├── generator_agent.py    # 出题智能体工厂（ReActAgent + 工具绑定）
│   ├── item_qa_agent.py      # 题目质检智能体
│   ├── user_observer_agent.py# 行为观察智能体
│   ├── grading_agent.py      # 评分智能体
│   ├── memory_mgmt_agent.py  # 记忆管理智能体
│   ├── master_agent.py       # Master 协调智能体
│   └── thinking_coordinator.py # 思考协调器（ParallelAgent 封装）
├── models/
│   └── session.py            # SessionEvent（JSONB 事件流）+ UserProfile 模型
├── core/
│   └── database.py           # 异步 SQLAlchemy 引擎/会话管理（惰性初始化）
├── services/
│   ├── fence_service.py      # 知识围栏 Mock（待接入真实词库）
│   └── ttr_engine.py         # TTR 词汇多样性计算 Mock
├── tests/                    # 单元测试 + 集成测试
├── requirements.txt
├── .env.example
└── README.md
```

---

## 三、模块详解

### 3.1 `app/main.py` — 入口与路由

**MAS 初始化流程**：
1. 配置 LLM 模型（`Config.set_agent_llm_model`）
2. 组装 `oxy_space`：HttpLLM + 6 个 Agent + Thinking Coordinator + Master
3. 调用 `init_db()` 建表（惰性同步引擎 → 异步引擎）
4. 进入 `MAS` 上下文管理器 → 启动 Web 服务

**API 端点**：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/sessions` | 创建评测 Session，返回 `needs_cold_start` 标记 |
| GET | `/api/v1/sessions/{id}/cold_start` | SSE 冷启动问题推送（流式 thinking） |
| POST | `/api/v1/sessions/{id}/cold_start_answer` | SSE 冷启动答案评估（流式 thinking） |
| GET | `/api/v1/sessions/{id}/question` | SSE 正式评测题目推送（流式 thinking） |
| POST | `/api/v1/sessions/{id}/answer` | 提交答案，返回评分 + 置信度 |
| GET | `/api/v1/sessions/{id}/confidence` | 获取当前置信度统计 |
| GET | `/api/v1/sessions/{id}/thinking` | 获取上次操作的思考步骤 |
| GET | `/api/v1/sessions/{id}/events` | 获取 Session 完整事件流 |
| GET | `/api/v1/users/{user_id}/profile` | 获取用户能力画像 |
| POST | `/api/v1/sessions/{id}/end` | 结束 Session，批量更新记忆 |

### 3.2 `app/cold_start.py` — 冷启动引擎

**冷启动回合定义**（`COLD_START_ROUNDS`）：

| 轮次 | 标签 | 目标 |
|------|------|------|
| 1 | 背景了解 | 收集母语、学习时长、学习目标 |
| 2 | 场景表达 | 根据用户背景生成场景题，探测表达能力 |
| 3 | 难度探测（基础） | 因果复句等基础语法探测 |
| 4 | 难度探测（进阶） | 逻辑连接词 + 紧急语境探测 |

**动态生成机制**：
- 第1轮：使用预定义 prompt
- 第2轮起：MAS 根据用户第1轮回答动态生成场景相关题目

**Initial_Vector 结构**：

```json
{
  "language_family": "日语",
  "domain_knowledge": "留学",
  "initial_difficulty": 3,
  "input_stability": "normal",
  "skill_levels": { "hsk": 50.0, "vocabulary": 40.0, "grammar": 37.5, "reading": 35.0 },
  "hsk_level": 3,
  "cold_start_complete": true
}
```

### 3.3 `app/confidence.py` — 置信度与自适应停止

**Wilson 分数区间**：基于二项分布计算 95% 置信区间

```
置信度 = 1 - (ci_upper - ci_lower)
```

**自适应停止规则**：

| 条件 | 阈值 | 说明 |
|------|------|------|
| 最小题数 | < 3 | 不检查 |
| 最大题数 | ≥ 12 | 强制停止 |
| 置信区间 | ≤ 85% | 区间足够窄时停止 |
| 连续正确 | 5 题全对 | 水平已确定 |
| 连续错误 | 5 题全错 | 可判定当前水平 |

### 3.4 `app/profile.py` — 用户画像异步更新

**零延迟设计**：`asyncio.create_task()` 后台运行，不阻塞 API 响应。

**4 维度水平计算**：
- **HSK 综合水平**：正确率 × 难度加权 → 映射 1-6 级
- **词汇水平**：基于答案长度和词汇多样性
- **语法水平**：基于语法焦点掌握情况
- **阅读水平**：基于复杂句理解能力

### 3.5 `core/database.py` — 数据库管理

**惰性初始化**：引擎在首次调用时才创建，避免导入时连接失败。

**双引擎设计**：
- `async_engine`（asyncpg）：运行时 CRUD 操作
- `sync_engine`（pg8000）：DDL 建表（`create_all` 不支持异步）

### 3.6 `models/session.py` — 数据模型

**SessionEvent**（事件流表）：
- 每条记录代表一个事件（出题、作答、评分、分析）
- `payload` 为 JSONB 格式，存储完整的结构化数据

**UserProfile**（用户画像表）：
- `skill_levels` JSONB：4 维度水平分数
- `stubborn_errors`：顽固语法点列表
- `strengths`：已掌握能力项
- `next_focus`：建议关注方向

### 3.7 智能体模块

| Agent | 类型 | 职责 |
|-------|------|------|
| `master_agent` | ReActAgent (is_master) | 冷启动总控 + 出题决策 + 演化裁决 |
| `generator_agent` | ReActAgent | 题目生成，绑定时间工具 |
| `item_qa_agent` | ChatAgent | 题目质检：超纲/违禁词/语法考察点 |
| `user_observer_agent` | ChatAgent | 行为观察：答题时间分析、水平归因 |
| `grading_agent` | ReActAgent | 四维度评分：字/词/句/语用 |
| `memory_mgmt_agent` | ReActAgent | 中长期记忆 CRUD：Probe/Review/Sync |
| `thinking_coordinator` | ParallelAgent | 并行执行所有子 Agent 并汇总 |

---

## 四、配置说明

### `.env` 环境变量

```env
# 数据库
DB_USER=postgres
DB_PASSWORD=你的密码
DB_HOST=localhost
DB_PORT=5432
DB_NAME=evaluator_db
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}

# LLM（阿里云 DashScope）
DEFAULT_LLM_API_KEY=sk-你的密钥
DEFAULT_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DEFAULT_LLM_MODEL_NAME=qwen-flash

# 服务器
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info

# Elasticsearch（中期记忆）
ES_HOST=localhost
ES_PORT=9200
ES_INDEX=mid_term_memory
```

---

## 五、快速开始

### 1. 环境准备

```bash
conda activate agent
pip install -r requirements.txt
```

### 2. 创建数据库

```powershell
# 方法 A：使用 psql（需要 PostgreSQL 命令行工具）
& "D:\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE evaluator_db;"

# 方法 B：使用 Python 脚本
conda run -n agent python create_db.py
```

### 3. 配置环境

```bash
cp .env.example .env
# 编辑 .env 填入数据库密码和 LLM 密钥
```

### 4. 启动

```bash
cd evaluater_backend_0.1
conda activate agent
python -m app.main
```

服务启动在 `http://0.0.0.0:8000`

---

## 六、数据流转

### 冷启动流程

```
用户登录 → 检测 skill_levels 为空 → needs_cold_start = true
  → 前端进入冷启动模式
  → 第1轮：背景收集（预定义 prompt）
  → 第2轮：MAS 根据第1轮回答动态生成场景题
  → 第3-4轮：难度梯度探测
  → 每轮：Master Agent 规划 → 出题 Agent 生成 → 用户作答 → 行为观察 + 评分
  → 达到收敛条件 → 生成 Initial_Vector → 写入 user_profiles
  → 自动转入正式评测
```

### 正式评测流程

```
获取题目（SSE 流式 thinking）
  → Master Agent 规划出题意图（思考中...）
  → 出题 Agent 生成题目（思考中...）
  → 质检 Agent 验证题目（思考中...）
  → 综合分析汇总（思考中...）
  → 推送题目到前端
  ↓
用户作答
  → 选择题/判断题：直接判分（零延迟）
  → 填空题：MAS 评分
  → 行为观察 + 评分 Agent 并行分析（流式 thinking）
  → 异步更新用户画像（零延迟影响）
  → 检查置信度 → 达标则自动停止
  ↓
Session 结束
  → 批量记忆更新（中期 + 长期）
```

---

## 七、扩展指南

### 新增题目类型

1. 在 `app/main.py` 的 `question_types` 列表中添加新类型
2. 在 prompt 中添加新类型的 JSON 格式定义
3. 在 `models/session.py` 的 `ItemData` 类型中添加对应字段
4. 在前端 `QuestionRenderer.vue` 中添加对应的渲染组件

### 新增智能体

1. 在 `agents/` 创建 `build_*_agent()` 工厂函数
2. 在 `app/main.py` 的 `oxy_space` 中注册
3. 在 `master_agent.py` 的 `sub_agents` 列表中添加

### 接入真实词库

替换 `services/fence_service.py` 中的 Mock 实现为真实词库加载和过滤逻辑。

### 接入 TTR 检测

替换 `services/ttr_engine.py` 中的 Mock 实现为 TTR 计算模块，接入外部词汇检测 API。

---

## 八、数据库迁移

```bash
alembic init alembic
# 配置 alembic.ini 的 DATABASE_URL
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

---

## 九、测试

```bash
cd evaluater_backend_0.1
pytest tests/ -v --ignore=tests/test_e2e_session.py  # 单元+集成测试
python -m tests.test_e2e_session                     # E2E 测试（需服务运行中）
```

---

## 十、技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 框架 | FastAPI | oxygent 内置 |
| MAS 框架 | oxygent | 1.0.13 |
| 数据库 | PostgreSQL | 18+ |
| ORM | SQLAlchemy (异步) | 2.0+ |
| 数据库驱动 | asyncpg (异步) + pg8000 (同步 DDL) | - |
| 搜索引擎 | Elasticsearch | 8+ |
| 配置管理 | pydantic-settings | 2.6+ |
| 测试框架 | pytest + pytest-asyncio | 9.0+ / 0.26+ |

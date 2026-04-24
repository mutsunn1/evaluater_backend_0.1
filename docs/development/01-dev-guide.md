# 开发指南

## 1. 环境搭建

```bash
conda activate agent
pip install -r requirements.txt
```

## 2. 运行测试

```bash
# 单元+集成测试
pytest tests/ -v --ignore=tests/test_e2e_session.py

# E2E 测试（需服务运行中）
python -m tests.test_e2e_session --base-url http://localhost:8000
```

## 3. 数据库迁移

```bash
alembic init alembic
# 配置 alembic.ini
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

## 4. 新增智能体

### 4.1 创建工厂函数
```python
# agents/my_new_agent.py
from oxygent import oxy

def build_my_new_agent() -> list:
    return [
        oxy.ChatAgent(
            name="my_new_agent",
            desc="Description of what this agent does.",
            short_memory_size=0,  # 绕过 ES 历史查询
        ),
    ]
```

### 4.2 注册到 MAS
```python
# app/main.py
from agents.my_new_agent import build_my_new_agent

# 在 oxy_space 中添加
oxy_space = [
    ...
    *build_my_new_agent(),
    ...
]
```

### 4.3 在 Master Agent 中注册
```python
# agents/master_agent.py
sub_agents=[
    "generator_agent",
    "item_qa_agent",
    ...
    "my_new_agent",  # 新增
]
```

## 5. 新增题目类型

1. 在 `app/main.py` 的 `question_types` 列表中添加
2. 在 prompt 中添加新类型的 JSON 格式定义
3. 在前端 `QuestionRenderer.vue` 中添加渲染组件
4. 在 `types/index.ts` 的 `QuestionType` 类型中添加

## 6. SSE 流式开发

### 6.1 后端
```python
async def event_generator():
    yield ": \n\n"  # flush marker
    yield f"event: thinking\ndata: {json.dumps({...})}\n\n: \n\n"
    yield f"event: question\ndata: {json.dumps({...})}\n\n"

return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    },
)
```

### 6.2 前端
```typescript
const resp = await fetch(url);
const reader = resp.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n');
  buffer = lines.pop() || '';
  for (const line of lines) {
    if (line.startsWith('event: ')) eventType = line.slice(7);
    if (line.startsWith('data: ')) handleData(JSON.parse(line.slice(6)));
  }
}
```

## 7. 并行优化

```python
# 错误示例：串行调用
result1 = await agent1_call()
summary1 = await summarize(result1)  # 阻塞
result2 = await agent2_call()

# 正确示例：并行执行
summary1_task = asyncio.create_task(summarize(result1))
result2 = await agent2_call()  # 与 summary1 并行
summary1 = await summary1_task
```

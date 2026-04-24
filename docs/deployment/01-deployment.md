# 部署指南

## 1. 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 运行环境 |
| PostgreSQL | 14+ | 主数据库 |
| Elasticsearch | 8.x | 搜索引擎（Docker） |
| Redis | 7+ | 缓存/队列（Docker） |
| Docker | 最新稳定版 | ES + Redis 容器 |

## 2. 数据库部署

### 2.1 PostgreSQL
```bash
# 创建数据库
psql -U postgres -c "CREATE DATABASE evaluator_db;"
```

### 2.2 Elasticsearch + Redis
```bash
# 一键部署
conda activate agent
python setup_es_v2.py
```

脚本自动：
1. 拉取 ES 和 Redis 镜像（支持国内镜像源）
2. 启动容器
3. 等待 ES 就绪
4. 创建所需索引（app_trace, app_node, mid_term_memory 等）

### 2.3 HSK 词库导入
```bash
python import_vocabulary.py
```

## 3. 配置

### 3.1 环境变量

```bash
cp .env.example .env
```

必须配置项：
- `DB_PASSWORD`: PostgreSQL 密码
- `DEFAULT_LLM_API_KEY`: LLM API 密钥
- `DEFAULT_LLM_BASE_URL`: LLM API 端点

### 3.2 数据库 URL
```env
DB_USER=postgres
DB_PASSWORD=你的密码
DB_HOST=localhost
DB_PORT=5432
DB_NAME=evaluator_db
DATABASE_URL=postgresql+asyncpg://postgres:密码@localhost:5432/evaluator_db
```

## 4. 启动

```bash
cd evaluater_backend_0.1
conda activate agent
python -m app.main
```

服务启动在 `http://0.0.0.0:8000`

## 5. 验证

```bash
# 检查健康状态
curl http://localhost:8000/health

# 检查 ES 状态
curl http://localhost:9200/_cluster/health

# 检查 Redis 状态
redis-cli ping
```

## 6. Docker 容器管理

```bash
# 查看容器状态
docker ps

# 停止服务
docker compose -f docker-compose.yml down

# 重启服务
docker compose -f docker-compose.yml restart

# 清理数据
docker compose -f docker-compose.yml down -v
```

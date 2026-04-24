# 开发文档索引

## 架构设计
- [系统架构总览](architecture/01-system-overview.md) - 整体架构、技术栈、目录结构
- [数据流转](architecture/02-data-flow.md) - 冷启动、出题、评分、Session 结束全流程

## 智能体
- [智能体总览](agents/01-agent-overview.md) - 角色职责、注册、通信模式
- [冷启动机制](agents/02-cold-start.md) - 回合定义、动态生成、收敛条件

## API
- [API 端点参考](api/01-api-reference.md) - 完整端点列表、请求/响应格式

## 部署
- [部署指南](deployment/01-deployment.md) - 环境要求、数据库、配置、启动

## 开发
- [开发指南](development/01-dev-guide.md) - 环境搭建、测试、新增 Agent、SSE 开发

## 服务
- [知识围栏服务](services/01-fence-service.md) - 词汇检查、题目验证、缓存策略
- [TTR 引擎](services/02-ttr-engine.md) - 分词算法、TTR/MTLD 计算、等级分析

# MangakAI 技术方案文档

## 📋 文档概览

本目录包含了 MangakAI 项目的完整技术方案文档，涵盖了从架构设计到部署运维的各个方面。

## 📚 文档结构

### 1. 核心技术方案
- **[技术方案文档](./technical-solution.md)** - 完整的技术架构和解决方案设计
- **[异步处理实现指南](./async-solution-implementation.md)** - 异步任务处理的详细实现方案

### 2. 部署和运维
- **[海外部署指南](./overseas-deployment-guide.md)** - 针对海外部署优化的完整指南
- **[监控运维指南](./monitoring-operations-guide.md)** - 监控、日志、告警和运维的完整方案

### 3. 配置文件
- **Docker 配置**
  - `../docker-compose.prod.yml` - 生产环境 Docker Compose 配置
  - `../Dockerfile.backend.prod` - 生产环境优化的 Dockerfile
  
- **Kubernetes 配置**
  - `../k8s/production/` - 生产环境 K8s 配置文件目录
    - `namespace.yaml` - 命名空间配置
    - `configmap.yaml` - 配置映射
    - `secrets.yaml` - 密钥配置模板
    - `deployments.yaml` - 部署配置

## 🎯 解决的核心问题

### 1. 长时间生成问题
- **问题**: 漫画生成耗时长，用户刷新页面会丢失结果
- **解决方案**: 异步任务队列 + WebSocket 实时通信 + 任务状态持久化

### 2. 存储可靠性问题
- **问题**: 图片存储在本地，服务器重启或负载均衡时会丢失
- **解决方案**: 云存储 (S3/OSS) + CDN 分发 + 数据库元数据管理

### 3. 海外部署优化
- **问题**: 海外部署需要优化中国用户访问体验
- **解决方案**: 新加坡/东京部署 + CloudFlare CDN + 网络优化

### 4. 系统可扩展性
- **问题**: 同步处理限制并发能力
- **解决方案**: 微服务架构 + Kubernetes + 自动扩缩容

## 🏗️ 技术架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端 React    │    │  API Gateway    │    │   负载均衡器     │
│                 │◄──►│   (FastAPI)     │◄──►│                 │
│ - 进度显示      │    │ - 任务创建      │    │ - 多实例部署     │
│ - WebSocket     │    │ - 状态查询      │    │ - 健康检查       │
│ - 历史记录      │    │ - 文件上传      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │   消息队列      │              │
         └──────────────►│   (Redis)       │◄─────────────┘
                        │ - 任务队列      │
                        │ - 状态存储      │
                        │ - 缓存层        │
                        └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │   工作进程      │
                        │   (Celery)      │
                        │ - 异步处理      │
                        │ - 图片生成      │
                        │ - 进度更新      │
                        └─────────────────┘
```

## 🚀 快速开始

### 1. 本地开发环境
```bash
# 启动开发环境
docker-compose up -d

# 运行数据库迁移
docker-compose exec backend alembic upgrade head
```

### 2. 生产环境部署
```bash
# 使用生产配置启动
docker-compose -f docker-compose.prod.yml up -d

# 或使用 Kubernetes
kubectl apply -f k8s/production/
```

### 3. 监控部署
```bash
# 部署监控栈
./scripts/deploy-monitoring.sh
```

## 📊 监控和运维

### 监控组件
- **Prometheus**: 指标收集和存储
- **Grafana**: 可视化仪表板
- **AlertManager**: 告警管理
- **Jaeger**: 分布式链路追踪
- **ELK Stack**: 日志收集和分析

### 关键指标
- API 响应时间 (目标: < 2秒)
- 错误率 (目标: < 1%)
- 任务成功率 (目标: > 95%)
- 系统可用性 (目标: > 99.9%)

## 🔧 配置说明

### 环境变量
```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@host:5432/dbname
REDIS_URL=redis://host:6379/0

# API 密钥
GEMINI_API_KEY=your-gemini-api-key

# AWS 配置
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET=your-s3-bucket

# 应用配置
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 资源配置
```yaml
# 生产环境推荐配置
Backend:
  replicas: 3
  resources:
    requests: { cpu: 500m, memory: 1Gi }
    limits: { cpu: 1000m, memory: 2Gi }

Celery Workers:
  replicas: 4
  resources:
    requests: { cpu: 1000m, memory: 2Gi }
    limits: { cpu: 2000m, memory: 4Gi }
```

## 📈 性能优化

### 1. 应用层优化
- 异步处理长时间任务
- 多级缓存策略
- 数据库连接池
- 图片压缩和 WebP 格式

### 2. 基础设施优化
- CDN 全球分发
- 自动扩缩容
- 负载均衡
- 数据库读写分离

### 3. 网络优化
- CloudFlare 智能路由
- HTTP/2 和 HTTP/3
- Gzip/Brotli 压缩
- 静态资源缓存

## 🔒 安全措施

### 1. 数据安全
- HTTPS 强制加密
- 数据库和存储加密
- 敏感信息脱敏
- 访问控制和权限管理

### 2. 应用安全
- API 限流和防护
- 输入验证和过滤
- CSRF 和 XSS 防护
- 安全头配置

### 3. 基础设施安全
- VPC 网络隔离
- 安全组配置
- WAF 防护
- DDoS 防护

## 💰 成本估算

### 小规模部署 (1000 DAU)
- **计算资源**: $200-300/月
- **存储和网络**: $100-150/月
- **总计**: $300-450/月

### 中等规模部署 (10000 DAU)
- **计算资源**: $800-1200/月
- **存储和网络**: $400-600/月
- **总计**: $1200-1800/月

## 🛠️ 故障排查

### 常见问题
1. **任务处理缓慢**: 检查 Celery Worker 数量和资源配置
2. **数据库连接问题**: 检查连接池配置和网络连通性
3. **图片生成失败**: 检查 Gemini API 配额和网络连接
4. **WebSocket 连接断开**: 检查负载均衡器配置和超时设置

### 排查工具
```bash
# 检查系统状态
./scripts/troubleshoot.sh

# 查看日志
kubectl logs -f deployment/mangakai-backend -n mangakai-prod

# 检查指标
curl http://prometheus:9090/api/v1/query?query=up
```

## 📞 支持和联系

- **技术文档**: 本目录下的各个 .md 文件
- **配置文件**: `../k8s/` 和 `../config/` 目录
- **部署脚本**: `../scripts/` 目录
- **监控面板**: Grafana 仪表板配置

## 🔄 更新日志

### v1.0.0 (2024-01-01)
- 初始版本技术方案
- 异步处理架构设计
- 海外部署方案
- 监控运维体系

---

**注意**: 在实际部署前，请仔细阅读各个文档，并根据实际环境调整配置参数。
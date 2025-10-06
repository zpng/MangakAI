# MangakAI 技术方案文档

## 1. 项目概述

### 1.1 项目背景
MangakAI 是一个基于 AI 的漫画生成平台，用户可以通过文本输入生成个性化的漫画面板。当前系统面临以下挑战：

- **长时间生成问题**：漫画生成耗时较长（2-5分钟），用户刷新页面会丢失结果
- **存储可靠性问题**：图片存储在本地文件系统，服务器重启或负载均衡时会丢失
- **用户体验问题**：缺乏进度反馈，无法了解生成状态
- **扩展性问题**：同步处理限制了系统的并发能力

### 1.2 解决目标
- 实现异步任务处理，支持长时间运行的生成任务
- 建立可靠的持久化存储方案
- 提供实时进度反馈和状态跟踪
- 支持海外部署，优化中国用户访问体验
- 提高系统可扩展性和可靠性

## 2. 系统架构设计

### 2.1 整体架构

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
                                 │
         ┌─────────────────┬─────────────────┬─────────────────┐
         │                 │                 │                 │
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   数据库        │ │   云存储        │ │   AI服务        │ │   监控系统      │
│ (PostgreSQL)    │ │   (S3/OSS)      │ │  (Gemini API)   │ │ - 任务监控      │
│ - 任务元数据    │ │ - 图片存储      │ │ - 图片生成      │ │ - 性能监控      │
│ - 用户会话      │ │ - 静态资源      │ │ - 场景分析      │ │ - 错误追踪      │
└─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 2.2 核心组件

#### 2.2.1 API Gateway (FastAPI)
- **职责**：接收用户请求，创建异步任务，返回任务ID
- **功能**：
  - 用户认证和会话管理
  - 请求参数验证
  - 任务创建和状态查询
  - WebSocket 连接管理
  - 静态文件服务

#### 2.2.2 任务队列系统 (Celery + Redis)
- **职责**：管理异步任务的执行和状态
- **功能**：
  - 任务分发和负载均衡
  - 任务状态跟踪
  - 失败重试机制
  - 任务优先级管理

#### 2.2.3 工作进程 (Celery Workers)
- **职责**：执行实际的漫画生成任务
- **功能**：
  - 场景分析和描述生成
  - AI 图片生成调用
  - 图片处理和优化
  - 进度状态更新

#### 2.2.4 存储系统
- **数据库 (PostgreSQL)**：存储任务元数据、用户会话、系统配置
- **对象存储 (S3/OSS)**：存储生成的图片、用户上传的模板
- **缓存 (Redis)**：缓存热点数据、会话信息、任务状态

## 3. 异步处理解决方案

### 3.1 任务流程设计

```
用户提交请求 → 创建异步任务 → 返回任务ID → 后台处理 → 实时推送进度 → 完成通知
```

### 3.2 任务状态定义

```python
TASK_STATES = {
    'PENDING': '等待处理',
    'PROCESSING': '正在处理',
    'SCENE_GENERATION': '生成场景描述',
    'IMAGE_GENERATION': '生成图片',
    'PANEL_PROCESSING': '处理面板 {current}/{total}',
    'UPLOADING': '上传图片',
    'COMPLETED': '完成',
    'FAILED': '失败'
}
```

### 3.3 数据库设计

```sql
-- 任务表
CREATE TABLE manga_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_session_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    story_text TEXT NOT NULL,
    parameters JSONB,
    progress INTEGER DEFAULT 0,
    total_panels INTEGER DEFAULT 5,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 生成的面板表
CREATE TABLE manga_panels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES manga_tasks(id) ON DELETE CASCADE,
    panel_number INTEGER NOT NULL,
    scene_description TEXT,
    image_url VARCHAR(500),
    image_path VARCHAR(500),
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户会话表
CREATE TABLE user_sessions (
    id VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- 索引优化
CREATE INDEX idx_manga_tasks_session_id ON manga_tasks(user_session_id);
CREATE INDEX idx_manga_tasks_status ON manga_tasks(status);
CREATE INDEX idx_manga_tasks_created_at ON manga_tasks(created_at);
CREATE INDEX idx_manga_panels_task_id ON manga_panels(task_id);
```

### 3.4 实时通信方案

#### WebSocket 实现
```python
# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    async def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
    
    async def send_progress_update(self, session_id: str, progress_data: dict):
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(progress_data)
```

## 4. 持久化存储方案

### 4.1 云存储架构

#### 主存储方案
- **服务商**：AWS S3 (新加坡区域)
- **CDN**：CloudFront 全球分发
- **备份**：跨区域自动备份到东京区域

#### 存储结构
```
mangakai-images/
├── tasks/
│   └── {task_id}/
│       ├── panel_1.webp
│       ├── panel_2.webp
│       └── ...
├── templates/
│   └── user_uploads/
│       └── {session_id}/
└── references/
    └── user_uploads/
        └── {session_id}/
```

### 4.2 图片处理优化

```python
# 图片优化处理
def optimize_image_for_web(image_path: str, output_path: str):
    """优化图片用于网络传输"""
    with Image.open(image_path) as img:
        # 转换为 RGB 模式
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 压缩并保存为 WebP 格式
        img.save(
            output_path,
            'WEBP',
            quality=85,
            optimize=True,
            method=6  # 最佳压缩
        )
```

### 4.3 缓存策略

#### 多级缓存设计
```python
CACHE_CONFIG = {
    'L1_BROWSER': {
        'type': '浏览器缓存',
        'duration': '24小时',
        'content': ['生成的图片', '静态资源']
    },
    'L2_CDN': {
        'type': 'CDN缓存',
        'duration': '7天',
        'content': ['图片资源', '前端静态文件']
    },
    'L3_REDIS': {
        'type': 'Redis缓存',
        'duration': '1小时',
        'content': ['任务状态', '用户会话', 'API响应']
    },
    'L4_APPLICATION': {
        'type': '应用内存缓存',
        'duration': '10分钟',
        'content': ['配置信息', '模板数据']
    }
}
```

## 5. 海外部署方案

### 5.1 云服务商选择

#### 推荐配置
- **主要部署**：AWS 新加坡区域 (ap-southeast-1)
- **备用部署**：Google Cloud 东京区域 (asia-northeast1)
- **CDN 加速**：CloudFlare + AWS CloudFront

#### 网络优化
```yaml
网络配置:
  主CDN: CloudFlare
    - 全球 POP 节点
    - 智能路由
    - DDoS 防护
  
  备用CDN: AWS CloudFront
    - 亚太区域优化
    - 边缘计算
    - 实时压缩
  
  专线加速:
    - AWS Global Accelerator
    - 香港/新加坡专线接入
```

### 5.2 性能优化策略

#### 延迟优化
- **目标延迟**：中国大陆用户 < 200ms
- **优化手段**：
  - 就近接入点部署
  - 智能 DNS 解析
  - HTTP/2 和 HTTP/3 支持
  - Gzip/Brotli 压缩

#### 带宽优化
- **图片压缩**：WebP 格式，85% 质量
- **代码分割**：前端按需加载
- **资源合并**：CSS/JS 文件合并
- **预加载策略**：关键资源预加载

## 6. 监控和运维

### 6.1 监控指标

#### 业务指标
```yaml
业务监控:
  - 任务成功率 (目标: >95%)
  - 平均生成时间 (目标: <3分钟)
  - 用户活跃度
  - 图片生成质量评分

技术指标:
  - API 响应时间 (目标: <2秒)
  - 系统可用性 (目标: >99.9%)
  - 错误率 (目标: <1%)
  - 资源使用率
```

#### 告警配置
```yaml
告警规则:
  严重:
    - 系统不可用 > 1分钟
    - 错误率 > 5%
    - 数据库连接失败
  
  警告:
    - API 响应时间 > 5秒
    - CPU 使用率 > 80%
    - 内存使用率 > 85%
    - 磁盘使用率 > 90%
  
  通知方式:
    - 邮件通知
    - 钉钉/企业微信
    - 短信通知 (严重告警)
```

### 6.2 日志管理

#### 日志分类
```python
LOG_LEVELS = {
    'ERROR': '错误日志 - 系统异常、任务失败',
    'WARN': '警告日志 - 性能问题、资源不足',
    'INFO': '信息日志 - 任务状态、用户操作',
    'DEBUG': '调试日志 - 详细执行过程'
}
```

#### 日志存储
- **实时日志**：ELK Stack (Elasticsearch + Logstash + Kibana)
- **长期存储**：S3 归档存储
- **日志轮转**：按天分割，保留30天

## 7. 安全方案

### 7.1 数据安全

#### 传输安全
- **HTTPS 强制**：所有 API 强制使用 HTTPS
- **证书管理**：Let's Encrypt 自动续期
- **HSTS 策略**：强制安全传输

#### 存储安全
- **数据加密**：数据库和对象存储启用加密
- **访问控制**：IAM 角色和权限管理
- **备份加密**：备份数据加密存储

### 7.2 应用安全

#### API 安全
```python
# 安全中间件配置
SECURITY_CONFIG = {
    'rate_limiting': {
        'requests_per_minute': 60,
        'burst_size': 10
    },
    'cors': {
        'allowed_origins': ['https://mangakai.com'],
        'allowed_methods': ['GET', 'POST', 'PUT', 'DELETE'],
        'allowed_headers': ['*']
    },
    'csrf_protection': True,
    'xss_protection': True
}
```

#### 输入验证
- **参数验证**：Pydantic 模型验证
- **文件上传**：类型和大小限制
- **SQL 注入防护**：参数化查询
- **XSS 防护**：输出编码

## 8. 成本估算

### 8.1 基础设施成本 (月费用)

#### 小规模部署 (1000 DAU)
```yaml
计算资源:
  - Web 服务器: 2x t3.medium ($60)
  - Worker 节点: 2x t3.medium ($60)
  - 数据库: db.t3.micro ($20)
  - Redis: cache.t3.micro ($15)
  小计: $155

存储和网络:
  - S3 存储: 100GB ($25)
  - CloudFront CDN: 1TB ($85)
  - 数据传输: ($30)
  小计: $140

总计: ~$300/月
```

#### 中等规模部署 (10000 DAU)
```yaml
计算资源:
  - Web 服务器: 4x t3.large ($280)
  - Worker 节点: 6x t3.large ($420)
  - 数据库: db.r5.large ($180)
  - Redis: cache.r5.large ($120)
  小计: $1000

存储和网络:
  - S3 存储: 1TB ($250)
  - CloudFront CDN: 10TB ($850)
  - 数据传输: ($200)
  小计: $1300

总计: ~$2300/月
```

### 8.2 成本优化建议

#### 资源优化
- **自动扩缩容**：根据负载自动调整实例数量
- **预留实例**：长期资源购买预留实例 (节省30-50%)
- **Spot 实例**：Worker 节点使用 Spot 实例 (节省60-70%)

#### 存储优化
- **生命周期管理**：旧图片自动转移到低成本存储
- **压缩优化**：图片压缩减少存储和传输成本
- **缓存策略**：合理的缓存策略减少 API 调用

## 9. 实施计划

### 9.1 第一阶段：异步化改造 (2-3周)

#### Week 1: 基础设施搭建
- [ ] 搭建 Redis 集群
- [ ] 配置 Celery 任务队列
- [ ] 创建数据库表结构
- [ ] 实现基本的任务创建和状态查询 API

#### Week 2: 异步任务实现
- [ ] 重构漫画生成逻辑为异步任务
- [ ] 实现进度跟踪和状态更新
- [ ] 添加 WebSocket 实时通信
- [ ] 前端适配异步处理流程

#### Week 3: 测试和优化
- [ ] 单元测试和集成测试
- [ ] 性能测试和调优
- [ ] 错误处理和重试机制
- [ ] 用户体验优化

### 9.2 第二阶段：存储优化 (2周)

#### Week 4: 云存储集成
- [ ] 配置 AWS S3 存储
- [ ] 实现图片上传和 CDN 分发
- [ ] 数据迁移和备份策略
- [ ] 图片优化和压缩

#### Week 5: 缓存和性能优化
- [ ] 实现多级缓存策略
- [ ] API 响应优化
- [ ] 数据库查询优化
- [ ] 前端资源优化

### 9.3 第三阶段：海外部署 (2周)

#### Week 6: 部署环境搭建
- [ ] AWS 环境配置
- [ ] Kubernetes 集群部署
- [ ] CI/CD 流水线搭建
- [ ] 监控和日志系统

#### Week 7: 上线和优化
- [ ] 生产环境部署
- [ ] 性能测试和调优
- [ ] 用户体验测试
- [ ] 文档完善和培训

## 10. 风险评估和应对

### 10.1 技术风险

#### 高风险
- **AI API 限制**：Gemini API 可能有调用限制
  - **应对**：实现多 API 提供商支持，添加降级策略
- **网络延迟**：海外部署可能影响中国用户体验
  - **应对**：多区域部署，智能路由优化

#### 中风险
- **数据一致性**：分布式系统的数据一致性问题
  - **应对**：实现事务管理和数据校验机制
- **扩展性瓶颈**：高并发时的性能瓶颈
  - **应对**：水平扩展设计，负载测试验证

### 10.2 业务风险

#### 合规风险
- **数据保护**：用户数据和生成内容的保护
  - **应对**：实施数据加密和访问控制
- **内容审核**：生成内容的合规性
  - **应对**：添加内容审核机制和人工复查

#### 成本风险
- **资源成本**：云服务成本可能超出预算
  - **应对**：实施成本监控和自动优化
- **API 成本**：AI API 调用成本增长
  - **应对**：优化调用策略，实现成本控制

## 11. 总结

本技术方案通过异步任务处理、持久化存储、海外部署优化等手段，全面解决了 MangakAI 项目面临的技术挑战。方案具有以下特点：

### 11.1 核心优势
- **高可靠性**：分布式架构，多重备份保障
- **高性能**：异步处理，多级缓存优化
- **高可用性**：自动扩缩容，故障自愈能力
- **用户友好**：实时进度反馈，良好的交互体验

### 11.2 技术创新
- **智能任务调度**：基于负载的任务分发
- **多级存储优化**：热冷数据分离存储
- **全球化部署**：针对中国用户的网络优化
- **实时通信**：WebSocket 进度推送

### 11.3 可扩展性
- **水平扩展**：支持多实例部署
- **模块化设计**：组件可独立扩展
- **插件化架构**：支持功能模块扩展
- **多云部署**：支持多云厂商部署

通过本方案的实施，MangakAI 将具备企业级的稳定性和可扩展性，为用户提供优质的漫画生成服务体验。
# MangakAI 海外部署指南

## 1. 部署概述

本指南详细描述了如何在海外云服务商部署 MangakAI 系统，以优化中国用户的访问体验。

### 1.1 部署目标
- **低延迟**：中国大陆用户访问延迟 < 200ms
- **高可用**：系统可用性 > 99.9%
- **高性能**：支持并发用户数 > 1000
- **成本优化**：在性能和成本之间找到平衡

### 1.2 推荐架构
- **主要部署区域**：AWS 新加坡 (ap-southeast-1)
- **备用部署区域**：Google Cloud 东京 (asia-northeast1)
- **CDN 加速**：CloudFlare + AWS CloudFront
- **数据库**：跨区域主从复制

## 2. AWS 部署方案

### 2.1 基础设施规划

#### 网络架构
```yaml
VPC 配置:
  CIDR: 10.0.0.0/16
  
子网规划:
  公有子网:
    - 10.0.1.0/24 (AZ-1a) - 负载均衡器
    - 10.0.2.0/24 (AZ-1b) - 负载均衡器
  
  私有子网:
    - 10.0.10.0/24 (AZ-1a) - 应用服务器
    - 10.0.11.0/24 (AZ-1b) - 应用服务器
    - 10.0.20.0/24 (AZ-1a) - 数据库
    - 10.0.21.0/24 (AZ-1b) - 数据库
```

#### 安全组配置
```yaml
# 负载均衡器安全组
ALB-SG:
  入站规则:
    - 端口 80: 0.0.0.0/0 (HTTP)
    - 端口 443: 0.0.0.0/0 (HTTPS)
  出站规则:
    - 全部流量: 0.0.0.0/0

# 应用服务器安全组
APP-SG:
  入站规则:
    - 端口 8000: ALB-SG (API 服务)
    - 端口 22: 管理员 IP (SSH)
  出站规则:
    - 全部流量: 0.0.0.0/0

# 数据库安全组
DB-SG:
  入站规则:
    - 端口 5432: APP-SG (PostgreSQL)
    - 端口 6379: APP-SG (Redis)
  出站规则:
    - 无
```

### 2.2 Terraform 基础设施代码

```hcl
# terraform/main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "mangakai-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "mangakai-igw"
  }
}

# 公有子网
resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "mangakai-public-${count.index + 1}"
  }
}

# 私有子网
resource "aws_subnet" "private" {
  count = 4

  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index % 2]

  tags = {
    Name = "mangakai-private-${count.index + 1}"
  }
}

# NAT Gateway
resource "aws_eip" "nat" {
  count = 2
  domain = "vpc"

  tags = {
    Name = "mangakai-nat-eip-${count.index + 1}"
  }
}

resource "aws_nat_gateway" "main" {
  count = 2

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = {
    Name = "mangakai-nat-${count.index + 1}"
  }
}

# 路由表
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "mangakai-public-rt"
  }
}

resource "aws_route_table" "private" {
  count = 2

  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = {
    Name = "mangakai-private-rt-${count.index + 1}"
  }
}

# 路由表关联
resource "aws_route_table_association" "public" {
  count = 2

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count = 4

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index % 2].id
}

# 安全组
resource "aws_security_group" "alb" {
  name_prefix = "mangakai-alb-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "mangakai-alb-sg"
  }
}

resource "aws_security_group" "app" {
  name_prefix = "mangakai-app-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "mangakai-app-sg"
  }
}

# RDS 子网组
resource "aws_db_subnet_group" "main" {
  name       = "mangakai-db-subnet-group"
  subnet_ids = [aws_subnet.private[2].id, aws_subnet.private[3].id]

  tags = {
    Name = "mangakai-db-subnet-group"
  }
}

# RDS 实例
resource "aws_db_instance" "main" {
  identifier = "mangakai-postgres"

  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.db_instance_class

  allocated_storage     = 100
  max_allocated_storage = 1000
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "mangakai"
  username = var.db_username
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  skip_final_snapshot = false
  final_snapshot_identifier = "mangakai-final-snapshot"

  tags = {
    Name = "mangakai-postgres"
  }
}

# ElastiCache 子网组
resource "aws_elasticache_subnet_group" "main" {
  name       = "mangakai-cache-subnet-group"
  subnet_ids = [aws_subnet.private[0].id, aws_subnet.private[1].id]
}

# ElastiCache Redis 集群
resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = "mangakai-redis"
  description                = "Redis cluster for MangakAI"

  node_type            = var.redis_node_type
  port                 = 6379
  parameter_group_name = "default.redis7"

  num_cache_clusters = 2
  
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = {
    Name = "mangakai-redis"
  }
}

# S3 存储桶
resource "aws_s3_bucket" "images" {
  bucket = var.s3_bucket_name

  tags = {
    Name = "mangakai-images"
  }
}

resource "aws_s3_bucket_versioning" "images" {
  bucket = aws_s3_bucket.images.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_encryption" "images" {
  bucket = aws_s3_bucket.images.id

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}

# CloudFront 分发
resource "aws_cloudfront_distribution" "main" {
  origin {
    domain_name = aws_s3_bucket.images.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.images.bucket}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.main.cloudfront_access_identity_path
    }
  }

  enabled = true

  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.images.bucket}"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 31536000
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name = "mangakai-cloudfront"
  }
}

resource "aws_cloudfront_origin_access_identity" "main" {
  comment = "OAI for MangakAI S3 bucket"
}
```

### 2.3 变量定义

```hcl
# terraform/variables.tf
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "admin_cidr" {
  description = "CIDR block for admin access"
  type        = string
  default     = "0.0.0.0/0"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "mangakai"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for images"
  type        = string
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
}
```

### 2.4 输出定义

```hcl
# terraform/outputs.tf
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.main.endpoint
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.images.bucket
}

output "cloudfront_domain" {
  description = "CloudFront domain name"
  value       = aws_cloudfront_distribution.main.domain_name
}
```

## 3. Kubernetes 部署配置

### 3.1 EKS 集群配置

```yaml
# k8s/cluster.yaml
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig

metadata:
  name: mangakai-cluster
  region: ap-southeast-1
  version: "1.28"

vpc:
  subnets:
    private:
      ap-southeast-1a: { id: subnet-xxx }
      ap-southeast-1b: { id: subnet-yyy }
    public:
      ap-southeast-1a: { id: subnet-aaa }
      ap-southeast-1b: { id: subnet-bbb }

nodeGroups:
  - name: mangakai-workers
    instanceType: t3.medium
    desiredCapacity: 2
    minSize: 1
    maxSize: 5
    volumeSize: 50
    volumeType: gp3
    
    subnets:
      - subnet-xxx
      - subnet-yyy
    
    iam:
      withAddonPolicies:
        imageBuilder: true
        autoScaler: true
        ebs: true
        efs: true
        albIngress: true
        cloudWatch: true
    
    tags:
      Environment: production
      Application: mangakai

addons:
  - name: vpc-cni
  - name: coredns
  - name: kube-proxy
  - name: aws-ebs-csi-driver

cloudWatch:
  clusterLogging:
    enableTypes: ["*"]
```

### 3.2 应用部署配置

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mangakai
  labels:
    name: mangakai

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mangakai-config
  namespace: mangakai
data:
  REDIS_URL: "redis://mangakai-redis:6379/0"
  DATABASE_URL: "postgresql://mangakai:password@postgres-service:5432/mangakai"
  AWS_REGION: "ap-southeast-1"
  S3_BUCKET: "mangakai-images-prod"

---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: mangakai-secrets
  namespace: mangakai
type: Opaque
stringData:
  GEMINI_API_KEY: "your-gemini-api-key"
  DATABASE_PASSWORD: "your-database-password"
  AWS_ACCESS_KEY_ID: "your-aws-access-key"
  AWS_SECRET_ACCESS_KEY: "your-aws-secret-key"

---
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mangakai-backend
  namespace: mangakai
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mangakai-backend
  template:
    metadata:
      labels:
        app: mangakai-backend
    spec:
      containers:
      - name: backend
        image: mangakai/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: mangakai-config
              key: REDIS_URL
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: mangakai-config
              key: DATABASE_URL
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: mangakai-secrets
              key: GEMINI_API_KEY
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: mangakai-secrets
              key: AWS_ACCESS_KEY_ID
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: mangakai-secrets
              key: AWS_SECRET_ACCESS_KEY
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
# k8s/celery-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mangakai-celery
  namespace: mangakai
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mangakai-celery
  template:
    metadata:
      labels:
        app: mangakai-celery
    spec:
      containers:
      - name: celery-worker
        image: mangakai/backend:latest
        command: ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=2"]
        env:
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: mangakai-config
              key: REDIS_URL
        - name: DATABASE_URL
          valueFrom:
            configMapKeyRef:
              name: mangakai-config
              key: DATABASE_URL
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: mangakai-secrets
              key: GEMINI_API_KEY
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"

---
# k8s/redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mangakai-redis
  namespace: mangakai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mangakai-redis
  template:
    metadata:
      labels:
        app: mangakai-redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command: ["redis-server", "--appendonly", "yes"]
        volumeMounts:
        - name: redis-data
          mountPath: /data
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: redis-data
        persistentVolumeClaim:
          claimName: redis-pvc

---
# k8s/services.yaml
apiVersion: v1
kind: Service
metadata:
  name: mangakai-backend-service
  namespace: mangakai
spec:
  selector:
    app: mangakai-backend
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP

---
apiVersion: v1
kind: Service
metadata:
  name: mangakai-redis
  namespace: mangakai
spec:
  selector:
    app: mangakai-redis
  ports:
  - protocol: TCP
    port: 6379
    targetPort: 6379
  type: ClusterIP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mangakai-ingress
  namespace: mangakai
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/ssl-redirect: '443'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:ap-southeast-1:123456789012:certificate/xxx
spec:
  rules:
  - host: api.mangakai.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mangakai-backend-service
            port:
              number: 8000

---
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: mangakai-backend-hpa
  namespace: mangakai
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mangakai-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## 4. CDN 和网络优化

### 4.1 CloudFlare 配置

```yaml
# cloudflare/dns-records.yaml
DNS 记录配置:
  - 类型: A
    名称: api
    值: ALB-IP-ADDRESS
    代理: 开启
    TTL: 自动
  
  - 类型: CNAME
    名称: cdn
    值: cloudfront-domain.cloudfront.net
    代理: 开启
    TTL: 自动
  
  - 类型: CNAME
    名称: www
    值: mangakai.com
    代理: 开启
    TTL: 自动

页面规则:
  - URL: api.mangakai.com/*
    设置:
      - 缓存级别: 绕过
      - SSL: 完全(严格)
      - 始终使用 HTTPS: 开启
  
  - URL: cdn.mangakai.com/*
    设置:
      - 缓存级别: 缓存所有内容
      - 边缘缓存 TTL: 1个月
      - 浏览器缓存 TTL: 1天
      - SSL: 完全(严格)

安全设置:
  - DDoS 防护: 开启
  - WAF: 开启
  - Bot Fight Mode: 开启
  - Rate Limiting: 
    - API 端点: 100 请求/分钟
    - 静态资源: 1000 请求/分钟
```

### 4.2 网络优化配置

```nginx
# nginx/nginx.conf
upstream backend {
    least_conn;
    server backend-1:8000 max_fails=3 fail_timeout=30s;
    server backend-2:8000 max_fails=3 fail_timeout=30s;
    server backend-3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.mangakai.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.mangakai.com;
    
    # SSL 配置
    ssl_certificate /etc/ssl/certs/mangakai.crt;
    ssl_certificate_key /etc/ssl/private/mangakai.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # 性能优化
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
    
    # 缓存配置
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header X-Content-Type-Options nosniff;
    }
    
    # API 代理
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

## 5. 监控和日志

### 5.1 Prometheus 监控配置

```yaml
# monitoring/prometheus.yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
    - role: pod
    relabel_configs:
    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
      action: keep
      regex: true
    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
      action: replace
      target_label: __metrics_path__
      regex: (.+)

  - job_name: 'mangakai-backend'
    static_configs:
    - targets: ['mangakai-backend-service:8000']
    metrics_path: /metrics
    scrape_interval: 30s

  - job_name: 'redis'
    static_configs:
    - targets: ['mangakai-redis:6379']

alerting:
  alertmanagers:
  - static_configs:
    - targets:
      - alertmanager:9093

---
# monitoring/alert-rules.yaml
groups:
- name: mangakai.rules
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }} errors per second"

  - alert: HighResponseTime
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High response time detected"
      description: "95th percentile response time is {{ $value }} seconds"

  - alert: PodCrashLooping
    expr: rate(kube_pod_container_status_restarts_total[15m]) > 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Pod is crash looping"
      description: "Pod {{ $labels.pod }} is crash looping"

  - alert: HighMemoryUsage
    expr: (container_memory_usage_bytes / container_spec_memory_limit_bytes) > 0.9
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High memory usage"
      description: "Memory usage is {{ $value | humanizePercentage }}"
```

### 5.2 Grafana 仪表板

```json
{
  "dashboard": {
    "title": "MangakAI Monitoring Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{status}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ]
      },
      {
        "title": "Active Tasks",
        "type": "singlestat",
        "targets": [
          {
            "expr": "celery_active_tasks",
            "legendFormat": "Active Tasks"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "container_memory_usage_bytes / container_spec_memory_limit_bytes",
            "legendFormat": "{{pod}}"
          }
        ]
      }
    ]
  }
}
```

## 6. 部署脚本

### 6.1 自动化部署脚本

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

# 配置变量
AWS_REGION="ap-southeast-1"
CLUSTER_NAME="mangakai-cluster"
NAMESPACE="mangakai"
IMAGE_TAG=${1:-latest}

echo "Starting deployment of MangakAI to AWS..."

# 1. 构建和推送 Docker 镜像
echo "Building and pushing Docker images..."
docker build -t mangakai/backend:${IMAGE_TAG} .
docker tag mangakai/backend:${IMAGE_TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/mangakai/backend:${IMAGE_TAG}

# 登录 ECR
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# 推送镜像
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/mangakai/backend:${IMAGE_TAG}

# 2. 更新 Kubernetes 配置
echo "Updating Kubernetes configurations..."
kubectl config use-context arn:aws:eks:${AWS_REGION}:${AWS_ACCOUNT_ID}:cluster/${CLUSTER_NAME}

# 创建命名空间（如果不存在）
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# 应用配置
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# 3. 部署应用
echo "Deploying applications..."
envsubst < k8s/backend-deployment.yaml | kubectl apply -f -
envsubst < k8s/celery-deployment.yaml | kubectl apply -f -
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/services.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml

# 4. 等待部署完成
echo "Waiting for deployment to complete..."
kubectl rollout status deployment/mangakai-backend -n ${NAMESPACE} --timeout=300s
kubectl rollout status deployment/mangakai-celery -n ${NAMESPACE} --timeout=300s

# 5. 运行数据库迁移
echo "Running database migrations..."
kubectl run migration --image=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/mangakai/backend:${IMAGE_TAG} \
  --rm -i --restart=Never -n ${NAMESPACE} \
  --env="DATABASE_URL=$(kubectl get secret mangakai-secrets -n ${NAMESPACE} -o jsonpath='{.data.DATABASE_URL}' | base64 -d)" \
  -- alembic upgrade head

# 6. 验证部署
echo "Verifying deployment..."
kubectl get pods -n ${NAMESPACE}
kubectl get services -n ${NAMESPACE}
kubectl get ingress -n ${NAMESPACE}

# 获取访问地址
INGRESS_HOST=$(kubectl get ingress mangakai-ingress -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "Application deployed successfully!"
echo "Access URL: https://${INGRESS_HOST}"

echo "Deployment completed successfully!"
```

### 6.2 回滚脚本

```bash
#!/bin/bash
# scripts/rollback.sh

set -e

NAMESPACE="mangakai"
REVISION=${1:-1}

echo "Rolling back MangakAI deployment..."

# 回滚后端部署
kubectl rollout undo deployment/mangakai-backend -n ${NAMESPACE} --to-revision=${REVISION}

# 回滚 Celery 部署
kubectl rollout undo deployment/mangakai-celery -n ${NAMESPACE} --to-revision=${REVISION}

# 等待回滚完成
kubectl rollout status deployment/mangakai-backend -n ${NAMESPACE}
kubectl rollout status deployment/mangakai-celery -n ${NAMESPACE}

echo "Rollback completed successfully!"
```

## 7. 成本优化

### 7.1 资源优化策略

```yaml
# 成本优化配置
资源配置:
  生产环境:
    Backend Pods: 3 replicas
    - CPU: 500m request, 1000m limit
    - Memory: 512Mi request, 1Gi limit
    
    Celery Workers: 2 replicas
    - CPU: 500m request, 1000m limit
    - Memory: 1Gi request, 2Gi limit
    
    Redis: 1 replica
    - CPU: 250m request, 500m limit
    - Memory: 256Mi request, 512Mi limit

  开发环境:
    Backend Pods: 1 replica
    - CPU: 250m request, 500m limit
    - Memory: 256Mi request, 512Mi limit
    
    Celery Workers: 1 replica
    - CPU: 250m request, 500m limit
    - Memory: 512Mi request, 1Gi limit

自动扩缩容:
  HPA 配置:
    - CPU 阈值: 70%
    - 内存阈值: 80%
    - 最小副本数: 2
    - 最大副本数: 10
  
  VPA 配置:
    - 自动调整资源请求
    - 基于历史使用情况
    - 避免资源浪费

Spot 实例使用:
  - Worker 节点使用 Spot 实例
  - 节省 60-70% 成本
  - 配置多个实例类型
  - 自动故障转移
```

### 7.2 成本监控

```bash
#!/bin/bash
# scripts/cost-monitor.sh

# AWS 成本监控脚本
echo "Generating AWS cost report..."

# 获取当月成本
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# 获取资源使用情况
kubectl top nodes
kubectl top pods -n mangakai

# 生成成本优化建议
echo "Cost optimization recommendations:"
echo "1. Consider using Spot instances for worker nodes"
echo "2. Enable cluster autoscaler for dynamic scaling"
echo "3. Use Reserved Instances for stable workloads"
echo "4. Implement resource quotas and limits"
```

## 8. 灾难恢复

### 8.1 备份策略

```yaml
# 备份配置
数据库备份:
  - 自动备份: 每日 3:00 AM
  - 保留期: 7天
  - 跨区域复制: 东京区域
  - 加密: AES-256

Redis 备份:
  - AOF 持久化: 开启
  - RDB 快照: 每小时
  - 保留期: 24小时

S3 备份:
  - 版本控制: 开启
  - 跨区域复制: 东京区域
  - 生命周期管理:
    - 30天后转移到 IA
    - 90天后转移到 Glacier
    - 365天后删除

配置备份:
  - Kubernetes 配置: Git 仓库
  - Terraform 状态: S3 + DynamoDB 锁
  - 应用配置: ConfigMap 备份
```

### 8.2 恢复流程

```bash
#!/bin/bash
# scripts/disaster-recovery.sh

set -e

BACKUP_DATE=${1:-$(date -d "yesterday" +%Y-%m-%d)}
REGION=${2:-ap-southeast-1}

echo "Starting disaster recovery for date: ${BACKUP_DATE}"

# 1. 恢复数据库
echo "Restoring database..."
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier mangakai-postgres-restored \
  --db-snapshot-identifier mangakai-postgres-${BACKUP_DATE} \
  --region ${REGION}

# 2. 恢复 Redis
echo "Restoring Redis..."
aws elasticache create-cache-cluster \
  --cache-cluster-id mangakai-redis-restored \
  --snapshot-name mangakai-redis-${BACKUP_DATE} \
  --region ${REGION}

# 3. 恢复应用
echo "Restoring application..."
kubectl apply -f k8s/

# 4. 验证恢复
echo "Verifying recovery..."
kubectl get pods -n mangakai
kubectl logs -l app=mangakai-backend -n mangakai --tail=50

echo "Disaster recovery completed!"
```

这个海外部署指南提供了完整的部署方案，包括基础设施配置、Kubernetes 部署、网络优化、监控告警、成本控制和灾难恢复等各个方面，确保 MangakAI 能够在海外稳定运行并为中国用户提供良好的访问体验。
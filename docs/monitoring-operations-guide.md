# MangakAI 监控和运维指南

## 1. 监控架构概述

### 1.1 监控栈组件
- **Prometheus**: 指标收集和存储
- **Grafana**: 可视化仪表板
- **AlertManager**: 告警管理
- **Jaeger**: 分布式链路追踪
- **ELK Stack**: 日志收集和分析
- **Sentry**: 错误追踪和性能监控

### 1.2 监控层级
```
应用层监控 → 服务层监控 → 基础设施监控 → 业务监控
```

## 2. Prometheus 配置

### 2.1 Prometheus 主配置

```yaml
# config/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'mangakai-prod'
    region: 'ap-southeast-1'

rule_files:
  - "/etc/prometheus/rules/*.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  # Kubernetes API Server
  - job_name: 'kubernetes-apiservers'
    kubernetes_sd_configs:
    - role: endpoints
    scheme: https
    tls_config:
      ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
    bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
    relabel_configs:
    - source_labels: [__meta_kubernetes_namespace, __meta_kubernetes_service_name, __meta_kubernetes_endpoint_port_name]
      action: keep
      regex: default;kubernetes;https

  # Kubernetes Nodes
  - job_name: 'kubernetes-nodes'
    kubernetes_sd_configs:
    - role: node
    scheme: https
    tls_config:
      ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
    bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
    relabel_configs:
    - action: labelmap
      regex: __meta_kubernetes_node_label_(.+)
    - target_label: __address__
      replacement: kubernetes.default.svc:443
    - source_labels: [__meta_kubernetes_node_name]
      regex: (.+)
      target_label: __metrics_path__
      replacement: /api/v1/nodes/${1}/proxy/metrics

  # Kubernetes Pods
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
    - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
      action: replace
      regex: ([^:]+)(?::\d+)?;(\d+)
      replacement: $1:$2
      target_label: __address__
    - action: labelmap
      regex: __meta_kubernetes_pod_label_(.+)
    - source_labels: [__meta_kubernetes_namespace]
      action: replace
      target_label: kubernetes_namespace
    - source_labels: [__meta_kubernetes_pod_name]
      action: replace
      target_label: kubernetes_pod_name

  # MangakAI Backend
  - job_name: 'mangakai-backend'
    kubernetes_sd_configs:
    - role: endpoints
      namespaces:
        names:
        - mangakai-prod
    relabel_configs:
    - source_labels: [__meta_kubernetes_service_name]
      action: keep
      regex: mangakai-backend-service
    - source_labels: [__meta_kubernetes_endpoint_port_name]
      action: keep
      regex: metrics
    scrape_interval: 30s
    metrics_path: /metrics

  # Redis
  - job_name: 'redis'
    static_configs:
    - targets: ['mangakai-redis-service:9121']
    scrape_interval: 30s

  # PostgreSQL
  - job_name: 'postgres'
    static_configs:
    - targets: ['postgres-exporter:9187']
    scrape_interval: 30s

  # Nginx
  - job_name: 'nginx'
    static_configs:
    - targets: ['mangakai-nginx-service:9113']
    scrape_interval: 30s

  # Node Exporter
  - job_name: 'node-exporter'
    kubernetes_sd_configs:
    - role: endpoints
    relabel_configs:
    - source_labels: [__meta_kubernetes_endpoints_name]
      regex: 'node-exporter'
      action: keep
```

### 2.2 告警规则配置

```yaml
# config/prometheus/rules/mangakai-alerts.yml
groups:
- name: mangakai.rules
  interval: 30s
  rules:
  
  # 应用层告警
  - alert: HighErrorRate
    expr: |
      (
        rate(http_requests_total{job="mangakai-backend",status=~"5.."}[5m]) /
        rate(http_requests_total{job="mangakai-backend"}[5m])
      ) > 0.05
    for: 2m
    labels:
      severity: critical
      service: mangakai-backend
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value | humanizePercentage }} for the last 5 minutes"
      runbook_url: "https://wiki.mangakai.com/runbooks/high-error-rate"

  - alert: HighResponseTime
    expr: |
      histogram_quantile(0.95, 
        rate(http_request_duration_seconds_bucket{job="mangakai-backend"}[5m])
      ) > 2
    for: 5m
    labels:
      severity: warning
      service: mangakai-backend
    annotations:
      summary: "High response time detected"
      description: "95th percentile response time is {{ $value }}s"
      runbook_url: "https://wiki.mangakai.com/runbooks/high-response-time"

  - alert: CeleryTaskFailureRate
    expr: |
      (
        rate(celery_task_total{status="FAILURE"}[5m]) /
        rate(celery_task_total[5m])
      ) > 0.1
    for: 3m
    labels:
      severity: warning
      service: celery
    annotations:
      summary: "High Celery task failure rate"
      description: "Task failure rate is {{ $value | humanizePercentage }}"

  - alert: CeleryQueueLength
    expr: celery_queue_length > 100
    for: 5m
    labels:
      severity: warning
      service: celery
    annotations:
      summary: "Celery queue is growing"
      description: "Queue length is {{ $value }} tasks"

  # 基础设施告警
  - alert: PodCrashLooping
    expr: |
      rate(kube_pod_container_status_restarts_total{namespace="mangakai-prod"}[15m]) > 0
    for: 5m
    labels:
      severity: critical
      service: kubernetes
    annotations:
      summary: "Pod is crash looping"
      description: "Pod {{ $labels.pod }} in namespace {{ $labels.namespace }} is crash looping"

  - alert: PodNotReady
    expr: |
      kube_pod_status_ready{condition="false",namespace="mangakai-prod"} == 1
    for: 10m
    labels:
      severity: warning
      service: kubernetes
    annotations:
      summary: "Pod not ready"
      description: "Pod {{ $labels.pod }} has been not ready for more than 10 minutes"

  - alert: HighMemoryUsage
    expr: |
      (
        container_memory_usage_bytes{namespace="mangakai-prod"} /
        container_spec_memory_limit_bytes{namespace="mangakai-prod"}
      ) > 0.9
    for: 5m
    labels:
      severity: warning
      service: kubernetes
    annotations:
      summary: "High memory usage"
      description: "Container {{ $labels.container }} memory usage is {{ $value | humanizePercentage }}"

  - alert: HighCPUUsage
    expr: |
      (
        rate(container_cpu_usage_seconds_total{namespace="mangakai-prod"}[5m]) /
        container_spec_cpu_quota{namespace="mangakai-prod"} * 
        container_spec_cpu_period{namespace="mangakai-prod"}
      ) > 0.8
    for: 10m
    labels:
      severity: warning
      service: kubernetes
    annotations:
      summary: "High CPU usage"
      description: "Container {{ $labels.container }} CPU usage is {{ $value | humanizePercentage }}"

  # 数据库告警
  - alert: PostgreSQLDown
    expr: pg_up == 0
    for: 1m
    labels:
      severity: critical
      service: postgresql
    annotations:
      summary: "PostgreSQL is down"
      description: "PostgreSQL instance is down"

  - alert: PostgreSQLTooManyConnections
    expr: |
      pg_stat_database_numbackends / pg_settings_max_connections > 0.8
    for: 5m
    labels:
      severity: warning
      service: postgresql
    annotations:
      summary: "PostgreSQL too many connections"
      description: "PostgreSQL has {{ $value | humanizePercentage }} connections"

  - alert: RedisDown
    expr: redis_up == 0
    for: 1m
    labels:
      severity: critical
      service: redis
    annotations:
      summary: "Redis is down"
      description: "Redis instance is down"

  - alert: RedisHighMemoryUsage
    expr: |
      redis_memory_used_bytes / redis_memory_max_bytes > 0.9
    for: 5m
    labels:
      severity: warning
      service: redis
    annotations:
      summary: "Redis high memory usage"
      description: "Redis memory usage is {{ $value | humanizePercentage }}"

  # 业务指标告警
  - alert: LowMangaGenerationRate
    expr: |
      rate(manga_generation_total{status="success"}[1h]) < 10
    for: 30m
    labels:
      severity: warning
      service: business
    annotations:
      summary: "Low manga generation rate"
      description: "Manga generation rate is {{ $value }} per hour"

  - alert: HighMangaGenerationFailureRate
    expr: |
      (
        rate(manga_generation_total{status="failure"}[1h]) /
        rate(manga_generation_total[1h])
      ) > 0.2
    for: 15m
    labels:
      severity: critical
      service: business
    annotations:
      summary: "High manga generation failure rate"
      description: "Failure rate is {{ $value | humanizePercentage }}"
```

### 2.3 AlertManager 配置

```yaml
# config/alertmanager/alertmanager.yml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@mangakai.com'
  smtp_auth_username: 'alerts@mangakai.com'
  smtp_auth_password: 'your-app-password'

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'default'
  routes:
  - match:
      severity: critical
    receiver: 'critical-alerts'
    group_wait: 5s
    repeat_interval: 30m
  - match:
      severity: warning
    receiver: 'warning-alerts'
    repeat_interval: 2h

receivers:
- name: 'default'
  email_configs:
  - to: 'team@mangakai.com'
    subject: '[MangakAI] {{ .GroupLabels.alertname }}'
    body: |
      {{ range .Alerts }}
      Alert: {{ .Annotations.summary }}
      Description: {{ .Annotations.description }}
      Labels: {{ range .Labels.SortedPairs }}{{ .Name }}={{ .Value }} {{ end }}
      {{ end }}

- name: 'critical-alerts'
  email_configs:
  - to: 'oncall@mangakai.com'
    subject: '[CRITICAL] MangakAI Alert: {{ .GroupLabels.alertname }}'
    body: |
      🚨 CRITICAL ALERT 🚨
      
      {{ range .Alerts }}
      Alert: {{ .Annotations.summary }}
      Description: {{ .Annotations.description }}
      Runbook: {{ .Annotations.runbook_url }}
      Labels: {{ range .Labels.SortedPairs }}{{ .Name }}={{ .Value }} {{ end }}
      {{ end }}
  
  slack_configs:
  - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
    channel: '#alerts-critical'
    title: 'Critical Alert: {{ .GroupLabels.alertname }}'
    text: |
      {{ range .Alerts }}
      {{ .Annotations.summary }}
      {{ .Annotations.description }}
      {{ end }}

- name: 'warning-alerts'
  email_configs:
  - to: 'team@mangakai.com'
    subject: '[WARNING] MangakAI Alert: {{ .GroupLabels.alertname }}'
    body: |
      ⚠️ WARNING ALERT ⚠️
      
      {{ range .Alerts }}
      Alert: {{ .Annotations.summary }}
      Description: {{ .Annotations.description }}
      {{ end }}

inhibit_rules:
- source_match:
    severity: 'critical'
  target_match:
    severity: 'warning'
  equal: ['alertname', 'cluster', 'service']
```

## 3. Grafana 仪表板

### 3.1 应用性能仪表板

```json
{
  "dashboard": {
    "id": null,
    "title": "MangakAI Application Performance",
    "tags": ["mangakai", "application"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{job=\"mangakai-backend\"}[5m])",
            "legendFormat": "{{method}} {{status}}"
          }
        ],
        "yAxes": [
          {
            "label": "Requests/sec",
            "min": 0
          }
        ],
        "xAxis": {
          "show": true
        },
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 0,
          "y": 0
        }
      },
      {
        "id": 2,
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job=\"mangakai-backend\"}[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{job=\"mangakai-backend\"}[5m]))",
            "legendFormat": "50th percentile"
          }
        ],
        "yAxes": [
          {
            "label": "Seconds",
            "min": 0
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 12,
          "y": 0
        }
      },
      {
        "id": 3,
        "title": "Error Rate",
        "type": "singlestat",
        "targets": [
          {
            "expr": "rate(http_requests_total{job=\"mangakai-backend\",status=~\"5..\"}[5m]) / rate(http_requests_total{job=\"mangakai-backend\"}[5m])",
            "legendFormat": "Error Rate"
          }
        ],
        "valueName": "current",
        "format": "percentunit",
        "thresholds": "0.01,0.05",
        "colorBackground": true,
        "gridPos": {
          "h": 4,
          "w": 6,
          "x": 0,
          "y": 8
        }
      },
      {
        "id": 4,
        "title": "Active Tasks",
        "type": "singlestat",
        "targets": [
          {
            "expr": "celery_active_tasks",
            "legendFormat": "Active Tasks"
          }
        ],
        "valueName": "current",
        "format": "short",
        "gridPos": {
          "h": 4,
          "w": 6,
          "x": 6,
          "y": 8
        }
      },
      {
        "id": 5,
        "title": "Queue Length",
        "type": "graph",
        "targets": [
          {
            "expr": "celery_queue_length",
            "legendFormat": "{{queue}}"
          }
        ],
        "yAxes": [
          {
            "label": "Tasks",
            "min": 0
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 12,
          "y": 8
        }
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
```

### 3.2 基础设施监控仪表板

```json
{
  "dashboard": {
    "id": null,
    "title": "MangakAI Infrastructure",
    "tags": ["mangakai", "infrastructure"],
    "panels": [
      {
        "id": 1,
        "title": "CPU Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(container_cpu_usage_seconds_total{namespace=\"mangakai-prod\"}[5m]) * 100",
            "legendFormat": "{{pod}}"
          }
        ],
        "yAxes": [
          {
            "label": "CPU %",
            "min": 0,
            "max": 100
          }
        ]
      },
      {
        "id": 2,
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "container_memory_usage_bytes{namespace=\"mangakai-prod\"} / 1024 / 1024",
            "legendFormat": "{{pod}}"
          }
        ],
        "yAxes": [
          {
            "label": "Memory (MB)",
            "min": 0
          }
        ]
      },
      {
        "id": 3,
        "title": "Network I/O",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(container_network_receive_bytes_total{namespace=\"mangakai-prod\"}[5m])",
            "legendFormat": "{{pod}} - RX"
          },
          {
            "expr": "rate(container_network_transmit_bytes_total{namespace=\"mangakai-prod\"}[5m])",
            "legendFormat": "{{pod}} - TX"
          }
        ]
      }
    ]
  }
}
```

## 4. 日志管理

### 4.1 ELK Stack 配置

```yaml
# config/elasticsearch/elasticsearch.yml
cluster.name: mangakai-logs
node.name: elasticsearch-master
network.host: 0.0.0.0
discovery.type: single-node
xpack.security.enabled: false
xpack.monitoring.collection.enabled: true

# JVM 设置
-Xms2g
-Xmx2g
```

```yaml
# config/logstash/logstash.conf
input {
  beats {
    port => 5044
  }
}

filter {
  if [fields][service] == "mangakai-backend" {
    grok {
      match => { 
        "message" => "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{DATA:logger} %{GREEDYDATA:message}" 
      }
    }
    
    date {
      match => [ "timestamp", "ISO8601" ]
    }
    
    if [level] == "ERROR" {
      mutate {
        add_tag => [ "error" ]
      }
    }
  }
  
  if [fields][service] == "nginx" {
    grok {
      match => { 
        "message" => "%{NGINXACCESS}" 
      }
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "mangakai-logs-%{+YYYY.MM.dd}"
  }
  
  if "error" in [tags] {
    email {
      to => "team@mangakai.com"
      subject => "Error in MangakAI Application"
      body => "Error detected: %{message}"
    }
  }
}
```

```yaml
# config/filebeat/filebeat.yml
filebeat.inputs:
- type: container
  paths:
    - '/var/lib/docker/containers/*/*.log'
  processors:
  - add_kubernetes_metadata:
      host: ${NODE_NAME}
      matchers:
      - logs_path:
          logs_path: "/var/lib/docker/containers/"

- type: log
  paths:
    - /var/log/mangakai/*.log
  fields:
    service: mangakai-backend
  fields_under_root: true
  multiline.pattern: '^\d{4}-\d{2}-\d{2}'
  multiline.negate: true
  multiline.match: after

output.logstash:
  hosts: ["logstash:5044"]

processors:
- add_host_metadata:
    when.not.contains.tags: forwarded
- add_docker_metadata: ~
- add_kubernetes_metadata: ~
```

### 4.2 Kibana 仪表板配置

```json
{
  "version": "7.15.0",
  "objects": [
    {
      "id": "mangakai-logs-dashboard",
      "type": "dashboard",
      "attributes": {
        "title": "MangakAI Logs Dashboard",
        "panelsJSON": "[{\"version\":\"7.15.0\",\"panelIndex\":\"1\",\"gridData\":{\"x\":0,\"y\":0,\"w\":24,\"h\":15},\"panelRefName\":\"panel_1\",\"embeddableConfig\":{\"title\":\"Log Levels Over Time\"}}]",
        "timeRestore": true,
        "timeTo": "now",
        "timeFrom": "now-24h"
      }
    }
  ]
}
```

## 5. 链路追踪

### 5.1 Jaeger 配置

```yaml
# config/jaeger/jaeger.yml
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: mangakai-jaeger
  namespace: mangakai-prod
spec:
  strategy: production
  storage:
    type: elasticsearch
    elasticsearch:
      nodeCount: 3
      storage:
        size: 100Gi
      resources:
        requests:
          memory: "2Gi"
          cpu: "1000m"
        limits:
          memory: "4Gi"
          cpu: "2000m"
  collector:
    replicas: 2
    resources:
      requests:
        memory: "512Mi"
        cpu: "500m"
      limits:
        memory: "1Gi"
        cpu: "1000m"
  query:
    replicas: 2
    resources:
      requests:
        memory: "256Mi"
        cpu: "250m"
      limits:
        memory: "512Mi"
        cpu: "500m"
```

### 5.2 应用集成

```python
# tracing/jaeger_config.py
from jaeger_client import Config
from opentracing.ext import tags
import opentracing

def init_jaeger_tracer(service_name='mangakai-backend'):
    """初始化 Jaeger 追踪器"""
    config = Config(
        config={
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
            'reporter_batch_size': 1,
        },
        service_name=service_name,
        validate=True,
    )
    
    return config.initialize_tracer()

# 在应用启动时初始化
tracer = init_jaeger_tracer()
opentracing.set_global_tracer(tracer)

# 装饰器用于自动追踪
def trace_function(operation_name=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            with tracer.start_span(op_name) as span:
                span.set_tag(tags.COMPONENT, 'mangakai-backend')
                try:
                    result = func(*args, **kwargs)
                    span.set_tag(tags.HTTP_STATUS_CODE, 200)
                    return result
                except Exception as e:
                    span.set_tag(tags.ERROR, True)
                    span.log_kv({'error.message': str(e)})
                    raise
        return wrapper
    return decorator
```

## 6. 错误追踪

### 6.1 Sentry 配置

```python
# config/sentry_config.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

def init_sentry():
    sentry_sdk.init(
        dsn="https://your-dsn@sentry.io/project-id",
        integrations=[
            FastApiIntegration(auto_enabling_integrations=False),
            SqlalchemyIntegration(),
            RedisIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,
        environment="production",
        release="mangakai@1.0.0",
        before_send=filter_sensitive_data,
    )

def filter_sensitive_data(event, hint):
    """过滤敏感数据"""
    if 'request' in event:
        if 'headers' in event['request']:
            # 移除敏感头信息
            sensitive_headers = ['authorization', 'cookie', 'x-api-key']
            for header in sensitive_headers:
                event['request']['headers'].pop(header, None)
    
    return event
```

## 7. 性能监控

### 7.1 应用性能指标

```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time
import functools

# 定义指标
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'websocket_connections_active',
    'Active WebSocket connections'
)

CELERY_TASK_COUNT = Counter(
    'celery_task_total',
    'Total Celery tasks',
    ['task_name', 'status']
)

CELERY_TASK_DURATION = Histogram(
    'celery_task_duration_seconds',
    'Celery task duration',
    ['task_name']
)

MANGA_GENERATION_COUNT = Counter(
    'manga_generation_total',
    'Total manga generations',
    ['status']
)

ACTIVE_TASKS = Gauge(
    'celery_active_tasks',
    'Number of active Celery tasks'
)

QUEUE_LENGTH = Gauge(
    'celery_queue_length',
    'Celery queue length',
    ['queue']
)

def track_request_metrics(func):
    """装饰器：追踪请求指标"""
    @functools.wraps(func)
    async def wrapper(request, *args, **kwargs):
        start_time = time.time()
        method = request.method
        endpoint = request.url.path
        
        try:
            response = await func(request, *args, **kwargs)
            status = response.status_code
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            return response
        except Exception as e:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=500).inc()
            raise
        finally:
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(
                time.time() - start_time
            )
    
    return wrapper

def track_celery_metrics(func):
    """装饰器：追踪 Celery 任务指标"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        task_name = func.__name__
        start_time = time.time()
        
        ACTIVE_TASKS.inc()
        
        try:
            result = func(*args, **kwargs)
            CELERY_TASK_COUNT.labels(task_name=task_name, status='SUCCESS').inc()
            return result
        except Exception as e:
            CELERY_TASK_COUNT.labels(task_name=task_name, status='FAILURE').inc()
            raise
        finally:
            ACTIVE_TASKS.dec()
            CELERY_TASK_DURATION.labels(task_name=task_name).observe(
                time.time() - start_time
            )
    
    return wrapper

# 启动指标服务器
def start_metrics_server(port=8001):
    start_http_server(port)
    print(f"Metrics server started on port {port}")
```

## 8. 健康检查

### 8.1 应用健康检查

```python
# health/health_checks.py
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from redis import Redis
import asyncio
import time

router = APIRouter()

class HealthChecker:
    def __init__(self, db_session, redis_client):
        self.db_session = db_session
        self.redis_client = redis_client
    
    async def check_database(self):
        """检查数据库连接"""
        try:
            result = await self.db_session.execute(text("SELECT 1"))
            return {"status": "healthy", "response_time": 0.001}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def check_redis(self):
        """检查 Redis 连接"""
        try:
            start_time = time.time()
            await self.redis_client.ping()
            response_time = time.time() - start_time
            return {"status": "healthy", "response_time": response_time}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def check_external_apis(self):
        """检查外部 API"""
        checks = {}
        
        # 检查 Gemini API
        try:
            # 这里添加实际的 API 检查逻辑
            checks["gemini_api"] = {"status": "healthy"}
        except Exception as e:
            checks["gemini_api"] = {"status": "unhealthy", "error": str(e)}
        
        # 检查 S3
        try:
            # 这里添加 S3 连接检查
            checks["s3"] = {"status": "healthy"}
        except Exception as e:
            checks["s3"] = {"status": "unhealthy", "error": str(e)}
        
        return checks

@router.get("/health")
async def health_check():
    """基本健康检查"""
    return {"status": "healthy", "timestamp": time.time()}

@router.get("/ready")
async def readiness_check():
    """就绪检查"""
    checker = HealthChecker(db_session, redis_client)
    
    checks = {
        "database": await checker.check_database(),
        "redis": await checker.check_redis(),
    }
    
    # 检查所有依赖是否健康
    all_healthy = all(check["status"] == "healthy" for check in checks.values())
    
    if all_healthy:
        return {"status": "ready", "checks": checks}
    else:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})

@router.get("/live")
async def liveness_check():
    """存活检查"""
    return {"status": "alive", "timestamp": time.time()}
```

## 9. 运维脚本

### 9.1 部署脚本

```bash
#!/bin/bash
# scripts/deploy-monitoring.sh

set -e

NAMESPACE="mangakai-prod"
MONITORING_NAMESPACE="monitoring"

echo "Deploying monitoring stack..."

# 创建监控命名空间
kubectl create namespace ${MONITORING_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# 部署 Prometheus
echo "Deploying Prometheus..."
kubectl apply -f k8s/monitoring/prometheus/ -n ${MONITORING_NAMESPACE}

# 部署 Grafana
echo "Deploying Grafana..."
kubectl apply -f k8s/monitoring/grafana/ -n ${MONITORING_NAMESPACE}

# 部署 AlertManager
echo "Deploying AlertManager..."
kubectl apply -f k8s/monitoring/alertmanager/ -n ${MONITORING_NAMESPACE}

# 部署 Jaeger
echo "Deploying Jaeger..."
kubectl apply -f k8s/monitoring/jaeger/ -n ${MONITORING_NAMESPACE}

# 等待部署完成
echo "Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/prometheus -n ${MONITORING_NAMESPACE}
kubectl wait --for=condition=available --timeout=300s deployment/grafana -n ${MONITORING_NAMESPACE}
kubectl wait --for=condition=available --timeout=300s deployment/alertmanager -n ${MONITORING_NAMESPACE}

echo "Monitoring stack deployed successfully!"

# 获取访问地址
echo "Access URLs:"
echo "Prometheus: http://$(kubectl get svc prometheus -n ${MONITORING_NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'):9090"
echo "Grafana: http://$(kubectl get svc grafana -n ${MONITORING_NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'):3000"
echo "AlertManager: http://$(kubectl get svc alertmanager -n ${MONITORING_NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'):9093"
```

### 9.2 备份脚本

```bash
#!/bin/bash
# scripts/backup-monitoring.sh

set -e

BACKUP_DIR="/backup/monitoring/$(date +%Y%m%d_%H%M%S)"
NAMESPACE="monitoring"

echo "Creating monitoring backup..."

mkdir -p ${BACKUP_DIR}

# 备份 Prometheus 数据
echo "Backing up Prometheus data..."
kubectl exec -n ${NAMESPACE} prometheus-0 -- tar czf - /prometheus | cat > ${BACKUP_DIR}/prometheus-data.tar.gz

# 备份 Grafana 配置
echo "Backing up Grafana configuration..."
kubectl get configmaps -n ${NAMESPACE} -o yaml > ${BACKUP_DIR}/grafana-configmaps.yaml
kubectl get secrets -n ${NAMESPACE} -o yaml > ${BACKUP_DIR}/grafana-secrets.yaml

# 备份告警规则
echo "Backing up alert rules..."
kubectl get prometheusrules -n ${NAMESPACE} -o yaml > ${BACKUP_DIR}/prometheus-rules.yaml

# 创建备份清单
echo "Creating backup manifest..."
cat > ${BACKUP_DIR}/backup-info.txt << EOF
Backup created: $(date)
Namespace: ${NAMESPACE}
Prometheus version: $(kubectl get deployment prometheus -n ${NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].image}')
Grafana version: $(kubectl get deployment grafana -n ${NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].image}')
EOF

echo "Backup completed: ${BACKUP_DIR}"
```

### 9.3 故障排查脚本

```bash
#!/bin/bash
# scripts/troubleshoot.sh

set -e

NAMESPACE="mangakai-prod"

echo "MangakAI Troubleshooting Script"
echo "================================"

# 检查 Pod 状态
echo "1. Checking Pod status..."
kubectl get pods -n ${NAMESPACE} -o wide

# 检查服务状态
echo -e "\n2. Checking Service status..."
kubectl get services -n ${NAMESPACE}

# 检查 Ingress 状态
echo -e "\n3. Checking Ingress status..."
kubectl get ingress -n ${NAMESPACE}

# 检查最近的事件
echo -e "\n4. Recent events..."
kubectl get events -n ${NAMESPACE} --sort-by='.lastTimestamp' | tail -10

# 检查资源使用情况
echo -e "\n5. Resource usage..."
kubectl top pods -n ${NAMESPACE}

# 检查失败的 Pod 日志
echo -e "\n6. Checking failed pods..."
FAILED_PODS=$(kubectl get pods -n ${NAMESPACE} --field-selector=status.phase!=Running -o jsonpath='{.items[*].metadata.name}')

if [ ! -z "$FAILED_PODS" ]; then
    for pod in $FAILED_PODS; do
        echo -e "\nLogs for failed pod: $pod"
        kubectl logs $pod -n ${NAMESPACE} --tail=50
    done
else
    echo "No failed pods found."
fi

# 检查数据库连接
echo -e "\n7. Checking database connectivity..."
kubectl exec -n ${NAMESPACE} deployment/mangakai-backend -- python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    print('Database connection: OK')
    conn.close()
except Exception as e:
    print(f'Database connection: FAILED - {e}')
"

# 检查 Redis 连接
echo -e "\n8. Checking Redis connectivity..."
kubectl exec -n ${NAMESPACE} deployment/mangakai-backend -- python -c "
import redis
import os
try:
    r = redis.from_url(os.environ['REDIS_URL'])
    r.ping()
    print('Redis connection: OK')
except Exception as e:
    print(f'Redis connection: FAILED - {e}')
"

echo -e "\nTroubleshooting completed."
```

这个监控和运维指南提供了完整的监控解决方案，包括指标收集、日志管理、链路追踪、错误监控和自动化运维脚本，确保 MangakAI 系统的稳定运行和快速故障定位。
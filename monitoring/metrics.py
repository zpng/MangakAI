"""
Prometheus metrics for MangakAI monitoring
"""
import time
import functools
import logging
from prometheus_client import Counter, Histogram, Gauge, start_http_server, CollectorRegistry, REGISTRY
import os

logger = logging.getLogger(__name__)

# Create custom registry for better control
CUSTOM_REGISTRY = CollectorRegistry()

# HTTP Request Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=CUSTOM_REGISTRY
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=CUSTOM_REGISTRY
)

# Celery Task Metrics
CELERY_TASK_COUNT = Counter(
    'celery_task_total',
    'Total Celery tasks',
    ['task_name', 'status'],
    registry=CUSTOM_REGISTRY
)

CELERY_TASK_DURATION = Histogram(
    'celery_task_duration_seconds',
    'Celery task duration in seconds',
    ['task_name'],
    registry=CUSTOM_REGISTRY
)

ACTIVE_TASKS = Gauge(
    'celery_active_tasks',
    'Number of active Celery tasks',
    registry=CUSTOM_REGISTRY
)

QUEUE_LENGTH = Gauge(
    'celery_queue_length',
    'Celery queue length',
    ['queue'],
    registry=CUSTOM_REGISTRY
)

# WebSocket Metrics
WEBSOCKET_CONNECTIONS = Gauge(
    'websocket_connections_active',
    'Active WebSocket connections',
    registry=CUSTOM_REGISTRY
)

WEBSOCKET_MESSAGES = Counter(
    'websocket_messages_total',
    'Total WebSocket messages',
    ['type', 'direction'],  # direction: sent/received
    registry=CUSTOM_REGISTRY
)

# Business Metrics
MANGA_GENERATION_COUNT = Counter(
    'manga_generation_total',
    'Total manga generations',
    ['status'],  # success, failure
    registry=CUSTOM_REGISTRY
)

MANGA_GENERATION_DURATION = Histogram(
    'manga_generation_duration_seconds',
    'Manga generation duration in seconds',
    registry=CUSTOM_REGISTRY
)

PANEL_GENERATION_COUNT = Counter(
    'panel_generation_total',
    'Total panel generations',
    ['status'],
    registry=CUSTOM_REGISTRY
)

# System Metrics
DATABASE_CONNECTIONS = Gauge(
    'database_connections_active',
    'Active database connections',
    registry=CUSTOM_REGISTRY
)

REDIS_CONNECTIONS = Gauge(
    'redis_connections_active',
    'Active Redis connections',
    registry=CUSTOM_REGISTRY
)

# Storage Metrics
STORAGE_OPERATIONS = Counter(
    'storage_operations_total',
    'Total storage operations',
    ['operation', 'status'],  # operation: upload/download/delete, status: success/failure
    registry=CUSTOM_REGISTRY
)

STORAGE_SIZE = Gauge(
    'storage_size_bytes',
    'Storage size in bytes',
    ['type'],  # type: local/s3/total
    registry=CUSTOM_REGISTRY
)

def track_request_metrics(func):
    """
    Decorator to track HTTP request metrics
    """
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
    """
    Decorator to track Celery task metrics
    """
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

def track_manga_generation(func):
    """
    Decorator to track manga generation metrics
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            MANGA_GENERATION_COUNT.labels(status='success').inc()
            return result
        except Exception as e:
            MANGA_GENERATION_COUNT.labels(status='failure').inc()
            raise
        finally:
            MANGA_GENERATION_DURATION.observe(time.time() - start_time)
    
    return wrapper

def track_panel_generation(func):
    """
    Decorator to track panel generation metrics
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            PANEL_GENERATION_COUNT.labels(status='success').inc()
            return result
        except Exception as e:
            PANEL_GENERATION_COUNT.labels(status='failure').inc()
            raise
    
    return wrapper

def track_storage_operation(operation: str):
    """
    Decorator to track storage operations
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                STORAGE_OPERATIONS.labels(operation=operation, status='success').inc()
                return result
            except Exception as e:
                STORAGE_OPERATIONS.labels(operation=operation, status='failure').inc()
                raise
        return wrapper
    return decorator

def update_websocket_connections(count: int):
    """
    Update WebSocket connections count
    """
    WEBSOCKET_CONNECTIONS.set(count)

def track_websocket_message(message_type: str, direction: str):
    """
    Track WebSocket message
    """
    WEBSOCKET_MESSAGES.labels(type=message_type, direction=direction).inc()

def update_database_connections(count: int):
    """
    Update database connections count
    """
    DATABASE_CONNECTIONS.set(count)

def update_redis_connections(count: int):
    """
    Update Redis connections count
    """
    REDIS_CONNECTIONS.set(count)

def update_queue_length(queue_name: str, length: int):
    """
    Update queue length
    """
    QUEUE_LENGTH.labels(queue=queue_name).set(length)

def update_storage_size(storage_type: str, size_bytes: int):
    """
    Update storage size
    """
    STORAGE_SIZE.labels(type=storage_type).set(size_bytes)

class MetricsCollector:
    """
    Metrics collector for periodic system metrics
    """
    
    def __init__(self):
        self.enabled = os.getenv('PROMETHEUS_ENABLED', 'true').lower() == 'true'
    
    def collect_system_metrics(self):
        """
        Collect system-level metrics
        """
        if not self.enabled:
            return
        
        try:
            # Collect database metrics
            self._collect_database_metrics()
            
            # Collect Redis metrics
            self._collect_redis_metrics()
            
            # Collect storage metrics
            self._collect_storage_metrics()
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {str(e)}")
    
    def _collect_database_metrics(self):
        """
        Collect database connection metrics
        """
        try:
            from database import engine
            pool = engine.pool
            
            # Update connection pool metrics
            update_database_connections(pool.checkedout())
            
        except Exception as e:
            logger.warning(f"Failed to collect database metrics: {str(e)}")
    
    def _collect_redis_metrics(self):
        """
        Collect Redis connection metrics
        """
        try:
            import redis
            from celery_app import celery_app
            
            # Get Redis connection info
            redis_url = celery_app.conf.broker_url
            r = redis.from_url(redis_url)
            info = r.info()
            
            # Update Redis metrics
            update_redis_connections(info.get('connected_clients', 0))
            
        except Exception as e:
            logger.warning(f"Failed to collect Redis metrics: {str(e)}")
    
    def _collect_storage_metrics(self):
        """
        Collect storage metrics
        """
        try:
            import os
            from storage.cloud_storage import storage_manager
            
            # Calculate local storage size
            if hasattr(storage_manager, 'local_storage_path'):
                local_size = self._get_directory_size(storage_manager.local_storage_path)
                update_storage_size('local', local_size)
            
        except Exception as e:
            logger.warning(f"Failed to collect storage metrics: {str(e)}")
    
    def _get_directory_size(self, path: str) -> int:
        """
        Get total size of directory in bytes
        """
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception as e:
            logger.warning(f"Error calculating directory size for {path}: {str(e)}")
        
        return total_size

# Global metrics collector instance
metrics_collector = MetricsCollector()

def start_metrics_server(port: int = None):
    """
    Start Prometheus metrics server
    """
    if not port:
        port = int(os.getenv('METRICS_PORT', 8001))
    
    try:
        start_http_server(port, registry=CUSTOM_REGISTRY)
        logger.info(f"Metrics server started on port {port}")
        return True
    except Exception as e:
        logger.error(f"Failed to start metrics server: {str(e)}")
        return False

def get_metrics_summary():
    """
    Get current metrics summary for debugging
    """
    try:
        from prometheus_client import generate_latest
        return generate_latest(CUSTOM_REGISTRY).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to generate metrics summary: {str(e)}")
        return None
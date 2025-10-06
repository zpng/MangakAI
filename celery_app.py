"""
Celery application configuration for MangakAI
"""
from celery import Celery
from kombu import Queue
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Celery application instance
celery_app = Celery('mangakai')

# Configuration
celery_app.conf.update(
    # Message broker
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    
    # Task serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'tasks.generate_manga_task': {'queue': 'manga_generation'},
        'tasks.regenerate_panel_task': {'queue': 'panel_regeneration'},
        'tasks.cleanup_old_tasks': {'queue': 'maintenance'},
    },
    
    # Queue definitions
    task_default_queue='default',
    task_queues=(
        Queue('manga_generation', routing_key='manga_generation'),
        Queue('panel_regeneration', routing_key='panel_regeneration'),
        Queue('maintenance', routing_key='maintenance'),
    ),
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Task timeout settings
    task_soft_time_limit=300,  # 5 minutes soft timeout
    task_time_limit=600,       # 10 minutes hard timeout
    
    # Retry configuration
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Result expiration
    result_expires=3600,  # 1 hour
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'cleanup-old-tasks': {
            'task': 'tasks.cleanup_old_tasks',
            'schedule': 3600.0,  # Run every hour
        },
        'cleanup-old-sessions': {
            'task': 'tasks.cleanup_old_sessions',
            'schedule': 86400.0,  # Run daily
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(['tasks'])

if __name__ == '__main__':
    celery_app.start()
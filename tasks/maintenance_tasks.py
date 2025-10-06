"""
Maintenance tasks for MangakAI
"""
import logging
from datetime import datetime, timedelta
from celery_app import celery_app
from models.manga_models import MangaTask, MangaPanel, UserSession, TaskStatus
from database import get_db_session

logger = logging.getLogger(__name__)

@celery_app.task(name='tasks.cleanup_old_tasks')
def cleanup_old_tasks():
    """
    Clean up old completed or failed tasks
    """
    try:
        with get_db_session() as db:
            # Delete tasks older than 7 days
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            # Find old tasks
            old_tasks = db.query(MangaTask).filter(
                MangaTask.created_at < cutoff_date,
                MangaTask.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
            ).all()
            
            deleted_count = 0
            for task in old_tasks:
                # Delete associated panels first (cascade should handle this, but being explicit)
                db.query(MangaPanel).filter(MangaPanel.task_id == task.id).delete()
                
                # Delete the task
                db.delete(task)
                deleted_count += 1
            
            db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old tasks")
            return f"Cleaned up {deleted_count} old tasks"
            
    except Exception as e:
        logger.error(f"Error cleaning up old tasks: {str(e)}")
        raise

@celery_app.task(name='tasks.cleanup_old_sessions')
def cleanup_old_sessions():
    """
    Clean up old user sessions
    """
    try:
        with get_db_session() as db:
            # Delete sessions older than 30 days
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            deleted_count = db.query(UserSession).filter(
                UserSession.last_activity < cutoff_date
            ).delete()
            
            db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old sessions")
            return f"Cleaned up {deleted_count} old sessions"
            
    except Exception as e:
        logger.error(f"Error cleaning up old sessions: {str(e)}")
        raise

@celery_app.task(name='tasks.cleanup_failed_tasks')
def cleanup_failed_tasks():
    """
    Clean up tasks that have been in processing state for too long
    """
    try:
        with get_db_session() as db:
            # Mark tasks as failed if they've been processing for more than 1 hour
            cutoff_date = datetime.utcnow() - timedelta(hours=1)
            
            stuck_tasks = db.query(MangaTask).filter(
                MangaTask.status.in_([TaskStatus.PROCESSING, TaskStatus.IMAGE_GENERATION, TaskStatus.SCENE_GENERATION]),
                MangaTask.updated_at < cutoff_date
            ).all()
            
            updated_count = 0
            for task in stuck_tasks:
                task.status = TaskStatus.FAILED
                task.error_message = "Task timed out"
                updated_count += 1
            
            db.commit()
            
            logger.info(f"Marked {updated_count} stuck tasks as failed")
            return f"Marked {updated_count} stuck tasks as failed"
            
    except Exception as e:
        logger.error(f"Error cleaning up failed tasks: {str(e)}")
        raise

@celery_app.task(name='tasks.generate_task_statistics')
def generate_task_statistics():
    """
    Generate statistics about task processing
    """
    try:
        with get_db_session() as db:
            # Count tasks by status
            stats = {}
            
            for status in [TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.COMPLETED, TaskStatus.FAILED]:
                count = db.query(MangaTask).filter(MangaTask.status == status).count()
                stats[status] = count
            
            # Count tasks created in the last 24 hours
            last_24h = datetime.utcnow() - timedelta(hours=24)
            recent_tasks = db.query(MangaTask).filter(MangaTask.created_at >= last_24h).count()
            stats['recent_tasks_24h'] = recent_tasks
            
            # Count total panels generated
            total_panels = db.query(MangaPanel).count()
            stats['total_panels'] = total_panels
            
            logger.info(f"Task statistics: {stats}")
            return stats
            
    except Exception as e:
        logger.error(f"Error generating task statistics: {str(e)}")
        raise
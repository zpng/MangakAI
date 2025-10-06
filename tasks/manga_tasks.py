"""
Celery tasks for manga generation
"""
import os
import time
import traceback
import logging
from sqlalchemy import text
from celery import current_task
from celery_app import celery_app
from models.manga_models import MangaTask, MangaPanel, TaskStatus, PanelStatus
from database import get_db_session
from manga import MangaGenerator
from websocket_manager import ConnectionManager
from storage.cloud_storage import upload_to_cloud_storage
from utils import get_regeneration_prompt

logger = logging.getLogger(__name__)
connection_manager = ConnectionManager()

@celery_app.task(bind=True, name='tasks.generate_manga_task')
def generate_manga_task(self, task_id: str, story_text: str, parameters: dict):
    """
    Asynchronous manga generation task
    """
    with get_db_session() as db:
        try:
            # Get task record
            task = db.query(MangaTask).filter(MangaTask.id == task_id).first()
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Update task status
            task.status = TaskStatus.PROCESSING
            task.current_panel = 0
            db.commit()
            
            # Send progress update
            send_progress_update(task.user_session_id, {
                'task_id': task_id,
                'status': TaskStatus.PROCESSING,
                'progress': 0,
                'message': '开始生成漫画...'
            })
            
            # Initialize generator
            generator = MangaGenerator()
            
            # Step 1: Generate scene descriptions
            task.status = TaskStatus.SCENE_GENERATION
            db.commit()
            
            send_progress_update(task.user_session_id, {
                'task_id': task_id,
                'status': TaskStatus.SCENE_GENERATION,
                'progress': 10,
                'message': '正在分析故事并生成场景描述...'
            })
            
            scenes = generator.split_into_scenes(story_text, task.total_panels)
            
            # Create panel records
            for i, scene in enumerate(scenes):
                panel = MangaPanel(
                    task_id=task.id,
                    panel_number=i + 1,
                    scene_description=scene,
                    status=PanelStatus.PENDING
                )
                db.add(panel)
            db.commit()
            
            # Step 2: Generate images
            task.status = TaskStatus.IMAGE_GENERATION
            db.commit()
            
            generated_panels = []
            
            # Create chat session for consistency
            chat = generator.image_gen_client.chats.create(model=generator.image_gen_model_name)
            
            for i, scene in enumerate(scenes):
                try:
                    # Update current panel
                    task.current_panel = i + 1
                    progress = 20 + (i / len(scenes)) * 70  # 20-90% for image generation
                    task.progress = int(progress)
                    db.commit()
                    
                    send_progress_update(task.user_session_id, {
                        'task_id': task_id,
                        'status': TaskStatus.IMAGE_GENERATION,
                        'progress': int(progress),
                        'message': f'正在生成第 {i+1}/{len(scenes)} 个面板...',
                        'current_panel': i + 1,
                        'total_panels': len(scenes)
                    })
                    
                    # Generate image with user preferences
                    user_preferences = parameters or {}
                    enhanced_prompt = generator.enhance_scene_with_preferences(scene, user_preferences)
                    
                    # Generate image
                    output_path = f"/tmp/panel_{task_id}_{i+1}.png"
                    response, saved_image = generator.generate_image_with_chat(
                        enhanced_prompt, output_path, chat
                    )
                    
                    # Upload to cloud storage
                    cloud_url = upload_to_cloud_storage(
                        output_path, 
                        f"tasks/{task_id}/panel_{i+1}.webp"
                    )
                    
                    # Update panel record
                    panel = db.query(MangaPanel).filter(
                        MangaPanel.task_id == task.id,
                        MangaPanel.panel_number == i + 1
                    ).first()
                    
                    panel.image_url = cloud_url
                    panel.image_path = output_path
                    panel.status = PanelStatus.COMPLETED
                    db.commit()
                    
                    generated_panels.append({
                        'panel_number': i + 1,
                        'scene_description': scene,
                        'image_url': cloud_url
                    })
                    
                    # Clean up temporary file
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    
                except Exception as e:
                    logger.error(f"Error generating panel {i+1}: {str(e)}")
                    
                    # Update panel status to failed
                    panel = db.query(MangaPanel).filter(
                        MangaPanel.task_id == task.id,
                        MangaPanel.panel_number == i + 1
                    ).first()
                    if panel:
                        panel.status = PanelStatus.FAILED
                        db.commit()
                    
                    # Continue with next panel
                    continue
            
            # Step 3: Complete task
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.completed_at = db.execute(text("SELECT CURRENT_TIMESTAMP")).scalar()
            db.commit()
            
            send_progress_update(task.user_session_id, {
                'task_id': task_id,
                'status': TaskStatus.COMPLETED,
                'progress': 100,
                'message': '漫画生成完成！',
                'panels': generated_panels
            })
            
            return {
                'task_id': task_id,
                'status': TaskStatus.COMPLETED,
                'panels': generated_panels
            }
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Update task status to failed
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
            
            send_progress_update(task.user_session_id, {
                'task_id': task_id,
                'status': TaskStatus.FAILED,
                'progress': 0,
                'message': f'生成失败: {str(e)}'
            })
            
            raise

@celery_app.task(bind=True, name='tasks.regenerate_panel_task')
def regenerate_panel_task(self, task_id: str, panel_number: int, modification_request: str, reference_image_path: str = None):
    """
    Asynchronous panel regeneration task
    """
    with get_db_session() as db:
        try:
            # Get task and panel
            task = db.query(MangaTask).filter(MangaTask.id == task_id).first()
            panel = db.query(MangaPanel).filter(
                MangaPanel.task_id == task_id,
                MangaPanel.panel_number == panel_number
            ).first()
            
            if not task or not panel:
                raise ValueError("Task or panel not found")
            
            # Update panel status
            panel.status = PanelStatus.REGENERATING
            db.commit()
            
            send_progress_update(task.user_session_id, {
                'task_id': task_id,
                'status': 'REGENERATING',
                'panel_number': panel_number,
                'message': f'正在重新生成第 {panel_number} 个面板...'
            })
            
            # Initialize generator and create chat session
            generator = MangaGenerator()
            chat = generator.image_gen_client.chats.create(model=generator.image_gen_model_name)
            
            # Create modified prompt
            user_preferences = task.parameters or {}
            modified_scene = get_regeneration_prompt(
                panel.scene_description,
                modification_request,
                is_first_panel=(panel_number == 1),
                user_preferences=user_preferences
            )
            
            # Generate new image
            output_path = f"/tmp/panel_{task_id}_{panel_number}_v{panel.version + 1}.png"
            
            # Use reference image if provided
            if reference_image_path and os.path.exists(reference_image_path):
                response, saved_image = generator.generate_image_with_chat_and_reference(
                    modified_scene, output_path, chat, reference_image_path
                )
            else:
                response, saved_image = generator.generate_image_with_chat(
                    modified_scene, output_path, chat
                )
            
            # Upload to cloud storage
            cloud_url = upload_to_cloud_storage(
                output_path, 
                f"tasks/{task_id}/panel_{panel_number}_v{panel.version + 1}.webp"
            )
            
            # Update panel record
            panel.image_url = cloud_url
            panel.image_path = output_path
            panel.version += 1
            panel.status = PanelStatus.COMPLETED
            db.commit()
            
            send_progress_update(task.user_session_id, {
                'task_id': task_id,
                'status': 'PANEL_REGENERATED',
                'panel_number': panel_number,
                'image_url': cloud_url,
                'message': f'第 {panel_number} 个面板重新生成完成！'
            })
            
            # Clean up temporary file
            if os.path.exists(output_path):
                os.remove(output_path)
            
            return {
                'panel_number': panel_number,
                'image_url': cloud_url,
                'version': panel.version
            }
            
        except Exception as e:
            logger.error(f"Panel regeneration failed: {str(e)}")
            
            if panel:
                panel.status = PanelStatus.FAILED
                db.commit()
            
            send_progress_update(task.user_session_id, {
                'task_id': task_id,
                'status': 'REGENERATION_FAILED',
                'panel_number': panel_number,
                'message': f'面板重新生成失败: {str(e)}'
            })
            
            raise

def send_progress_update(session_id: str, data: dict):
    """
    Send progress update to frontend via WebSocket
    """
    try:
        connection_manager.send_progress_update_sync(session_id, data)
    except Exception as e:
        logger.warning(f"Failed to send progress update: {str(e)}")

# Helper function to enhance scene with user preferences
def enhance_scene_with_preferences(generator, scene: str, preferences: dict) -> str:
    """
    Enhance scene description with user preferences
    """
    enhanced_prompt = scene
    
    if preferences.get('art_style'):
        enhanced_prompt += f"\n\nArt style: {preferences['art_style']}"
    
    if preferences.get('mood'):
        enhanced_prompt += f"\nMood: {preferences['mood']}"
    
    if preferences.get('color_palette'):
        enhanced_prompt += f"\nColor palette: {preferences['color_palette']}"
    
    if preferences.get('character_style'):
        enhanced_prompt += f"\nCharacter style: {preferences['character_style']}"
    
    if preferences.get('line_style'):
        enhanced_prompt += f"\nLine style: {preferences['line_style']}"
    
    if preferences.get('composition'):
        enhanced_prompt += f"\nComposition: {preferences['composition']}"
    
    if preferences.get('additional_notes'):
        enhanced_prompt += f"\n\nAdditional notes: {preferences['additional_notes']}"
    
    return enhanced_prompt

# Add method to MangaGenerator class
MangaGenerator.enhance_scene_with_preferences = enhance_scene_with_preferences
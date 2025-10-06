"""
Async manga generation API endpoints
"""
import uuid
import logging
import os
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import get_db
from models.manga_models import MangaTask, MangaPanel, UserSession, TaskStatus
from tasks.manga_tasks import generate_manga_task, regenerate_panel_task
from utils import generate_session_id
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PIL import Image

router = APIRouter(prefix="/api/async", tags=["异步漫画生成"])
logger = logging.getLogger(__name__)

# Request/Response models
class CreateTaskRequest(BaseModel):
    story_text: str
    session_id: str
    num_scenes: int = 5
    art_style: Optional[str] = None
    mood: Optional[str] = None
    color_palette: Optional[str] = None
    character_style: Optional[str] = None
    line_style: Optional[str] = None
    composition: Optional[str] = None
    additional_notes: str = ""

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    current_panel: int
    total_panels: int
    panels: List[dict] = []
    error_message: Optional[str] = None
    created_at: str
    updated_at: str

class RegeneratePanelRequest(BaseModel):
    modification_request: str

class PDFResponse(BaseModel):
    success: bool
    message: str
    pdf_path: Optional[str] = None

def get_or_create_session(session_id: str, db: Session) -> UserSession:
    """
    Get or create user session
    """
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        session = UserSession(id=session_id)
        db.add(session)
        db.commit()
        db.refresh(session)
    else:
        # Update last activity
        session.last_activity = db.execute(text("SELECT CURRENT_TIMESTAMP")).scalar()
        db.commit()
    
    return session

@router.post("/generate-manga", response_model=TaskResponse)
async def create_manga_generation_task(
    request: CreateTaskRequest,
    db: Session = Depends(get_db)
):
    """
    Create an asynchronous manga generation task
    """
    try:
        # Get session_id from request body
        session_id = request.session_id
        if not session_id:
            session_id = generate_session_id()
        
        # Get or create user session
        user_session = get_or_create_session(session_id, db)
        
        # Create task record
        task = MangaTask(
            user_session_id=session_id,
            story_text=request.story_text,
            total_panels=request.num_scenes,
            parameters={
                "art_style": request.art_style,
                "mood": request.mood,
                "color_palette": request.color_palette,
                "character_style": request.character_style,
                "line_style": request.line_style,
                "composition": request.composition,
                "additional_notes": request.additional_notes
            }
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # Start async task
        generate_manga_task.delay(
            str(task.id),
            request.story_text,
            task.parameters
        )
        
        logger.info(f"Created manga generation task {task.id} for session {session_id}")
        
        return TaskResponse(
            task_id=str(task.id),
            status=TaskStatus.PENDING,
            message="任务已创建，正在处理中..."
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create manga generation task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")

@router.post("/generate-manga-from-file", response_model=TaskResponse)
async def create_manga_generation_task_from_file(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    num_scenes: int = Form(5),
    art_style: Optional[str] = Form(None),
    mood: Optional[str] = Form(None),
    color_palette: Optional[str] = Form(None),
    character_style: Optional[str] = Form(None),
    line_style: Optional[str] = Form(None),
    composition: Optional[str] = Form(None),
    additional_notes: str = Form(""),
    db: Session = Depends(get_db)
):
    """
    Create manga generation task from uploaded file
    """
    try:
        # Validate file type
        if not file.filename.endswith('.txt'):
            raise HTTPException(status_code=400, detail="只支持 .txt 文件")
        
        # Read file content
        content = await file.read()
        story_text = content.decode('utf-8')
        
        if not story_text.strip():
            raise HTTPException(status_code=400, detail="文件内容不能为空")
        
        # Create request object
        request = CreateTaskRequest(
            story_text=story_text,
            session_id=session_id,
            num_scenes=num_scenes,
            art_style=art_style,
            mood=mood,
            color_palette=color_palette,
            character_style=character_style,
            line_style=line_style,
            composition=composition,
            additional_notes=additional_notes
        )
        
        # Use the existing endpoint logic
        return await create_manga_generation_task(request, db)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create task from file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理文件失败: {str(e)}")

@router.get("/task/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """
    Get task status and progress
    """
    try:
        task = db.query(MangaTask).filter(MangaTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # Get panel information
        panels = db.query(MangaPanel).filter(
            MangaPanel.task_id == task.id
        ).order_by(MangaPanel.panel_number).all()
        
        panels_data = []
        for panel in panels:
            panels_data.append({
                "panel_number": panel.panel_number,
                "scene_description": panel.scene_description,
                "image_url": panel.image_url,
                "status": panel.status,
                "version": panel.version
            })
        
        return TaskStatusResponse(
            task_id=str(task.id),
            status=task.status,
            progress=task.progress,
            current_panel=task.current_panel,
            total_panels=task.total_panels,
            panels=panels_data,
            error_message=task.error_message,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")

@router.post("/task/{task_id}/regenerate-panel/{panel_number}")
async def regenerate_panel(
    task_id: str,
    panel_number: int,
    modification_request: str = Form(...),
    replace_original: bool = Form(False),
    reference_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Regenerate a specific panel
    """
    try:
        # Validate task exists
        task = db.query(MangaTask).filter(MangaTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # Find the original panel (only non-regenerated panels can be selected for regeneration)
        original_panel = db.query(MangaPanel).filter(
            MangaPanel.task_id == task_id,
            MangaPanel.panel_number == panel_number,
            MangaPanel.is_regenerated == False
        ).first()
        if not original_panel:
            raise HTTPException(status_code=404, detail="原始面板不存在")
        
        # Handle reference image if provided
        reference_image_path = None
        if reference_image:
            # Save reference image temporarily
            import tempfile
            import shutil
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                shutil.copyfileobj(reference_image.file, tmp_file)
                reference_image_path = tmp_file.name
        
        # Create new panel record for regenerated version
        new_panel = MangaPanel(
            task_id=task_id,
            panel_number=panel_number,
            scene_description=original_panel.scene_description,
            original_panel_id=original_panel.id,
            regeneration_request=modification_request,
            is_regenerated=True,
            status='PENDING',
            version=1
        )
        db.add(new_panel)
        db.commit()
        db.refresh(new_panel)
        
        # Start regeneration task with the new panel ID
        regenerate_panel_task.delay(
            new_panel.id,  # Use new panel ID instead of task_id + panel_number
            modification_request,
            reference_image_path
        )
        
        logger.info(f"Started panel regeneration for task {task_id}, panel {panel_number}, new panel ID: {new_panel.id}")
        
        return {"message": f"面板 {panel_number} 重新生成任务已启动", "regenerated_panel_id": new_panel.id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start panel regeneration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动重新生成任务失败: {str(e)}")

@router.get("/tasks")
async def get_user_tasks(
    session_id: str,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get user's task list
    """
    try:
        tasks = db.query(MangaTask).filter(
            MangaTask.user_session_id == session_id
        ).order_by(
            MangaTask.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        tasks_data = []
        for task in tasks:
            tasks_data.append({
                "task_id": str(task.id),
                "status": task.status,
                "progress": task.progress,
                "total_panels": task.total_panels,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "story_preview": task.story_text[:100] + "..." if len(task.story_text) > 100 else task.story_text
            })
        
        return {"tasks": tasks_data}
    
    except Exception as e:
        logger.error(f"Failed to get user tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")

@router.delete("/task/{task_id}")
async def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """
    Cancel a task (if it's still pending or processing)
    """
    try:
        task = db.query(MangaTask).filter(MangaTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            raise HTTPException(status_code=400, detail="任务已完成，无法取消")
        
        # Update task status
        task.status = TaskStatus.CANCELLED
        task.error_message = "用户取消"
        db.commit()
        
        logger.info(f"Cancelled task {task_id}")
        
        return {"message": "任务已取消"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")

@router.post("/task/{task_id}/create-pdf", response_model=PDFResponse)
async def create_pdf_from_task(task_id: str, db: Session = Depends(get_db)):
    """
    Create PDF from specific task panels
    """
    try:
        # Get task and its panels
        task = db.query(MangaTask).filter(MangaTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task.status != TaskStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="只有已完成的任务才能创建PDF")
        
        # Get panels for this task
        panels = db.query(MangaPanel).filter(
            MangaPanel.task_id == task_id
        ).order_by(MangaPanel.panel_number).all()
        
        logger.info(f"Found {len(panels)} panels for task {task_id}")
        for panel in panels:
            logger.info(f"Panel {panel.panel_number}: image_path={panel.image_path}, exists={os.path.exists(panel.image_path) if panel.image_path else False}")
        
        if not panels:
            return PDFResponse(
                success=False,
                message="该任务没有可用的面板",
                pdf_path=None
            )
        
        # Create PDF
        output_dir = "data/output"
        os.makedirs(output_dir, exist_ok=True)
        pdf_filename = f"manga_task_{task_id}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)
        
        # Create PDF with panels
        c = canvas.Canvas(pdf_path, pagesize=A4)
        page_width, page_height = A4
        
        # Add title page
        c.setFont("Helvetica-Bold", 24)
        title_text = "Manga Story"
        text_width = c.stringWidth(title_text, "Helvetica-Bold", 24)
        c.drawString((page_width - text_width) / 2, page_height - 100, title_text)
        
        c.setFont("Helvetica", 12)
        generated_text = f"Generated on: {task.created_at.strftime('%Y-%m-%d %H:%M')}"
        text_width = c.stringWidth(generated_text, "Helvetica", 12)
        c.drawString((page_width - text_width) / 2, page_height - 150, generated_text)
        
        task_id_text = f"Task ID: {task_id}"
        text_width = c.stringWidth(task_id_text, "Helvetica", 12)
        c.drawString((page_width - text_width) / 2, page_height - 170, task_id_text)
        c.showPage()
        
        # Add each panel as a page
        panels_added = 0
        for panel in panels:
            logger.info(f"Processing panel {panel.panel_number}, image_url: {panel.image_url}")
            
            # Try to find the actual image file
            image_source = None
            
            # First, try to use image_url (cloud storage path)
            if panel.image_url:
                if panel.image_url.startswith('/static/'):
                    # Convert static URL to local file path
                    local_path = panel.image_url.replace('/static/', 'data/')
                    if os.path.exists(local_path):
                        image_source = local_path
                        logger.info(f"Using local file from static URL: {local_path}")
                    else:
                        logger.warning(f"Local file not found for static URL: {local_path}")
                elif panel.image_url.startswith('http'):
                    # This is a remote URL, we would need to download it
                    logger.info(f"Panel {panel.panel_number} has remote URL: {panel.image_url}")
                else:
                    # Try as direct file path
                    if os.path.exists(panel.image_url):
                        image_source = panel.image_url
                        logger.info(f"Using direct path from image_url: {panel.image_url}")
            
            # Fallback to image_path if available
            if not image_source and panel.image_path and os.path.exists(panel.image_path):
                image_source = panel.image_path
                logger.info(f"Using image_path: {panel.image_path}")
            
            if image_source:
                try:
                    logger.info(f"Adding panel {panel.panel_number} to PDF from: {image_source}")
                    # Open and process image
                    img = Image.open(image_source)
                    
                    # Calculate dimensions to fit page while maintaining aspect ratio
                    img_width, img_height = img.size
                    aspect_ratio = img_width / img_height
                    
                    # Set maximum dimensions (with margins)
                    max_width = page_width - 100  # 50px margin on each side
                    max_height = page_height - 150  # 75px margin top/bottom
                    
                    if aspect_ratio > max_width / max_height:
                        # Image is wider, fit to width
                        display_width = max_width
                        display_height = max_width / aspect_ratio
                    else:
                        # Image is taller, fit to height
                        display_height = max_height
                        display_width = max_height * aspect_ratio
                    
                    # Center the image on the page
                    x = (page_width - display_width) / 2
                    y = (page_height - display_height) / 2
                    
                    # Draw the image
                    c.drawImage(image_source, x, y, width=display_width, height=display_height)
                    
                    # Add panel number at the bottom
                    c.setFont("Helvetica", 10)
                    panel_text = f"Panel {panel.panel_number}"
                    text_width = c.stringWidth(panel_text, "Helvetica", 10)
                    c.drawString((page_width - text_width) / 2, 30, panel_text)
                    
                    c.showPage()
                    panels_added += 1
                    
                except Exception as e:
                    logger.error(f"Error processing panel {panel.panel_number}: {str(e)}")
                    continue
            else:
                logger.warning(f"Panel {panel.panel_number} has no accessible image source. image_url: {panel.image_url}, image_path: {panel.image_path}")
        
        logger.info(f"Added {panels_added} panels to PDF")
        
        c.save()
        
        # Convert to API path
        relative_path = os.path.relpath(pdf_path, "data")
        api_pdf_path = f"/static/{relative_path}"
        
        return PDFResponse(
            success=True,
            message=f"PDF创建成功！({panels_added} 个面板)",
            pdf_path=api_pdf_path
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create PDF from task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建PDF失败: {str(e)}")

@router.get("/health")
async def async_api_health():
    """
    Health check for async API
    """
    return {
        "status": "healthy",
        "service": "async_manga_api"
    }
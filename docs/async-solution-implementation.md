# 异步处理解决方案实现指南

## 1. 概述

本文档详细描述了 MangakAI 异步处理系统的实现方案，包括任务队列、状态管理、实时通信等核心组件的具体实现。

## 2. 技术栈选择

### 2.1 核心组件
- **任务队列**: Celery 5.3+
- **消息代理**: Redis 7.0+
- **数据库**: PostgreSQL 15+
- **实时通信**: WebSocket (FastAPI WebSocket)
- **缓存**: Redis (复用消息代理)

### 2.2 依赖包
```toml
# pyproject.toml 新增依赖
[project.dependencies]
celery = "^5.3.0"
redis = "^5.0.0"
psycopg2-binary = "^2.9.0"
sqlalchemy = "^2.0.0"
alembic = "^1.12.0"
websockets = "^12.0"
```

## 3. 数据库设计

### 3.1 数据库迁移文件

```python
# alembic/versions/001_create_async_tables.py
"""Create async processing tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 任务表
    op.create_table('manga_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_session_id', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('story_text', sa.Text, nullable=False),
        sa.Column('parameters', postgresql.JSONB, nullable=True),
        sa.Column('progress', sa.Integer, server_default='0'),
        sa.Column('total_panels', sa.Integer, server_default='5'),
        sa.Column('current_panel', sa.Integer, server_default='0'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.func.current_timestamp()),
        sa.Column('completed_at', sa.TIMESTAMP, nullable=True),
    )
    
    # 面板表
    op.create_table('manga_panels',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('panel_number', sa.Integer, nullable=False),
        sa.Column('scene_description', sa.Text, nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('image_path', sa.String(500), nullable=True),
        sa.Column('version', sa.Integer, server_default='1'),
        sa.Column('status', sa.String(50), server_default='PENDING'),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['task_id'], ['manga_tasks.id'], ondelete='CASCADE'),
    )
    
    # 用户会话表
    op.create_table('user_sessions',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.current_timestamp()),
        sa.Column('last_activity', sa.TIMESTAMP, server_default=sa.func.current_timestamp()),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )
    
    # 创建索引
    op.create_index('idx_manga_tasks_session_id', 'manga_tasks', ['user_session_id'])
    op.create_index('idx_manga_tasks_status', 'manga_tasks', ['status'])
    op.create_index('idx_manga_tasks_created_at', 'manga_tasks', ['created_at'])
    op.create_index('idx_manga_panels_task_id', 'manga_panels', ['task_id'])
    op.create_index('idx_user_sessions_last_activity', 'user_sessions', ['last_activity'])

def downgrade() -> None:
    op.drop_table('manga_panels')
    op.drop_table('manga_tasks')
    op.drop_table('user_sessions')
```

### 3.2 SQLAlchemy 模型

```python
# models/async_models.py
from sqlalchemy import Column, String, Text, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class MangaTask(Base):
    __tablename__ = 'manga_tasks'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_session_id = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, default='PENDING', index=True)
    story_text = Column(Text, nullable=False)
    parameters = Column(JSONB, nullable=True)
    progress = Column(Integer, default=0)
    total_panels = Column(Integer, default=5)
    current_panel = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    completed_at = Column(TIMESTAMP, nullable=True)
    
    # 关系
    panels = relationship("MangaPanel", back_populates="task", cascade="all, delete-orphan")

class MangaPanel(Base):
    __tablename__ = 'manga_panels'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey('manga_tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    panel_number = Column(Integer, nullable=False)
    scene_description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    image_path = Column(String(500), nullable=True)
    version = Column(Integer, default=1)
    status = Column(String(50), default='PENDING')
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # 关系
    task = relationship("MangaTask", back_populates="panels")

class UserSession(Base):
    __tablename__ = 'user_sessions'
    
    id = Column(String(255), primary_key=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    last_activity = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    metadata = Column(JSONB, nullable=True)
```

## 4. Celery 配置

### 4.1 Celery 应用配置

```python
# celery_app.py
from celery import Celery
from kombu import Queue
import os

# Celery 应用实例
celery_app = Celery('mangakai')

# 配置
celery_app.conf.update(
    # 消息代理
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    
    # 任务序列化
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # 任务路由
    task_routes={
        'tasks.generate_manga': {'queue': 'manga_generation'},
        'tasks.regenerate_panel': {'queue': 'panel_regeneration'},
        'tasks.cleanup_old_tasks': {'queue': 'maintenance'},
    },
    
    # 队列定义
    task_default_queue='default',
    task_queues=(
        Queue('manga_generation', routing_key='manga_generation'),
        Queue('panel_regeneration', routing_key='panel_regeneration'),
        Queue('maintenance', routing_key='maintenance'),
    ),
    
    # 工作进程配置
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # 任务超时
    task_soft_time_limit=300,  # 5分钟软超时
    task_time_limit=600,       # 10分钟硬超时
    
    # 重试配置
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # 结果过期时间
    result_expires=3600,  # 1小时
)

# 自动发现任务
celery_app.autodiscover_tasks(['tasks'])
```

### 4.2 任务定义

```python
# tasks/manga_tasks.py
from celery import current_task
from celery_app import celery_app
from models.async_models import MangaTask, MangaPanel
from database import get_db_session
from manga import MangaGenerator
from storage import upload_to_s3
from websocket_manager import ConnectionManager
import logging
import traceback

logger = logging.getLogger(__name__)
connection_manager = ConnectionManager()

@celery_app.task(bind=True, name='tasks.generate_manga')
def generate_manga_task(self, task_id: str, story_text: str, parameters: dict):
    """异步生成漫画任务"""
    db = get_db_session()
    
    try:
        # 获取任务记录
        task = db.query(MangaTask).filter(MangaTask.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # 更新任务状态
        task.status = 'PROCESSING'
        task.current_panel = 0
        db.commit()
        
        # 发送进度更新
        await send_progress_update(task.user_session_id, {
            'task_id': task_id,
            'status': 'PROCESSING',
            'progress': 0,
            'message': '开始生成漫画...'
        })
        
        # 初始化生成器
        generator = MangaGenerator()
        
        # 第一步：生成场景描述
        task.status = 'SCENE_GENERATION'
        db.commit()
        
        await send_progress_update(task.user_session_id, {
            'task_id': task_id,
            'status': 'SCENE_GENERATION',
            'progress': 10,
            'message': '正在分析故事并生成场景描述...'
        })
        
        scenes = generator.split_into_scenes(story_text, task.total_panels)
        
        # 创建面板记录
        for i, scene in enumerate(scenes):
            panel = MangaPanel(
                task_id=task.id,
                panel_number=i + 1,
                scene_description=scene,
                status='PENDING'
            )
            db.add(panel)
        db.commit()
        
        # 第二步：生成图片
        task.status = 'IMAGE_GENERATION'
        db.commit()
        
        generated_panels = []
        
        for i, scene in enumerate(scenes):
            try:
                # 更新当前面板
                task.current_panel = i + 1
                progress = 20 + (i / len(scenes)) * 70  # 20-90% 用于图片生成
                task.progress = int(progress)
                db.commit()
                
                await send_progress_update(task.user_session_id, {
                    'task_id': task_id,
                    'status': 'IMAGE_GENERATION',
                    'progress': int(progress),
                    'message': f'正在生成第 {i+1}/{len(scenes)} 个面板...',
                    'current_panel': i + 1,
                    'total_panels': len(scenes)
                })
                
                # 生成图片
                output_path = f"/tmp/panel_{task_id}_{i+1}.png"
                response, saved_image = generator.generate_image_for_scene(scene, output_path)
                
                # 上传到云存储
                s3_url = upload_to_s3(output_path, f"tasks/{task_id}/panel_{i+1}.webp")
                
                # 更新面板记录
                panel = db.query(MangaPanel).filter(
                    MangaPanel.task_id == task.id,
                    MangaPanel.panel_number == i + 1
                ).first()
                
                panel.image_url = s3_url
                panel.image_path = output_path
                panel.status = 'COMPLETED'
                db.commit()
                
                generated_panels.append({
                    'panel_number': i + 1,
                    'scene_description': scene,
                    'image_url': s3_url
                })
                
                # 清理临时文件
                os.remove(output_path)
                
            except Exception as e:
                logger.error(f"Error generating panel {i+1}: {str(e)}")
                # 更新面板状态为失败
                panel = db.query(MangaPanel).filter(
                    MangaPanel.task_id == task.id,
                    MangaPanel.panel_number == i + 1
                ).first()
                panel.status = 'FAILED'
                db.commit()
                
                # 继续处理下一个面板
                continue
        
        # 第三步：完成任务
        task.status = 'COMPLETED'
        task.progress = 100
        task.completed_at = func.current_timestamp()
        db.commit()
        
        await send_progress_update(task.user_session_id, {
            'task_id': task_id,
            'status': 'COMPLETED',
            'progress': 100,
            'message': '漫画生成完成！',
            'panels': generated_panels
        })
        
        return {
            'task_id': task_id,
            'status': 'COMPLETED',
            'panels': generated_panels
        }
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        # 更新任务状态为失败
        task.status = 'FAILED'
        task.error_message = str(e)
        db.commit()
        
        await send_progress_update(task.user_session_id, {
            'task_id': task_id,
            'status': 'FAILED',
            'progress': 0,
            'message': f'生成失败: {str(e)}'
        })
        
        raise
    
    finally:
        db.close()

@celery_app.task(bind=True, name='tasks.regenerate_panel')
def regenerate_panel_task(self, task_id: str, panel_number: int, modification_request: str):
    """异步重新生成面板任务"""
    db = get_db_session()
    
    try:
        # 获取任务和面板
        task = db.query(MangaTask).filter(MangaTask.id == task_id).first()
        panel = db.query(MangaPanel).filter(
            MangaPanel.task_id == task_id,
            MangaPanel.panel_number == panel_number
        ).first()
        
        if not task or not panel:
            raise ValueError("Task or panel not found")
        
        # 更新面板状态
        panel.status = 'REGENERATING'
        db.commit()
        
        await send_progress_update(task.user_session_id, {
            'task_id': task_id,
            'status': 'REGENERATING',
            'panel_number': panel_number,
            'message': f'正在重新生成第 {panel_number} 个面板...'
        })
        
        # 重新生成
        generator = MangaGenerator()
        modified_scene = f"{panel.scene_description}\n\n修改要求: {modification_request}"
        
        output_path = f"/tmp/panel_{task_id}_{panel_number}_v{panel.version + 1}.png"
        response, saved_image = generator.generate_image_for_scene(modified_scene, output_path)
        
        # 上传到云存储
        s3_url = upload_to_s3(output_path, f"tasks/{task_id}/panel_{panel_number}_v{panel.version + 1}.webp")
        
        # 更新面板记录
        panel.image_url = s3_url
        panel.image_path = output_path
        panel.version += 1
        panel.status = 'COMPLETED'
        db.commit()
        
        await send_progress_update(task.user_session_id, {
            'task_id': task_id,
            'status': 'PANEL_REGENERATED',
            'panel_number': panel_number,
            'image_url': s3_url,
            'message': f'第 {panel_number} 个面板重新生成完成！'
        })
        
        # 清理临时文件
        os.remove(output_path)
        
        return {
            'panel_number': panel_number,
            'image_url': s3_url,
            'version': panel.version
        }
        
    except Exception as e:
        logger.error(f"Panel regeneration failed: {str(e)}")
        
        panel.status = 'FAILED'
        db.commit()
        
        await send_progress_update(task.user_session_id, {
            'task_id': task_id,
            'status': 'REGENERATION_FAILED',
            'panel_number': panel_number,
            'message': f'面板重新生成失败: {str(e)}'
        })
        
        raise
    
    finally:
        db.close()

async def send_progress_update(session_id: str, data: dict):
    """发送进度更新到前端"""
    try:
        await connection_manager.send_progress_update(session_id, data)
    except Exception as e:
        logger.warning(f"Failed to send progress update: {str(e)}")
```

## 5. WebSocket 实时通信

### 5.1 连接管理器

```python
# websocket_manager.py
from fastapi import WebSocket
from typing import Dict, List
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.connection_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """建立 WebSocket 连接"""
        await websocket.accept()
        
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        
        self.active_connections[session_id].append(websocket)
        logger.info(f"WebSocket connected for session {session_id}")
        
        # 启动心跳检测
        task = asyncio.create_task(self._heartbeat(websocket, session_id))
        self.connection_tasks[f"{session_id}_{id(websocket)}"] = task
    
    async def disconnect(self, websocket: WebSocket, session_id: str):
        """断开 WebSocket 连接"""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            
            # 如果没有更多连接，清理会话
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        
        # 取消心跳任务
        task_key = f"{session_id}_{id(websocket)}"
        if task_key in self.connection_tasks:
            self.connection_tasks[task_key].cancel()
            del self.connection_tasks[task_key]
        
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def send_progress_update(self, session_id: str, data: dict):
        """发送进度更新"""
        if session_id not in self.active_connections:
            return
        
        message = {
            "type": "progress_update",
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # 发送给该会话的所有连接
        disconnected = []
        for websocket in self.active_connections[session_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to websocket: {str(e)}")
                disconnected.append(websocket)
        
        # 清理断开的连接
        for websocket in disconnected:
            await self.disconnect(websocket, session_id)
    
    async def send_task_status(self, session_id: str, task_id: str, status: str, **kwargs):
        """发送任务状态更新"""
        data = {
            "task_id": task_id,
            "status": status,
            **kwargs
        }
        await self.send_progress_update(session_id, data)
    
    async def _heartbeat(self, websocket: WebSocket, session_id: str):
        """心跳检测"""
        try:
            while True:
                await asyncio.sleep(30)  # 每30秒发送一次心跳
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time()
                })
        except Exception as e:
            logger.info(f"Heartbeat failed for session {session_id}: {str(e)}")
            await self.disconnect(websocket, session_id)

# 全局连接管理器实例
connection_manager = ConnectionManager()
```

### 5.2 WebSocket 端点

```python
# api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websocket_manager import connection_manager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket 连接端点"""
    await connection_manager.connect(websocket, session_id)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()
            
            # 处理不同类型的消息
            message_type = data.get("type")
            
            if message_type == "ping":
                # 响应 ping
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": data.get("timestamp")
                })
            
            elif message_type == "subscribe_task":
                # 订阅任务状态更新
                task_id = data.get("task_id")
                await websocket.send_json({
                    "type": "subscribed",
                    "task_id": task_id,
                    "message": f"已订阅任务 {task_id} 的状态更新"
                })
            
            elif message_type == "unsubscribe_task":
                # 取消订阅任务状态更新
                task_id = data.get("task_id")
                await websocket.send_json({
                    "type": "unsubscribed",
                    "task_id": task_id,
                    "message": f"已取消订阅任务 {task_id}"
                })
    
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {str(e)}")
        await connection_manager.disconnect(websocket, session_id)
```

## 6. API 端点更新

### 6.1 异步任务 API

```python
# api/async_manga.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from database import get_db
from models.async_models import MangaTask, MangaPanel
from tasks.manga_tasks import generate_manga_task, regenerate_panel_task
from uuid import uuid4
import uuid

router = APIRouter(prefix="/api/async", tags=["异步漫画生成"])

class CreateTaskRequest(BaseModel):
    story_text: str
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

@router.post("/generate-manga", response_model=TaskResponse)
async def create_manga_generation_task(
    request: CreateTaskRequest,
    session_id: str,
    db: Session = Depends(get_db)
):
    """创建异步漫画生成任务"""
    try:
        # 创建任务记录
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
        
        # 启动异步任务
        generate_manga_task.delay(
            str(task.id),
            request.story_text,
            task.parameters
        )
        
        return TaskResponse(
            task_id=str(task.id),
            status="PENDING",
            message="任务已创建，正在处理中..."
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")

@router.get("/task/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """获取任务状态"""
    try:
        task = db.query(MangaTask).filter(MangaTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取面板信息
        panels = db.query(MangaPanel).filter(MangaPanel.task_id == task.id).order_by(MangaPanel.panel_number).all()
        
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
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")

@router.post("/task/{task_id}/regenerate-panel/{panel_number}")
async def regenerate_panel(
    task_id: str,
    panel_number: int,
    modification_request: str,
    db: Session = Depends(get_db)
):
    """重新生成指定面板"""
    try:
        # 验证任务和面板存在
        task = db.query(MangaTask).filter(MangaTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        panel = db.query(MangaPanel).filter(
            MangaPanel.task_id == task_id,
            MangaPanel.panel_number == panel_number
        ).first()
        if not panel:
            raise HTTPException(status_code=404, detail="面板不存在")
        
        # 启动重新生成任务
        regenerate_panel_task.delay(task_id, panel_number, modification_request)
        
        return {"message": f"面板 {panel_number} 重新生成任务已启动"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动重新生成任务失败: {str(e)}")

@router.get("/tasks")
async def get_user_tasks(
    session_id: str,
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """获取用户的任务列表"""
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
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            })
        
        return {"tasks": tasks_data}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")
```

## 7. 前端集成

### 7.1 WebSocket 客户端

```javascript
// frontend/src/services/websocket.js
class WebSocketService {
    constructor() {
        this.ws = null;
        this.sessionId = this.getOrCreateSessionId();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.listeners = new Map();
    }
    
    getOrCreateSessionId() {
        let sessionId = localStorage.getItem('session_id');
        if (!sessionId) {
            sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('session_id', sessionId);
        }
        return sessionId;
    }
    
    connect() {
        const wsUrl = `ws://localhost:8000/ws/${this.sessionId}`;
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.emit('connected');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.emit('disconnected');
            this.attemptReconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.emit('error', error);
        };
    }
    
    handleMessage(data) {
        const { type } = data;
        
        switch (type) {
            case 'progress_update':
                this.emit('progress_update', data.data);
                break;
            case 'heartbeat':
                // 响应心跳
                this.send({ type: 'pong', timestamp: data.timestamp });
                break;
            case 'pong':
                // 处理 pong 响应
                break;
            default:
                this.emit('message', data);
        }
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }
    
    subscribeToTask(taskId) {
        this.send({
            type: 'subscribe_task',
            task_id: taskId
        });
    }
    
    unsubscribeFromTask(taskId) {
        this.send({
            type: 'unsubscribe_task',
            task_id: taskId
        });
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
            
            setTimeout(() => {
                console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                this.connect();
            }, delay);
        }
    }
    
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
    }
    
    off(event, callback) {
        if (this.listeners.has(event)) {
            const callbacks = this.listeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }
    
    emit(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error('Error in event listener:', error);
                }
            });
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

export default new WebSocketService();
```

### 7.2 React 组件集成

```jsx
// frontend/src/components/AsyncMangaGenerator.jsx
import React, { useState, useEffect } from 'react';
import websocketService from '../services/websocket';
import { generateMangaAsync, getTaskStatus } from '../services/api';

const AsyncMangaGenerator = () => {
    const [storyText, setStoryText] = useState('');
    const [currentTask, setCurrentTask] = useState(null);
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState('');
    const [panels, setPanels] = useState([]);
    const [isGenerating, setIsGenerating] = useState(false);
    
    useEffect(() => {
        // 连接 WebSocket
        websocketService.connect();
        
        // 监听进度更新
        websocketService.on('progress_update', handleProgressUpdate);
        
        // 清理
        return () => {
            websocketService.off('progress_update', handleProgressUpdate);
            websocketService.disconnect();
        };
    }, []);
    
    const handleProgressUpdate = (data) => {
        const { task_id, status, progress, message, panels: updatedPanels } = data;
        
        if (currentTask && task_id === currentTask.task_id) {
            setStatus(status);
            setProgress(progress || 0);
            
            if (updatedPanels) {
                setPanels(updatedPanels);
            }
            
            if (status === 'COMPLETED' || status === 'FAILED') {
                setIsGenerating(false);
            }
        }
    };
    
    const handleGenerateManga = async () => {
        if (!storyText.trim()) {
            alert('请输入故事内容');
            return;
        }
        
        try {
            setIsGenerating(true);
            setProgress(0);
            setStatus('PENDING');
            setPanels([]);
            
            // 创建异步任务
            const response = await generateMangaAsync({
                story_text: storyText,
                num_scenes: 5
            });
            
            const task = {
                task_id: response.task_id,
                status: response.status
            };
            
            setCurrentTask(task);
            
            // 订阅任务状态更新
            websocketService.subscribeToTask(task.task_id);
            
            // 定期轮询任务状态（作为 WebSocket 的备用方案）
            const pollInterval = setInterval(async () => {
                try {
                    const statusResponse = await getTaskStatus(task.task_id);
                    
                    if (statusResponse.status === 'COMPLETED' || statusResponse.status === 'FAILED') {
                        clearInterval(pollInterval);
                        setIsGenerating(false);
                        
                        if (statusResponse.status === 'COMPLETED') {
                            setPanels(statusResponse.panels);
                        }
                    }
                } catch (error) {
                    console.error('Error polling task status:', error);
                }
            }, 5000);
            
            // 10分钟后停止轮询
            setTimeout(() => {
                clearInterval(pollInterval);
            }, 600000);
            
        } catch (error) {
            console.error('Error creating task:', error);
            setIsGenerating(false);
            alert('创建任务失败: ' + error.message);
        }
    };
    
    const getStatusMessage = () => {
        switch (status) {
            case 'PENDING':
                return '等待处理...';
            case 'PROCESSING':
                return '开始处理...';
            case 'SCENE_GENERATION':
                return '正在分析故事并生成场景描述...';
            case 'IMAGE_GENERATION':
                return `正在生成图片... (${progress}%)`;
            case 'COMPLETED':
                return '生成完成！';
            case 'FAILED':
                return '生成失败';
            default:
                return '';
        }
    };
    
    return (
        <div className="async-manga-generator">
            <div className="input-section">
                <textarea
                    value={storyText}
                    onChange={(e) => setStoryText(e.target.value)}
                    placeholder="请输入您的故事..."
                    rows={6}
                    disabled={isGenerating}
                />
                
                <button
                    onClick={handleGenerateManga}
                    disabled={isGenerating || !storyText.trim()}
                    className="generate-button"
                >
                    {isGenerating ? '生成中...' : '生成漫画'}
                </button>
            </div>
            
            {isGenerating && (
                <div className="progress-section">
                    <div className="progress-bar">
                        <div
                            className="progress-fill"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                    <div className="status-message">
                        {getStatusMessage()}
                    </div>
                </div>
            )}
            
            {panels.length > 0 && (
                <div className="panels-section">
                    <h3>生成的漫画面板</h3>
                    <div className="panels-grid">
                        {panels.map((panel, index) => (
                            <div key={index} className="panel-item">
                                <img
                                    src={panel.image_url}
                                    alt={`Panel ${panel.panel_number}`}
                                    loading="lazy"
                                />
                                <div className="panel-description">
                                    {panel.scene_description}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default AsyncMangaGenerator;
```

## 8. 部署配置

### 8.1 Docker Compose 配置

```yaml
# docker-compose.async.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: mangakai
      POSTGRES_USER: mangakai
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://mangakai:password@postgres:5432/mangakai
      - REDIS_URL=redis://redis:6379/0
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    depends_on:
      - redis
      - postgres
    volumes:
      - ./data:/app/data
    
  celery-worker:
    build: .
    command: celery -A celery_app worker --loglevel=info --concurrency=2
    environment:
      - DATABASE_URL=postgresql://mangakai:password@postgres:5432/mangakai
      - REDIS_URL=redis://redis:6379/0
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    depends_on:
      - redis
      - postgres
    volumes:
      - ./data:/app/data
    
  celery-beat:
    build: .
    command: celery -A celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://mangakai:password@postgres:5432/mangakai
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - postgres
    
  flower:
    build: .
    command: celery -A celery_app flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

volumes:
  redis_data:
  postgres_data:
```

### 8.2 启动脚本

```bash
#!/bin/bash
# scripts/start-async.sh

echo "Starting MangakAI Async Services..."

# 启动基础服务
docker-compose -f docker-compose.async.yml up -d redis postgres

# 等待数据库启动
echo "Waiting for database to be ready..."
sleep 10

# 运行数据库迁移
docker-compose -f docker-compose.async.yml exec backend alembic upgrade head

# 启动应用服务
docker-compose -f docker-compose.async.yml up -d backend celery-worker celery-beat flower

echo "All services started successfully!"
echo "Backend: http://localhost:8000"
echo "Flower (Celery monitoring): http://localhost:5555"
```

## 9. 监控和调试

### 9.1 Celery 监控

```python
# monitoring/celery_monitor.py
from celery_app import celery_app
from celery.events.state import State
from celery.events import EventReceiver
import logging

logger = logging.getLogger(__name__)

def monitor_celery_events():
    """监控 Celery 事件"""
    state = State()
    
    def on_event(event):
        state.event(event)
        
        # 记录任务事件
        if event['type'].startswith('task-'):
            task_id = event.get('uuid')
            task_name = event.get('name')
            
            if event['type'] == 'task-sent':
                logger.info(f"Task {task_name}[{task_id}] sent")
            elif event['type'] == 'task-started':
                logger.info(f"Task {task_name}[{task_id}] started")
            elif event['type'] == 'task-succeeded':
                logger.info(f"Task {task_name}[{task_id}] succeeded")
            elif event['type'] == 'task-failed':
                logger.error(f"Task {task_name}[{task_id}] failed: {event.get('exception')}")
    
    with celery_app.connection() as connection:
        recv = EventReceiver(connection, handlers={'*': on_event})
        recv.capture(limit=None, timeout=None, wakeup=True)

if __name__ == '__main__':
    monitor_celery_events()
```

### 9.2 性能指标收集

```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# 定义指标
TASK_COUNTER = Counter('celery_tasks_total', 'Total number of Celery tasks', ['task_name', 'status'])
TASK_DURATION = Histogram('celery_task_duration_seconds', 'Task execution time', ['task_name'])
ACTIVE_TASKS = Gauge('celery_active_tasks', 'Number of active tasks')
WEBSOCKET_CONNECTIONS = Gauge('websocket_connections_total', 'Number of active WebSocket connections')

def record_task_start(task_name):
    """记录任务开始"""
    ACTIVE_TASKS.inc()
    return time.time()

def record_task_completion(task_name, start_time, status='success'):
    """记录任务完成"""
    duration = time.time() - start_time
    TASK_DURATION.labels(task_name=task_name).observe(duration)
    TASK_COUNTER.labels(task_name=task_name, status=status).inc()
    ACTIVE_TASKS.dec()

def record_websocket_connection(action='connect'):
    """记录 WebSocket 连接"""
    if action == 'connect':
        WEBSOCKET_CONNECTIONS.inc()
    elif action == 'disconnect':
        WEBSOCKET_CONNECTIONS.dec()

# 启动 Prometheus 指标服务器
def start_metrics_server(port=8001):
    start_http_server(port)
    print(f"Metrics server started on port {port}")
```

这个异步处理解决方案提供了完整的实现指南，包括数据库设计、任务队列配置、WebSocket 实时通信、API 端点和前端集成。通过这个方案，MangakAI 将能够处理长时间运行的漫画生成任务，并为用户提供实时的进度反馈。
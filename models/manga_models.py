"""
Database models for MangakAI async processing
"""
from sqlalchemy import Column, String, Text, Integer, TIMESTAMP, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from database import Base

class MangaTask(Base):
    """
    Manga generation task model
    """
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
    
    # Relationships
    panels = relationship("MangaPanel", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MangaTask(id={self.id}, status={self.status}, progress={self.progress})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': str(self.id),
            'user_session_id': self.user_session_id,
            'status': self.status,
            'story_text': self.story_text,
            'parameters': self.parameters,
            'progress': self.progress,
            'total_panels': self.total_panels,
            'current_panel': self.current_panel,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

class MangaPanel(Base):
    """
    Individual manga panel model
    """
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
    
    # Relationships
    task = relationship("MangaTask", back_populates="panels")
    
    def __repr__(self):
        return f"<MangaPanel(id={self.id}, task_id={self.task_id}, panel_number={self.panel_number})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': str(self.id),
            'task_id': str(self.task_id),
            'panel_number': self.panel_number,
            'scene_description': self.scene_description,
            'image_url': self.image_url,
            'image_path': self.image_path,
            'version': self.version,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class UserSession(Base):
    """
    User session model for tracking user activity
    """
    __tablename__ = 'user_sessions'
    
    id = Column(String(255), primary_key=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    last_activity = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    session_metadata = Column(JSONB, nullable=True)
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, last_activity={self.last_activity})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'session_metadata': self.session_metadata,
        }

# Task status constants
class TaskStatus:
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    SCENE_GENERATION = 'SCENE_GENERATION'
    IMAGE_GENERATION = 'IMAGE_GENERATION'
    PANEL_PROCESSING = 'PANEL_PROCESSING'
    UPLOADING = 'UPLOADING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'

# Panel status constants
class PanelStatus:
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    REGENERATING = 'REGENERATING'
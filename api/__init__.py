"""
API package for MangakAI
"""
from .websocket import router as websocket_router
from .async_manga import router as async_manga_router

__all__ = ["websocket_router", "async_manga_router"]
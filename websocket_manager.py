"""
WebSocket connection manager for real-time communication
"""
import asyncio
import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect
import time
import threading

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication
    """
    
    def __init__(self):
        # Active connections: session_id -> list of websockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        
        # Connection tasks for heartbeat
        self.connection_tasks: Dict[str, asyncio.Task] = {}
        
        # Lock for thread-safe operations
        self._lock = threading.Lock()
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """
        Accept a new WebSocket connection
        """
        await websocket.accept()
        
        with self._lock:
            if session_id not in self.active_connections:
                self.active_connections[session_id] = []
            
            self.active_connections[session_id].append(websocket)
        
        logger.info(f"WebSocket connected for session {session_id}")
        
        # Start heartbeat task
        task_key = f"{session_id}_{id(websocket)}"
        task = asyncio.create_task(self._heartbeat(websocket, session_id))
        self.connection_tasks[task_key] = task
        
        # Send welcome message
        await self.send_personal_message({
            "type": "connection_established",
            "session_id": session_id,
            "timestamp": time.time()
        }, websocket)
    
    async def disconnect(self, websocket: WebSocket, session_id: str):
        """
        Remove a WebSocket connection
        """
        with self._lock:
            if session_id in self.active_connections:
                if websocket in self.active_connections[session_id]:
                    self.active_connections[session_id].remove(websocket)
                
                # Clean up empty session
                if not self.active_connections[session_id]:
                    del self.active_connections[session_id]
        
        # Cancel heartbeat task
        task_key = f"{session_id}_{id(websocket)}"
        if task_key in self.connection_tasks:
            self.connection_tasks[task_key].cancel()
            del self.connection_tasks[task_key]
        
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send a message to a specific WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send personal message: {str(e)}")
    
    async def send_progress_update(self, session_id: str, data: dict):
        """
        Send progress update to all connections for a session
        """
        if session_id not in self.active_connections:
            logger.debug(f"No active connections for session {session_id}")
            return
        
        message = {
            "type": "progress_update",
            "data": data,
            "timestamp": time.time()
        }
        
        # Send to all connections for this session
        disconnected = []
        connections = self.active_connections.get(session_id, []).copy()
        
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send progress update: {str(e)}")
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected:
            await self.disconnect(websocket, session_id)
    
    def send_progress_update_sync(self, session_id: str, data: dict):
        """
        Synchronous version for use in Celery tasks
        """
        try:
            # Create new event loop if none exists
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run the async function
            if loop.is_running():
                # If loop is already running, schedule the coroutine
                asyncio.create_task(self.send_progress_update(session_id, data))
            else:
                # If loop is not running, run it
                loop.run_until_complete(self.send_progress_update(session_id, data))
        except Exception as e:
            logger.warning(f"Failed to send sync progress update: {str(e)}")
    
    async def broadcast_message(self, message: dict):
        """
        Broadcast a message to all connected clients
        """
        if not self.active_connections:
            return
        
        message["timestamp"] = time.time()
        disconnected = []
        
        for session_id, connections in self.active_connections.items():
            for websocket in connections:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to broadcast message: {str(e)}")
                    disconnected.append((websocket, session_id))
        
        # Clean up disconnected websockets
        for websocket, session_id in disconnected:
            await self.disconnect(websocket, session_id)
    
    async def send_task_status(self, session_id: str, task_id: str, status: str, **kwargs):
        """
        Send task status update
        """
        data = {
            "task_id": task_id,
            "status": status,
            **kwargs
        }
        await self.send_progress_update(session_id, data)
    
    async def _heartbeat(self, websocket: WebSocket, session_id: str):
        """
        Send periodic heartbeat to keep connection alive
        """
        try:
            while True:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": time.time()
                })
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat cancelled for session {session_id}")
        except Exception as e:
            logger.info(f"Heartbeat failed for session {session_id}: {str(e)}")
            await self.disconnect(websocket, session_id)
    
    def get_connection_count(self) -> int:
        """
        Get total number of active connections
        """
        return sum(len(connections) for connections in self.active_connections.values())
    
    def get_session_count(self) -> int:
        """
        Get number of active sessions
        """
        return len(self.active_connections)
    
    def get_connections_for_session(self, session_id: str) -> int:
        """
        Get number of connections for a specific session
        """
        return len(self.active_connections.get(session_id, []))

# Global connection manager instance
connection_manager = ConnectionManager()
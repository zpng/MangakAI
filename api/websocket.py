"""
WebSocket API endpoints for real-time communication
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from websocket_manager import connection_manager
from models.manga_models import UserSession
from database import get_db_session

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time communication
    """
    await connection_manager.connect(websocket, session_id)
    
    # Update user session activity
    try:
        with get_db_session() as db:
            session = db.query(UserSession).filter(UserSession.id == session_id).first()
            if not session:
                session = UserSession(id=session_id)
                db.add(session)
            else:
                session.last_activity = db.execute("SELECT CURRENT_TIMESTAMP").scalar()
            db.commit()
    except Exception as e:
        logger.warning(f"Failed to update session activity: {str(e)}")
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            # Handle different message types
            message_type = data.get("type")
            
            if message_type == "ping":
                # Respond to ping with pong
                await connection_manager.send_personal_message({
                    "type": "pong",
                    "timestamp": data.get("timestamp")
                }, websocket)
            
            elif message_type == "subscribe_task":
                # Subscribe to task status updates
                task_id = data.get("task_id")
                await connection_manager.send_personal_message({
                    "type": "subscribed",
                    "task_id": task_id,
                    "message": f"已订阅任务 {task_id} 的状态更新"
                }, websocket)
                
                logger.info(f"Session {session_id} subscribed to task {task_id}")
            
            elif message_type == "unsubscribe_task":
                # Unsubscribe from task status updates
                task_id = data.get("task_id")
                await connection_manager.send_personal_message({
                    "type": "unsubscribed",
                    "task_id": task_id,
                    "message": f"已取消订阅任务 {task_id}"
                }, websocket)
                
                logger.info(f"Session {session_id} unsubscribed from task {task_id}")
            
            elif message_type == "get_connection_info":
                # Send connection information
                await connection_manager.send_personal_message({
                    "type": "connection_info",
                    "session_id": session_id,
                    "total_connections": connection_manager.get_connection_count(),
                    "session_connections": connection_manager.get_connections_for_session(session_id)
                }, websocket)
            
            else:
                # Unknown message type
                await connection_manager.send_personal_message({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                }, websocket)
    
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket, session_id)
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {str(e)}")
        await connection_manager.disconnect(websocket, session_id)

@router.websocket("/ws/admin")
async def admin_websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """
    Admin WebSocket endpoint for monitoring
    """
    # Simple token-based authentication (in production, use proper JWT)
    if token != "admin_token_123":  # Replace with proper authentication
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    await websocket.accept()
    
    try:
        while True:
            # Send periodic statistics
            stats = {
                "type": "admin_stats",
                "total_connections": connection_manager.get_connection_count(),
                "total_sessions": connection_manager.get_session_count(),
                "timestamp": connection_manager.active_connections
            }
            
            await websocket.send_json(stats)
            
            # Wait for 10 seconds before sending next update
            import asyncio
            await asyncio.sleep(10)
    
    except WebSocketDisconnect:
        logger.info("Admin WebSocket disconnected")
    except Exception as e:
        logger.error(f"Admin WebSocket error: {str(e)}")

# Health check endpoint for WebSocket
@router.get("/ws/health")
async def websocket_health():
    """
    Health check for WebSocket service
    """
    return {
        "status": "healthy",
        "active_connections": connection_manager.get_connection_count(),
        "active_sessions": connection_manager.get_session_count()
    }
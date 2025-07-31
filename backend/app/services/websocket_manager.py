from fastapi import WebSocket
import asyncio
import json
from typing import List, Dict, Any
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SearchProgressManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.session_data: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Connect a WebSocket for a specific session"""
        await websocket.accept()
        
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        
        self.active_connections[session_id].append(websocket)
        
        # Initialize session data if not exists
        if session_id not in self.session_data:
            self.session_data[session_id] = {
                'started_at': datetime.now(timezone.utc).isoformat(),
                'status': 'connected',
                'agents': []
            }
        
        logger.info(f"WebSocket connected for session {session_id}")
    
    def disconnect(self, websocket: WebSocket, session_id: str):
        """Disconnect a WebSocket"""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            
            # Clean up empty session connections
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def broadcast_progress(self, session_id: str, progress_data: Dict[str, Any]):
        """Broadcast progress update to all connections for a session"""
        logger.info(f"Broadcasting progress for session {session_id}: {progress_data}")

        if session_id not in self.active_connections:
            logger.warning(f"No active connections for session {session_id}")
            return

        logger.info(f"Found {len(self.active_connections[session_id])} active connections for session {session_id}")

        message = {
            "session_id": session_id,
            "type": "progress_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": progress_data
        }
        
        # Update session data
        if session_id in self.session_data:
            self.session_data[session_id]['last_update'] = datetime.now(timezone.utc).isoformat()
            if 'agent' in progress_data:
                agent_info = {
                    'name': progress_data['agent'],
                    'status': progress_data.get('status', 'unknown'),
                    'message': progress_data.get('message', ''),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                self.session_data[session_id]['agents'].append(agent_info)
        
        disconnected = []
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.active_connections[session_id].remove(connection)
    
    async def broadcast_result(self, session_id: str, result_data: Dict[str, Any]):
        """Broadcast final result to all connections for a session"""
        logger.info(f"Broadcasting final result for session {session_id}: {result_data}")

        if session_id not in self.active_connections:
            logger.warning(f"No active connections for session {session_id}")
            return

        logger.info(f"Found {len(self.active_connections[session_id])} active connections for session {session_id}")

        message = {
            "session_id": session_id,
            "type": "final_result",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": result_data
        }
        
        # Update session data
        if session_id in self.session_data:
            self.session_data[session_id]['status'] = 'completed'
            self.session_data[session_id]['completed_at'] = datetime.now(timezone.utc).isoformat()
            self.session_data[session_id]['result'] = result_data
        
        disconnected = []
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending result to WebSocket: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.active_connections[session_id].remove(connection)
    
    async def broadcast_error(self, session_id: str, error_message: str):
        """Broadcast error to all connections for a session"""
        if session_id not in self.active_connections:
            return
        
        message = {
            "session_id": session_id,
            "type": "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error_message
        }
        
        # Update session data
        if session_id in self.session_data:
            self.session_data[session_id]['status'] = 'error'
            self.session_data[session_id]['error'] = error_message
            self.session_data[session_id]['completed_at'] = datetime.now(timezone.utc).isoformat()
        
        disconnected = []
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending error to WebSocket: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.active_connections[session_id].remove(connection)
    
    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get session information"""
        return self.session_data.get(session_id, {})
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self.active_connections.keys())
    
    def cleanup_session(self, session_id: str):
        """Clean up session data"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.session_data:
            del self.session_data[session_id]


# Global progress manager instance
progress_manager = SearchProgressManager()

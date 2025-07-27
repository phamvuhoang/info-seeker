import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)


class SearchProgressManager:
    def __init__(self):
        self.active_sessions: Dict[str, bool] = {}
        self.session_queues: Dict[str, asyncio.Queue] = {}
        self.session_data: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, session_id: str):
        """Connect a session for SSE updates"""
        self.active_sessions[session_id] = True
        self.session_queues[session_id] = asyncio.Queue()
        
        # Initialize session data if not exists
        if session_id not in self.session_data:
            self.session_data[session_id] = {
                'started_at': datetime.now(timezone.utc).isoformat(),
                'status': 'connected',
                'agents': []
            }
        
        logger.info(f"SSE connected for session {session_id}")
    
    def disconnect(self, session_id: str):
        """Disconnect a session"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        if session_id in self.session_queues:
            del self.session_queues[session_id]
        
        logger.info(f"SSE disconnected for session {session_id}")
    
    async def get_message(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the next message for a session (non-blocking)"""
        if session_id not in self.session_queues:
            return None
        
        try:
            # Try to get a message without blocking
            message = self.session_queues[session_id].get_nowait()
            return message
        except asyncio.QueueEmpty:
            return None
    
    async def broadcast_progress(self, session_id: str, progress_data: Dict[str, Any]):
        """Broadcast progress update to a specific session"""
        if session_id not in self.active_sessions:
            logger.warning(f"No active SSE connection for session {session_id}")
            return
        
        try:
            # Add timestamp
            progress_data['timestamp'] = datetime.now(timezone.utc).isoformat()
            progress_data['type'] = 'progress_update'
            
            # Add to queue
            if session_id in self.session_queues:
                await self.session_queues[session_id].put(progress_data)
                logger.info(f"Broadcasting progress for session {session_id}: {progress_data.get('agent', 'Unknown')} - {progress_data.get('status', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Error broadcasting progress for session {session_id}: {e}")
    
    async def broadcast_final_result(self, session_id: str, result_data: Dict[str, Any]):
        """Broadcast final result to a specific session"""
        if session_id not in self.active_sessions:
            logger.warning(f"No active SSE connection for session {session_id}")
            return

        try:
            # Add timestamp and type
            result_data['timestamp'] = datetime.now(timezone.utc).isoformat()
            result_data['type'] = 'final_result'

            # Add to queue
            if session_id in self.session_queues:
                await self.session_queues[session_id].put(result_data)
                logger.info(f"Broadcasting final result for session {session_id}")

        except Exception as e:
            logger.error(f"Error broadcasting final result for session {session_id}: {e}")

    async def broadcast_result(self, session_id: str, result_data: Dict[str, Any]):
        """Alias for broadcast_final_result for compatibility"""
        await self.broadcast_final_result(session_id, result_data)
    
    async def broadcast_error(self, session_id: str, error_message: str):
        """Broadcast error to a specific session"""
        if session_id not in self.active_sessions:
            logger.warning(f"No active SSE connection for session {session_id}")
            return
        
        try:
            error_data = {
                'type': 'error',
                'error': error_message,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Add to queue
            if session_id in self.session_queues:
                await self.session_queues[session_id].put(error_data)
                logger.info(f"Broadcasting error for session {session_id}: {error_message}")
            
        except Exception as e:
            logger.error(f"Error broadcasting error for session {session_id}: {e}")
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get current status of a session"""
        return self.session_data.get(session_id, {})
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self.active_sessions.keys())


# Global instance
progress_manager = SearchProgressManager()

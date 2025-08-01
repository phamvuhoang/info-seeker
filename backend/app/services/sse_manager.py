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
        self.last_message_time: Dict[str, float] = {}
        self.message_throttle_interval = 0.5  # Minimum 0.5 seconds between messages
    
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
            logger.warning(f"Session {session_id} not found in queues")
            return None

        try:
            # Try to get a message without blocking
            message = self.session_queues[session_id].get_nowait()
            logger.debug(f"Retrieved message for session {session_id}: {message.get('type', 'unknown')}")
            return message
        except asyncio.QueueEmpty:
            return None
    
    async def broadcast_progress(self, session_id: str, progress_data: Dict[str, Any]):
        """Broadcast enhanced progress update with detailed information"""
        if session_id not in self.active_sessions:
            logger.warning(f"No active SSE connection for session {session_id}")
            return

        # Throttle messages to prevent overwhelming the frontend
        import time
        current_time = time.time()
        last_time = self.last_message_time.get(session_id, 0)

        # Skip non-critical messages if sent too frequently
        if (current_time - last_time) < self.message_throttle_interval:
            status = progress_data.get('status', '')
            # Only allow critical status updates through throttling
            if status not in ['started', 'completed', 'failed']:
                return

        try:
            # Enhance progress data with additional metadata
            enhanced_progress = {
                **progress_data,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'type': 'progress_update',
                'session_id': session_id
            }

            # Add detailed information if available
            if 'details' in progress_data:
                enhanced_progress['details'] = progress_data['details']

            # Add result preview if available
            if 'result_preview' in progress_data:
                enhanced_progress['result_preview'] = progress_data['result_preview']

            # Track agent progress in session data
            if session_id in self.session_data:
                agent_name = progress_data.get('agent', 'Unknown')
                status = progress_data.get('status', 'unknown')

                # Update or add agent status
                agents = self.session_data[session_id].get('agents', [])
                agent_found = False

                for agent in agents:
                    if agent['name'] == agent_name:
                        agent['status'] = status
                        agent['last_update'] = enhanced_progress['timestamp']
                        if 'message' in progress_data:
                            agent['message'] = progress_data['message']
                        if 'details' in progress_data:
                            agent['details'] = progress_data['details']
                        agent_found = True
                        break

                if not agent_found:
                    agents.append({
                        'name': agent_name,
                        'status': status,
                        'message': progress_data.get('message', ''),
                        'details': progress_data.get('details', {}),
                        'last_update': enhanced_progress['timestamp']
                    })

                self.session_data[session_id]['agents'] = agents
                self.session_data[session_id]['last_update'] = enhanced_progress['timestamp']

            # Add to queue
            if session_id in self.session_queues:
                await self.session_queues[session_id].put(enhanced_progress)
                self.last_message_time[session_id] = current_time

                # Log with more detail
                agent_name = progress_data.get('agent', 'Unknown')
                status = progress_data.get('status', 'Unknown')
                message = progress_data.get('message', '')
                details = progress_data.get('details', {})

                logger.info(f"Broadcasting progress for session {session_id}: {agent_name} - {status}")
                if details:
                    logger.debug(f"Progress details: {details}")

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

    async def broadcast_step_result(self, session_id: str, step_data: Dict[str, Any]):
        """Broadcast detailed step result with intermediate outputs"""
        if session_id not in self.active_sessions:
            logger.warning(f"No active SSE connection for session {session_id}")
            return

        try:
            step_result = {
                'type': 'step_result',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'session_id': session_id,
                **step_data
            }

            # Add to queue
            if session_id in self.session_queues:
                await self.session_queues[session_id].put(step_result)
                logger.info(f"Broadcasting step result for session {session_id}: {step_data.get('step_name', 'Unknown step')}")

        except Exception as e:
            logger.error(f"Error broadcasting step result for session {session_id}: {e}")

    async def broadcast_agent_metrics(self, session_id: str, metrics_data: Dict[str, Any]):
        """Broadcast agent performance metrics"""
        if session_id not in self.active_sessions:
            logger.warning(f"No active SSE connection for session {session_id}")
            return

        try:
            metrics = {
                'type': 'agent_metrics',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'session_id': session_id,
                **metrics_data
            }

            # Add to queue
            if session_id in self.session_queues:
                await self.session_queues[session_id].put(metrics)
                logger.debug(f"Broadcasting metrics for session {session_id}: {metrics_data.get('agent', 'Unknown agent')}")

        except Exception as e:
            logger.error(f"Error broadcasting metrics for session {session_id}: {e}")
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get current status of a session"""
        return self.session_data.get(session_id, {})
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self.active_sessions.keys())


# Global instance
progress_manager = SearchProgressManager()

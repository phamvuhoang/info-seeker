import asyncpg
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from ..core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for handling database operations for structured data tables"""
    
    def __init__(self):
        self.connection_pool = None
    
    async def get_connection(self):
        """Get database connection"""
        if not self.connection_pool:
            # Parse database URL to get connection parameters
            db_url = settings.database_url
            # Convert from SQLAlchemy format to asyncpg format
            if db_url.startswith("postgresql+psycopg://"):
                db_url = db_url.replace("postgresql+psycopg://", "postgresql://")
            
            self.connection_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=10)
        
        return self.connection_pool.acquire()
    
    async def save_user_session(self, session_id: str, user_data: Dict[str, Any] = None) -> bool:
        """Save or update user session"""
        try:
            async with await self.get_connection() as conn:
                query = """
                    INSERT INTO user_sessions (session_id, user_data, last_activity, created_at)
                    VALUES ($1, $2, NOW(), NOW())
                    ON CONFLICT (session_id) 
                    DO UPDATE SET 
                        user_data = EXCLUDED.user_data,
                        last_activity = NOW();
                """
                
                await conn.execute(query, session_id, json.dumps(user_data or {}))
                logger.info(f"Saved user session: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving user session {session_id}: {e}")
            return False
    
    async def save_search_history(
        self, 
        session_id: str, 
        query: str, 
        response: str, 
        sources: List[Dict[str, Any]] = None,
        processing_time: float = None
    ) -> bool:
        """Save search query and response to history"""
        try:
            async with await self.get_connection() as conn:
                # Ensure user session exists
                await self.save_user_session(session_id)
                
                query_sql = """
                    INSERT INTO search_history (session_id, query, response, sources, processing_time, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW());
                """
                
                await conn.execute(
                    query_sql, 
                    session_id, 
                    query, 
                    response, 
                    json.dumps(sources or []),
                    processing_time
                )
                logger.info(f"Saved search history for session: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving search history for session {session_id}: {e}")
            return False
    
    async def save_agent_workflow_session(
        self,
        session_id: str,
        workflow_name: str,
        status: str = 'running',
        metadata: Dict[str, Any] = None,
        result: Dict[str, Any] = None
    ) -> bool:
        """Save or update agent workflow session"""
        try:
            async with await self.get_connection() as conn:
                query = """
                    INSERT INTO agent_workflow_sessions (session_id, workflow_name, status, started_at, metadata, result)
                    VALUES ($1, $2, $3, NOW(), $4, $5)
                    ON CONFLICT (session_id) 
                    DO UPDATE SET 
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        result = EXCLUDED.result,
                        completed_at = CASE WHEN EXCLUDED.status IN ('completed', 'failed') THEN NOW() ELSE agent_workflow_sessions.completed_at END;
                """
                
                await conn.execute(
                    query, 
                    session_id, 
                    workflow_name, 
                    status, 
                    json.dumps(metadata or {}),
                    json.dumps(result or {})
                )
                logger.info(f"Saved agent workflow session: {session_id} - {status}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving agent workflow session {session_id}: {e}")
            return False
    
    async def save_agent_execution_log(
        self,
        session_id: str,
        agent_name: str,
        step_name: str = None,
        status: str = 'started',
        input_data: Dict[str, Any] = None,
        output_data: Dict[str, Any] = None,
        error_message: str = None,
        execution_time_ms: int = None
    ) -> bool:
        """Save agent execution log"""
        try:
            async with await self.get_connection() as conn:
                # Handle timing properly to avoid constraint violations
                if status in ('completed', 'failed'):
                    # For completed/failed status, use a query that ensures completed_at > started_at
                    query = """
                        INSERT INTO agent_execution_logs
                        (session_id, agent_name, step_name, status, started_at, input_data, output_data, error_message, execution_time_ms, completed_at)
                        VALUES ($1, $2, $3, $4::VARCHAR(50), NOW(), $5, $6, $7, $8, NOW() + INTERVAL '1 millisecond');
                    """

                    await conn.execute(
                        query,
                        session_id,
                        agent_name,
                        step_name,
                        status,
                        json.dumps(input_data or {}),
                        json.dumps(output_data or {}),
                        error_message,
                        execution_time_ms
                    )
                else:
                    # For started status, completed_at is NULL
                    query = """
                        INSERT INTO agent_execution_logs
                        (session_id, agent_name, step_name, status, started_at, input_data, output_data, error_message, execution_time_ms, completed_at)
                        VALUES ($1, $2, $3, $4::VARCHAR(50), NOW(), $5, $6, $7, $8, NULL);
                    """

                    await conn.execute(
                        query,
                        session_id,
                        agent_name,
                        step_name,
                        status,
                        json.dumps(input_data or {}),
                        json.dumps(output_data or {}),
                        error_message,
                        execution_time_ms
                    )
                logger.info(f"Saved agent execution log: {agent_name} - {status}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving agent execution log for {agent_name}: {e}")
            return False
    
    async def save_search_feedback(
        self,
        session_id: str,
        query: str,
        rating: int,
        feedback_text: str = None,
        sources_helpful: List[str] = None
    ) -> bool:
        """Save user feedback on search results"""
        try:
            async with await self.get_connection() as conn:
                query_sql = """
                    INSERT INTO search_feedback (session_id, query, rating, feedback_text, sources_helpful, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW());
                """
                
                await conn.execute(
                    query_sql,
                    session_id,
                    query,
                    rating,
                    feedback_text,
                    json.dumps(sources_helpful or [])
                )
                logger.info(f"Saved search feedback for session: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving search feedback for session {session_id}: {e}")
            return False
    
    async def update_source_reliability(
        self,
        domain: str,
        positive_feedback: bool = None,
        citation_count: int = 1
    ) -> bool:
        """Update source reliability scores"""
        try:
            async with await self.get_connection() as conn:
                if positive_feedback is not None:
                    # Update with feedback
                    query = """
                        INSERT INTO source_reliability (domain, total_citations, positive_feedback, negative_feedback, last_updated)
                        VALUES ($1, $2, $3, $4, NOW())
                        ON CONFLICT (domain) 
                        DO UPDATE SET 
                            total_citations = source_reliability.total_citations + $2,
                            positive_feedback = source_reliability.positive_feedback + $3,
                            negative_feedback = source_reliability.negative_feedback + $4,
                            reliability_score = LEAST(0.95, GREATEST(0.1, 
                                (source_reliability.positive_feedback + $3) * 1.0 / 
                                GREATEST(1, source_reliability.total_citations + $2)
                            )),
                            last_updated = NOW();
                    """
                    
                    pos_feedback = 1 if positive_feedback else 0
                    neg_feedback = 0 if positive_feedback else 1
                    
                    await conn.execute(query, domain, citation_count, pos_feedback, neg_feedback)
                else:
                    # Just update citation count
                    query = """
                        INSERT INTO source_reliability (domain, total_citations, last_updated)
                        VALUES ($1, $2, NOW())
                        ON CONFLICT (domain) 
                        DO UPDATE SET 
                            total_citations = source_reliability.total_citations + $2,
                            last_updated = NOW();
                    """
                    
                    await conn.execute(query, domain, citation_count)
                
                logger.info(f"Updated source reliability for domain: {domain}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating source reliability for {domain}: {e}")
            return False
    
    async def get_search_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get search history for a session"""
        try:
            async with await self.get_connection() as conn:
                query = """
                    SELECT id, query, response, sources, processing_time, created_at
                    FROM search_history 
                    WHERE session_id = $1 
                    ORDER BY created_at DESC 
                    LIMIT $2;
                """
                
                rows = await conn.fetch(query, session_id, limit)
                
                history = []
                for row in rows:
                    history.append({
                        'id': row['id'],
                        'query': row['query'],
                        'response': row['response'],
                        'sources': row['sources'],
                        'processing_time': row['processing_time'],
                        'created_at': row['created_at'].isoformat() if row['created_at'] else None
                    })
                
                return history
                
        except Exception as e:
            logger.error(f"Error getting search history for session {session_id}: {e}")
            return []


# Global instance
database_service = DatabaseService()

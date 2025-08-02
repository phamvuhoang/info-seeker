from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings(BaseSettings):
    # API Configuration
    app_name: str = "InfoSeeker"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # OpenAI Configuration
    openai_api_key: str
    
    # Database Configuration
    database_url: str = "postgresql+psycopg://infoseeker:infoseeker@localhost:5433/infoseeker"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    
    # Search Configuration
    max_search_results: int = 10
    response_timeout: int = 30

    # Vector database settings
    vector_table_name: str = "infoseeker_documents"
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072
    max_chunk_size: int = 1000
    chunk_overlap: int = 200

    # Multi-agent settings - Optimized for performance
    max_concurrent_agents: int = 3  # Reduced for better performance
    agent_timeout_seconds: int = 60  # Reduced timeout
    workflow_timeout_seconds: int = 120  # Reduced workflow timeout

    # WebSocket settings
    websocket_heartbeat_interval: int = 30
    max_websocket_connections: int = 100

    # Search settings - Optimized for speed and rate limiting
    max_rag_results: int = 3  # Reduced for faster processing and balance
    max_web_results: int = 3  # Reduced to avoid rate limiting
    hybrid_search_weight_rag: float = 0.6
    hybrid_search_weight_web: float = 0.4

    # RAG relevance filtering (disabled - using agno's built-in search)
    rag_similarity_threshold: Optional[float] = None  # Disabled to use agno's built-in search reliability

    # Source balancing settings
    max_total_sources: int = 8  # Maximum sources to display
    max_db_sources: int = 3     # Maximum DB sources to prevent domination
    min_web_sources: int = 2    # Minimum web sources for freshness

    # Performance settings
    redis_cache_ttl: int = 3600  # 1 hour
    vector_search_cache_ttl: int = 1800  # 30 minutes

    # Connection settings - Optimized to reduce resource leaks
    http_connection_pool_size: int = 50  # Reduced to prevent resource leaks
    http_connection_timeout: int = 30
    database_pool_size: int = 10  # Reduced for better resource management
    database_pool_timeout: int = 30
    max_websocket_connections: int = 50  # Added limit for websocket connections

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False
    )


settings = Settings()
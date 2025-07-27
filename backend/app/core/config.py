from pydantic_settings import BaseSettings, SettingsConfigDict
import os
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

    # Multi-agent settings
    max_concurrent_agents: int = 5
    agent_timeout_seconds: int = 300
    workflow_timeout_seconds: int = 600

    # WebSocket settings
    websocket_heartbeat_interval: int = 30
    max_websocket_connections: int = 100

    # Search settings
    max_rag_results: int = 10
    max_web_results: int = 10
    hybrid_search_weight_rag: float = 0.6
    hybrid_search_weight_web: float = 0.4

    # Performance settings
    redis_cache_ttl: int = 3600  # 1 hour
    vector_search_cache_ttl: int = 1800  # 30 minutes

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False
    )


settings = Settings()
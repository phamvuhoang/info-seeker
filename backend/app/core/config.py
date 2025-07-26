from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Configuration
    app_name: str = "InfoSeeker"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # OpenAI Configuration
    openai_api_key: str
    
    # Database Configuration
    database_url: str = "postgresql+psycopg://infoseeker:infoseeker@localhost:5432/infoseeker"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    
    # Search Configuration
    max_search_results: int = 10
    response_timeout: int = 30
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"


settings = Settings()
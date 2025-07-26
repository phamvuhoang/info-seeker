from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SearchQuery(BaseModel):
    query: str = Field(..., description="The search query")
    max_results: Optional[int] = Field(10, description="Maximum number of results")
    include_web: bool = Field(True, description="Include web search results")
    include_stored: bool = Field(True, description="Include stored knowledge results")


class SearchResult(BaseModel):
    title: str
    content: str
    url: Optional[str] = None
    source: str
    relevance_score: Optional[float] = None
    timestamp: Optional[datetime] = None


class SearchResponse(BaseModel):
    query: str
    answer: str
    sources: List[SearchResult]
    processing_time: float
    session_id: Optional[str] = None


class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    version: str
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SearchQuery(BaseModel):
    query: str = Field(..., description="The search query")
    max_results: Optional[int] = Field(10, description="Maximum number of results")
    include_web: bool = Field(True, description="Include web search results")
    include_stored: bool = Field(True, description="Include stored knowledge results")
    include_site_specific: bool = Field(False, description="Include site-specific search results")
    target_sites: Optional[List[str]] = Field(None, description="Specific sites to search (auto-detect if None)")
    use_intelligent_search: bool = Field(True, description="Use intelligent search intent detection")


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


class SiteSpecificSearchQuery(BaseModel):
    query: str = Field(..., description="The search query")
    target_sites: List[str] = Field(..., description="List of site keys to search")
    page: int = Field(1, description="Page number (1-based)")
    per_page: int = Field(10, description="Results per page")
    sort_by: str = Field("relevance", description="Sort by: relevance, title, site")
    filter_by_site: Optional[str] = Field(None, description="Filter by specific site")


class ProductResult(BaseModel):
    title: str = Field(..., description="Product title")
    description: str = Field("", description="Product description")
    url: str = Field(..., description="Product URL")
    image_url: Optional[str] = Field(None, description="Product image URL")
    price: Optional[str] = Field(None, description="Product price")
    rating: Optional[float] = Field(None, description="Product rating")
    site_key: str = Field(..., description="Site identifier")
    site_name: str = Field(..., description="Site display name")
    content: str = Field("", description="Full content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    tokens_used: int = Field(0, description="Tokens used for this result")
    relevance_score: Optional[float] = Field(None, description="Relevance score")


class SiteSpecificSearchResponse(BaseModel):
    query: str = Field(..., description="Original search query")
    results: List[ProductResult] = Field(..., description="Search results")
    pagination: Dict[str, Any] = Field(..., description="Pagination information")
    sites_searched: List[str] = Field(..., description="Successfully searched sites")
    sites_failed: List[str] = Field(default_factory=list, description="Failed sites")
    total_results: int = Field(..., description="Total number of results")
    total_tokens_used: int = Field(0, description="Total tokens used")
    processing_time: float = Field(..., description="Processing time in seconds")
    session_id: Optional[str] = Field(None, description="Session identifier")


class SearchIntentResponse(BaseModel):
    query: str
    detected_language: str
    category: str
    recommendations: Dict[str, Any]
    confidence: float
    reasoning: str


class EnhancedSearchResponse(BaseModel):
    query: str
    answer: str
    sources: List[SearchResult]
    search_strategy: Dict[str, Any]
    processing_time: float
    session_id: Optional[str] = None
    intent_analysis: Optional[SearchIntentResponse] = None


class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    version: str
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal


class HotelBase(BaseModel):
    """Base model for hotel data"""
    name: str = Field(..., description="Hotel name")
    url: str = Field(..., description="Hotel URL")
    rating: Optional[float] = Field(None, ge=0.0, le=5.0, description="Hotel rating (0-5)")
    review_count: Optional[int] = Field(None, ge=0, description="Number of reviews")
    price_per_night: Optional[Decimal] = Field(None, ge=0, description="Price per night")
    currency: Optional[str] = Field(None, max_length=10, description="Currency code")
    address: Optional[str] = Field(None, description="Hotel address")
    city: Optional[str] = Field(None, max_length=255, description="City name")
    image_url: Optional[str] = Field(None, description="Hotel image URL")


class Hotel(HotelBase):
    """Hotel model with database fields"""
    id: int = Field(..., description="Database ID")
    source_item_id: str = Field(..., description="Source website item ID")
    source_name: str = Field(..., description="Source website name")
    content_hash: str = Field(..., description="Content hash for change detection")
    scraped_at: datetime = Field(..., description="When the data was scraped")
    
    model_config = ConfigDict(from_attributes=True)


class HotelCreate(HotelBase):
    """Model for creating new hotel records"""
    source_item_id: str = Field(..., description="Source website item ID")
    source_name: str = Field(..., description="Source website name")
    content_hash: str = Field(..., description="Content hash for change detection")


class RestaurantBase(BaseModel):
    """Base model for restaurant data"""
    name: str = Field(..., description="Restaurant name")
    url: str = Field(..., description="Restaurant URL")
    rating: Optional[float] = Field(None, ge=0.0, le=5.0, description="Restaurant rating (0-5)")
    review_count: Optional[int] = Field(None, ge=0, description="Number of reviews")
    cuisine_type: Optional[str] = Field(None, max_length=255, description="Type of cuisine")
    price_range: Optional[str] = Field(None, max_length=100, description="Price range")
    address: Optional[str] = Field(None, description="Restaurant address")
    city: Optional[str] = Field(None, max_length=255, description="City name")
    image_url: Optional[str] = Field(None, description="Restaurant image URL")


class Restaurant(RestaurantBase):
    """Restaurant model with database fields"""
    id: int = Field(..., description="Database ID")
    source_item_id: str = Field(..., description="Source website item ID")
    source_name: str = Field(..., description="Source website name")
    content_hash: str = Field(..., description="Content hash for change detection")
    scraped_at: datetime = Field(..., description="When the data was scraped")
    
    model_config = ConfigDict(from_attributes=True)


class RestaurantCreate(RestaurantBase):
    """Model for creating new restaurant records"""
    source_item_id: str = Field(..., description="Source website item ID")
    source_name: str = Field(..., description="Source website name")
    content_hash: str = Field(..., description="Content hash for change detection")


class ScrapingConfig(BaseModel):
    """Model for scraping configuration"""
    id: int = Field(..., description="Configuration ID")
    source_name: str = Field(..., description="Source website name")
    base_url: str = Field(..., description="Base URL of the source")
    is_active: bool = Field(..., description="Whether scraping is active")
    extraction_schema: Dict[str, Any] = Field(..., description="Data extraction schema")
    scrape_interval_hours: int = Field(..., description="Scraping interval in hours")
    last_scraped_at: Optional[datetime] = Field(None, description="Last scraping timestamp")
    created_at: datetime = Field(..., description="Configuration creation timestamp")
    
    model_config = ConfigDict(from_attributes=True)


class ScrapingConfigCreate(BaseModel):
    """Model for creating scraping configuration"""
    source_name: str = Field(..., description="Source website name")
    base_url: str = Field(..., description="Base URL of the source")
    is_active: bool = Field(True, description="Whether scraping is active")
    extraction_schema: Dict[str, Any] = Field(..., description="Data extraction schema")
    scrape_interval_hours: int = Field(24, description="Scraping interval in hours")


class ScrapingConfigUpdate(BaseModel):
    """Model for updating scraping configuration"""
    is_active: Optional[bool] = Field(None, description="Whether scraping is active")
    extraction_schema: Optional[Dict[str, Any]] = Field(None, description="Data extraction schema")
    scrape_interval_hours: Optional[int] = Field(None, description="Scraping interval in hours")


class SearchFilters(BaseModel):
    """Model for search filters"""
    search: Optional[str] = Field(None, description="Text search query")
    min_rating: Optional[float] = Field(None, ge=0.0, le=5.0, description="Minimum rating filter")
    max_rating: Optional[float] = Field(None, ge=0.0, le=5.0, description="Maximum rating filter")
    city: Optional[str] = Field(None, description="City filter")
    source_name: Optional[str] = Field(None, description="Source website filter")
    cuisine_type: Optional[str] = Field(None, description="Cuisine type filter (restaurants only)")
    min_price: Optional[Decimal] = Field(None, ge=0, description="Minimum price filter (hotels only)")
    max_price: Optional[Decimal] = Field(None, ge=0, description="Maximum price filter (hotels only)")


class PaginationParams(BaseModel):
    """Model for pagination parameters"""
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Page size")


class PaginatedResponse(BaseModel):
    """Generic paginated response model"""
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class PaginatedHotelsResponse(BaseModel):
    """Paginated response for hotels"""
    items: List[Hotel] = Field(..., description="List of hotels")
    total: int = Field(..., description="Total number of hotels")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class PaginatedRestaurantsResponse(BaseModel):
    """Paginated response for restaurants"""
    items: List[Restaurant] = Field(..., description="List of restaurants")
    total: int = Field(..., description="Total number of restaurants")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class ScrapingResult(BaseModel):
    """Model for scraping operation results"""
    source_name: str = Field(..., description="Source website name")
    status: str = Field(..., description="Scraping status")
    started_at: datetime = Field(..., description="When scraping started")
    completed_at: Optional[datetime] = Field(None, description="When scraping completed")
    duration_seconds: Optional[float] = Field(None, description="Scraping duration in seconds")
    urls_processed: int = Field(0, description="Number of URLs processed")
    items_scraped: int = Field(0, description="Number of items scraped")
    items_saved: int = Field(0, description="Number of items saved")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")


class ManualScrapingRequest(BaseModel):
    """Model for manual scraping requests"""
    source_name: str = Field(..., description="Source website name to scrape")


class ScrapingStatusResponse(BaseModel):
    """Model for scraping status response"""
    scheduler_running: bool = Field(..., description="Whether scheduler is running")
    jobs: List[Dict[str, Any]] = Field(..., description="List of scheduled jobs")
    last_run_results: Optional[List[ScrapingResult]] = Field(None, description="Results from last run")

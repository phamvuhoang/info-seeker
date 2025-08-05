from fastapi import APIRouter, Query, HTTPException, Depends, BackgroundTasks
from typing import Optional
import logging
from ..models.scraped_data import (
    Hotel, Restaurant, SearchFilters, PaginationParams,
    PaginatedHotelsResponse, PaginatedRestaurantsResponse,
    ManualScrapingRequest, ScrapingResult, ScrapingStatusResponse
)
from ..services.scraped_data_service import scraped_data_service
from ..services.scheduler_service import scheduler_service

logger = logging.getLogger(__name__)

router = APIRouter()


def get_search_filters(
    search: Optional[str] = Query(None, description="Text search query"),
    min_rating: Optional[float] = Query(None, ge=0.0, le=5.0, description="Minimum rating filter"),
    max_rating: Optional[float] = Query(None, ge=0.0, le=5.0, description="Maximum rating filter"),
    city: Optional[str] = Query(None, description="City filter"),
    source_name: Optional[str] = Query(None, description="Source website filter"),
    cuisine_type: Optional[str] = Query(None, description="Cuisine type filter (restaurants only)"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter (hotels only)"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter (hotels only)")
) -> SearchFilters:
    """Dependency to extract search filters from query parameters"""
    return SearchFilters(
        search=search,
        min_rating=min_rating,
        max_rating=max_rating,
        city=city,
        source_name=source_name,
        cuisine_type=cuisine_type,
        min_price=min_price,
        max_price=max_price
    )


def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size")
) -> PaginationParams:
    """Dependency to extract pagination parameters from query parameters"""
    return PaginationParams(page=page, size=size)


@router.get("/hotels", response_model=PaginatedHotelsResponse)
async def search_hotels(
    filters: SearchFilters = Depends(get_search_filters),
    pagination: PaginationParams = Depends(get_pagination_params)
):
    """
    Search hotels with filtering and pagination
    
    - **search**: Text search in hotel name and address
    - **min_rating**: Minimum rating filter (0-5)
    - **max_rating**: Maximum rating filter (0-5)
    - **city**: Filter by city name
    - **source_name**: Filter by source website (e.g., 'agoda')
    - **min_price**: Minimum price per night
    - **max_price**: Maximum price per night
    - **page**: Page number (starts from 1)
    - **size**: Number of items per page (1-100)
    """
    try:
        logger.info(f"Searching hotels with filters: {filters.dict()} and pagination: {pagination.dict()}")
        result = await scraped_data_service.search_hotels(filters, pagination)
        logger.info(f"Found {result.total} hotels, returning page {result.page}")
        return result
    except Exception as e:
        logger.error(f"Error searching hotels: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while searching hotels")


@router.get("/restaurants", response_model=PaginatedRestaurantsResponse)
async def search_restaurants(
    filters: SearchFilters = Depends(get_search_filters),
    pagination: PaginationParams = Depends(get_pagination_params)
):
    """
    Search restaurants with filtering and pagination
    
    - **search**: Text search in restaurant name and address
    - **min_rating**: Minimum rating filter (0-5)
    - **max_rating**: Maximum rating filter (0-5)
    - **city**: Filter by city name
    - **source_name**: Filter by source website (e.g., 'tabelog')
    - **cuisine_type**: Filter by cuisine type
    - **page**: Page number (starts from 1)
    - **size**: Number of items per page (1-100)
    """
    try:
        logger.info(f"Searching restaurants with filters: {filters.dict()} and pagination: {pagination.dict()}")
        result = await scraped_data_service.search_restaurants(filters, pagination)
        logger.info(f"Found {result.total} restaurants, returning page {result.page}")
        return result
    except Exception as e:
        logger.error(f"Error searching restaurants: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while searching restaurants")


@router.get("/hotels/{hotel_id}", response_model=Hotel)
async def get_hotel(hotel_id: int):
    """Get a specific hotel by ID"""
    try:
        hotel = await scraped_data_service.get_hotel_by_id(hotel_id)
        if not hotel:
            raise HTTPException(status_code=404, detail="Hotel not found")
        return hotel
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting hotel {hotel_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while getting hotel")


@router.get("/restaurants/{restaurant_id}", response_model=Restaurant)
async def get_restaurant(restaurant_id: int):
    """Get a specific restaurant by ID"""
    try:
        restaurant = await scraped_data_service.get_restaurant_by_id(restaurant_id)
        if not restaurant:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        return restaurant
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting restaurant {restaurant_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while getting restaurant")


@router.get("/statistics")
async def get_statistics():
    """Get statistics about scraped data"""
    try:
        stats = await scraped_data_service.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while getting statistics")


@router.post("/scrape/{source_name}", response_model=ScrapingResult)
async def trigger_manual_scraping(
    source_name: str,
    background_tasks: BackgroundTasks
):
    """
    Manually trigger scraping for a specific source
    
    **Note**: This is an admin/debug endpoint. The scraping will run in the background.
    
    Supported sources:
    - **agoda**: Scrape hotel data from Agoda
    - **tabelog**: Scrape restaurant data from Tabelog
    """
    try:
        # Validate source name
        valid_sources = ['agoda', 'tabelog']
        if source_name not in valid_sources:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid source name. Supported sources: {', '.join(valid_sources)}"
            )
        
        logger.info(f"Manual scraping triggered for source: {source_name}")
        
        # Trigger scraping in background
        result = await scheduler_service.trigger_manual_scraping(source_name)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering manual scraping for {source_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while triggering scraping")


@router.get("/scraping/status", response_model=ScrapingStatusResponse)
async def get_scraping_status():
    """
    Get the status of the scraping scheduler and recent jobs
    
    Returns information about:
    - Whether the scheduler is running
    - List of scheduled jobs
    - Status of recent scraping runs
    """
    try:
        status = scheduler_service.get_job_status()
        
        return ScrapingStatusResponse(
            scheduler_running=status.get('scheduler_running', False),
            jobs=status.get('jobs', []),
            last_run_results=None  # Could be extended to include recent results
        )
        
    except Exception as e:
        logger.error(f"Error getting scraping status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while getting scraping status")


@router.post("/scraping/schedule/{source_name}")
async def add_custom_schedule(
    source_name: str,
    cron_expression: str = Query(..., description="Cron expression (e.g., '0 2 * * *' for daily at 2 AM)")
):
    """
    Add a custom schedule for a specific source
    
    **Cron expression format**: "minute hour day month day_of_week"
    
    Examples:
    - `0 2 * * *`: Daily at 2 AM
    - `0 */6 * * *`: Every 6 hours
    - `0 9 * * 1`: Every Monday at 9 AM
    """
    try:
        # Validate source name
        valid_sources = ['agoda', 'tabelog']
        if source_name not in valid_sources:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid source name. Supported sources: {', '.join(valid_sources)}"
            )
        
        success = await scheduler_service.add_custom_job(source_name, cron_expression)
        
        if success:
            return {"message": f"Custom schedule added for {source_name}", "cron_expression": cron_expression}
        else:
            raise HTTPException(status_code=400, detail="Failed to add custom schedule")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding custom schedule for {source_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while adding custom schedule")


@router.delete("/scraping/schedule/{source_name}")
async def remove_custom_schedule(source_name: str):
    """Remove custom schedule for a specific source"""
    try:
        # Validate source name
        valid_sources = ['agoda', 'tabelog']
        if source_name not in valid_sources:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid source name. Supported sources: {', '.join(valid_sources)}"
            )
        
        success = await scheduler_service.remove_custom_job(source_name)
        
        if success:
            return {"message": f"Custom schedule removed for {source_name}"}
        else:
            raise HTTPException(status_code=404, detail="No custom schedule found for this source")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing custom schedule for {source_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while removing custom schedule")

import asyncpg
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
from ..core.config import settings
from ..models.scraped_data import (
    Hotel, Restaurant, SearchFilters, PaginationParams,
    PaginatedHotelsResponse, PaginatedRestaurantsResponse
)

logger = logging.getLogger(__name__)


class ScrapedDataService:
    """Service for handling CRUD operations on scraped data"""
    
    def __init__(self):
        self.connection_pool = None
    
    async def get_connection(self):
        """Get database connection"""
        if not self.connection_pool:
            db_url = settings.database_url
            if db_url.startswith("postgresql+psycopg://"):
                db_url = db_url.replace("postgresql+psycopg://", "postgresql://")
            
            self.connection_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=10)
        
        return self.connection_pool.acquire()
    
    async def search_hotels(
        self,
        filters: SearchFilters,
        pagination: PaginationParams
    ) -> PaginatedHotelsResponse:
        """Search hotels with filters and pagination"""
        try:
            async with await self.get_connection() as conn:
                # Build WHERE clause
                where_conditions = []
                params = []
                param_count = 0
                
                if filters.search:
                    param_count += 1
                    where_conditions.append(f"(name ILIKE ${param_count} OR address ILIKE ${param_count})")
                    params.append(f"%{filters.search}%")
                
                if filters.min_rating is not None:
                    param_count += 1
                    where_conditions.append(f"rating >= ${param_count}")
                    params.append(filters.min_rating)
                
                if filters.max_rating is not None:
                    param_count += 1
                    where_conditions.append(f"rating <= ${param_count}")
                    params.append(filters.max_rating)
                
                if filters.city:
                    param_count += 1
                    where_conditions.append(f"city ILIKE ${param_count}")
                    params.append(f"%{filters.city}%")
                
                if filters.source_name:
                    param_count += 1
                    where_conditions.append(f"source_name = ${param_count}")
                    params.append(filters.source_name)
                
                if filters.min_price is not None:
                    param_count += 1
                    where_conditions.append(f"price_per_night >= ${param_count}")
                    params.append(filters.min_price)
                
                if filters.max_price is not None:
                    param_count += 1
                    where_conditions.append(f"price_per_night <= ${param_count}")
                    params.append(filters.max_price)
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                # Count total results
                count_query = f"""
                    SELECT COUNT(*) 
                    FROM scraped_hotels 
                    {where_clause};
                """
                
                total = await conn.fetchval(count_query, *params)
                
                # Calculate pagination
                offset = (pagination.page - 1) * pagination.size
                total_pages = (total + pagination.size - 1) // pagination.size
                
                # Get paginated results
                data_query = f"""
                    SELECT id, source_item_id, source_name, name, url, rating, review_count,
                           price_per_night, currency, address, city, image_url, content_hash, scraped_at
                    FROM scraped_hotels 
                    {where_clause}
                    ORDER BY scraped_at DESC, rating DESC NULLS LAST
                    LIMIT ${param_count + 1} OFFSET ${param_count + 2};
                """
                
                params.extend([pagination.size, offset])
                rows = await conn.fetch(data_query, *params)
                
                # Convert to Hotel objects
                hotels = []
                for row in rows:
                    hotel_data = dict(row)
                    hotels.append(Hotel(**hotel_data))
                
                return PaginatedHotelsResponse(
                    items=hotels,
                    total=total,
                    page=pagination.page,
                    size=pagination.size,
                    total_pages=total_pages,
                    has_next=pagination.page < total_pages,
                    has_prev=pagination.page > 1
                )
                
        except Exception as e:
            logger.error(f"Error searching hotels: {e}")
            return PaginatedHotelsResponse(
                items=[],
                total=0,
                page=pagination.page,
                size=pagination.size,
                total_pages=0,
                has_next=False,
                has_prev=False
            )
    
    async def search_restaurants(
        self,
        filters: SearchFilters,
        pagination: PaginationParams
    ) -> PaginatedRestaurantsResponse:
        """Search restaurants with filters and pagination"""
        try:
            async with await self.get_connection() as conn:
                # Build WHERE clause
                where_conditions = []
                params = []
                param_count = 0
                
                if filters.search:
                    param_count += 1
                    where_conditions.append(f"(name ILIKE ${param_count} OR address ILIKE ${param_count})")
                    params.append(f"%{filters.search}%")
                
                if filters.min_rating is not None:
                    param_count += 1
                    where_conditions.append(f"rating >= ${param_count}")
                    params.append(filters.min_rating)
                
                if filters.max_rating is not None:
                    param_count += 1
                    where_conditions.append(f"rating <= ${param_count}")
                    params.append(filters.max_rating)
                
                if filters.city:
                    param_count += 1
                    where_conditions.append(f"city ILIKE ${param_count}")
                    params.append(f"%{filters.city}%")
                
                if filters.source_name:
                    param_count += 1
                    where_conditions.append(f"source_name = ${param_count}")
                    params.append(filters.source_name)
                
                if filters.cuisine_type:
                    param_count += 1
                    where_conditions.append(f"cuisine_type ILIKE ${param_count}")
                    params.append(f"%{filters.cuisine_type}%")
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                # Count total results
                count_query = f"""
                    SELECT COUNT(*) 
                    FROM scraped_restaurants 
                    {where_clause};
                """
                
                total = await conn.fetchval(count_query, *params)
                
                # Calculate pagination
                offset = (pagination.page - 1) * pagination.size
                total_pages = (total + pagination.size - 1) // pagination.size
                
                # Get paginated results
                data_query = f"""
                    SELECT id, source_item_id, source_name, name, url, rating, review_count,
                           cuisine_type, price_range, address, city, image_url, content_hash, scraped_at
                    FROM scraped_restaurants 
                    {where_clause}
                    ORDER BY scraped_at DESC, rating DESC NULLS LAST
                    LIMIT ${param_count + 1} OFFSET ${param_count + 2};
                """
                
                params.extend([pagination.size, offset])
                rows = await conn.fetch(data_query, *params)
                
                # Convert to Restaurant objects
                restaurants = []
                for row in rows:
                    restaurant_data = dict(row)
                    restaurants.append(Restaurant(**restaurant_data))
                
                return PaginatedRestaurantsResponse(
                    items=restaurants,
                    total=total,
                    page=pagination.page,
                    size=pagination.size,
                    total_pages=total_pages,
                    has_next=pagination.page < total_pages,
                    has_prev=pagination.page > 1
                )
                
        except Exception as e:
            logger.error(f"Error searching restaurants: {e}")
            return PaginatedRestaurantsResponse(
                items=[],
                total=0,
                page=pagination.page,
                size=pagination.size,
                total_pages=0,
                has_next=False,
                has_prev=False
            )
    
    async def get_hotel_by_id(self, hotel_id: int) -> Optional[Hotel]:
        """Get hotel by ID"""
        try:
            async with await self.get_connection() as conn:
                query = """
                    SELECT id, source_item_id, source_name, name, url, rating, review_count,
                           price_per_night, currency, address, city, image_url, content_hash, scraped_at
                    FROM scraped_hotels 
                    WHERE id = $1;
                """
                
                row = await conn.fetchrow(query, hotel_id)
                
                if row:
                    return Hotel(**dict(row))
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting hotel by ID {hotel_id}: {e}")
            return None
    
    async def get_restaurant_by_id(self, restaurant_id: int) -> Optional[Restaurant]:
        """Get restaurant by ID"""
        try:
            async with await self.get_connection() as conn:
                query = """
                    SELECT id, source_item_id, source_name, name, url, rating, review_count,
                           cuisine_type, price_range, address, city, image_url, content_hash, scraped_at
                    FROM scraped_restaurants 
                    WHERE id = $1;
                """
                
                row = await conn.fetchrow(query, restaurant_id)
                
                if row:
                    return Restaurant(**dict(row))
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting restaurant by ID {restaurant_id}: {e}")
            return None
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about scraped data"""
        try:
            async with await self.get_connection() as conn:
                # Hotel statistics
                hotel_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_hotels,
                        COUNT(DISTINCT source_name) as hotel_sources,
                        COUNT(DISTINCT city) as hotel_cities,
                        AVG(rating) as avg_hotel_rating,
                        MAX(scraped_at) as last_hotel_scraped
                    FROM scraped_hotels;
                """)
                
                # Restaurant statistics
                restaurant_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_restaurants,
                        COUNT(DISTINCT source_name) as restaurant_sources,
                        COUNT(DISTINCT city) as restaurant_cities,
                        COUNT(DISTINCT cuisine_type) as cuisine_types,
                        AVG(rating) as avg_restaurant_rating,
                        MAX(scraped_at) as last_restaurant_scraped
                    FROM scraped_restaurants;
                """)
                
                return {
                    'hotels': {
                        'total': hotel_stats['total_hotels'],
                        'sources': hotel_stats['hotel_sources'],
                        'cities': hotel_stats['hotel_cities'],
                        'avg_rating': float(hotel_stats['avg_hotel_rating']) if hotel_stats['avg_hotel_rating'] else None,
                        'last_scraped': hotel_stats['last_hotel_scraped'].isoformat() if hotel_stats['last_hotel_scraped'] else None
                    },
                    'restaurants': {
                        'total': restaurant_stats['total_restaurants'],
                        'sources': restaurant_stats['restaurant_sources'],
                        'cities': restaurant_stats['restaurant_cities'],
                        'cuisine_types': restaurant_stats['cuisine_types'],
                        'avg_rating': float(restaurant_stats['avg_restaurant_rating']) if restaurant_stats['avg_restaurant_rating'] else None,
                        'last_scraped': restaurant_stats['last_restaurant_scraped'].isoformat() if restaurant_stats['last_restaurant_scraped'] else None
                    }
                }
                
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'hotels': {'total': 0, 'sources': 0, 'cities': 0, 'avg_rating': None, 'last_scraped': None},
                'restaurants': {'total': 0, 'sources': 0, 'cities': 0, 'cuisine_types': 0, 'avg_rating': None, 'last_scraped': None}
            }
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.connection_pool:
                await self.connection_pool.close()
                logger.info("Scraped data service connection pool closed")
        except Exception as e:
            logger.error(f"Error cleaning up scraped data service: {e}")


# Global instance
scraped_data_service = ScrapedDataService()

-- Migration V009: Create scraped restaurants table
-- This table stores scraped restaurant data

CREATE TABLE IF NOT EXISTS scraped_restaurants (
    id SERIAL PRIMARY KEY,
    -- Unique ID from the source website (e.g., Tabelog's restaurant ID)
    source_item_id VARCHAR(255) NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    name TEXT NOT NULL,
    url VARCHAR(1024) UNIQUE NOT NULL,
    rating FLOAT,
    review_count INTEGER,
    cuisine_type VARCHAR(255),
    price_range VARCHAR(100),
    address TEXT,
    city VARCHAR(255),
    image_url VARCHAR(1024),
    -- A hash of the content to detect changes and prevent duplicates
    content_hash VARCHAR(64) NOT NULL,
    scraped_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_restaurant_source_item UNIQUE (source_item_id, source_name)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_scraped_restaurants_source ON scraped_restaurants(source_name, source_item_id);
CREATE INDEX IF NOT EXISTS idx_scraped_restaurants_city ON scraped_restaurants(city);
CREATE INDEX IF NOT EXISTS idx_scraped_restaurants_rating ON scraped_restaurants(rating DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_restaurants_cuisine ON scraped_restaurants(cuisine_type);
CREATE INDEX IF NOT EXISTS idx_scraped_restaurants_scraped_at ON scraped_restaurants(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_restaurants_name_search ON scraped_restaurants USING gin(to_tsvector('english', name));
CREATE INDEX IF NOT EXISTS idx_scraped_restaurants_address_search ON scraped_restaurants USING gin(to_tsvector('english', address));

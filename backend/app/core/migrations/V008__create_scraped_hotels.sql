-- Migration V008: Create scraped hotels table
-- This table stores scraped hotel/accommodation data

CREATE TABLE IF NOT EXISTS scraped_hotels (
    id SERIAL PRIMARY KEY,
    -- Unique ID from the source website (e.g., Agoda's hotel ID)
    source_item_id VARCHAR(255) NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    name TEXT NOT NULL,
    url VARCHAR(1024) UNIQUE NOT NULL,
    rating FLOAT,
    review_count INTEGER,
    price_per_night DECIMAL(10, 2),
    currency VARCHAR(10),
    address TEXT,
    city VARCHAR(255),
    image_url VARCHAR(1024),
    -- A hash of the content to detect changes and prevent duplicates
    content_hash VARCHAR(64) NOT NULL,
    scraped_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_hotel_source_item UNIQUE (source_item_id, source_name)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_scraped_hotels_source ON scraped_hotels(source_name, source_item_id);
CREATE INDEX IF NOT EXISTS idx_scraped_hotels_city ON scraped_hotels(city);
CREATE INDEX IF NOT EXISTS idx_scraped_hotels_rating ON scraped_hotels(rating DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_hotels_price ON scraped_hotels(price_per_night);
CREATE INDEX IF NOT EXISTS idx_scraped_hotels_scraped_at ON scraped_hotels(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_hotels_name_search ON scraped_hotels USING gin(to_tsvector('english', name));
CREATE INDEX IF NOT EXISTS idx_scraped_hotels_address_search ON scraped_hotels USING gin(to_tsvector('english', address));

-- Migration V007: Create scraping configurations table
-- This table stores and manages scraping source configurations

CREATE TABLE IF NOT EXISTS scraping_configs (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) UNIQUE NOT NULL,
    base_url VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    -- Defines the data structure to be extracted (e.g., {"name": ".css-selector", "rating": ".rating-selector"})
    extraction_schema JSONB NOT NULL,
    -- How often to run the scraper, in hours
    scrape_interval_hours INTEGER DEFAULT 24,
    last_scraped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create index for active sources lookup
CREATE INDEX IF NOT EXISTS idx_scraping_configs_active ON scraping_configs(is_active, source_name);

-- Create index for scheduling lookup
CREATE INDEX IF NOT EXISTS idx_scraping_configs_schedule ON scraping_configs(is_active, last_scraped_at, scrape_interval_hours);

-- Insert initial configuration for Agoda
INSERT INTO scraping_configs (source_name, base_url, extraction_schema, scrape_interval_hours)
VALUES (
    'agoda',
    'https://www.agoda.com',
    '{
        "name": "h1, h2, .hotel-name, [data-selenium*=\"hotel-header-name\"], .HeaderCerebrum__Name, .PropertyHeaderName",
        "rating": ".rating, .score, [data-selenium*=\"review-score\"], .Review-comment-leftScore, .PropertyReviewScore",
        "review_count": ".review-count, .reviews, [data-selenium*=\"review-text\"], .Review-statusBar-text, .PropertyReviewText",
        "price": ".price, .rate, .PropertyCardPrice__Value, .pd-price, [data-selenium*=\"price\"]",
        "address": ".address, .location, [data-selenium*=\"address\"], .hotel-address, .PropertyAddress",
        "image": "img[src*=\"hotel\"], img[src*=\"property\"], .hotel-cover-image img, .PropertyPhotos img"
    }',
    24
) ON CONFLICT (source_name) DO NOTHING;

-- Insert initial configuration for Tabelog
INSERT INTO scraping_configs (source_name, base_url, extraction_schema, scrape_interval_hours)
VALUES (
    'tabelog',
    'https://tabelog.com',
    '{
        "name": ".display-name, h2.display-name, h1",
        "rating": ".rdheader-rating__score-val-dtl, .rdheader-rating__score-val, .c-rating__val",
        "review_count": ".rdheader-rating__review-target em.num, .rdheader-rating__review em.num, .num",
        "cuisine_type": ".rdheader-subinfo__item-text, .rdheader-subinfo__item",
        "price_range": ".rdheader-budget__price-target, .rdheader-budget, .rstinfo-table__budget em",
        "address": ".rstinfo-table__address, .address, .location",
        "image": "img[src*=\"restaurant\"], .js-open-photo img, img"
    }',
    24
) ON CONFLICT (source_name) DO NOTHING;

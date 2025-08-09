-- V010__add_site_specific_search_tables.sql
-- Migration for Milestone 3.2: Site-Specific Search Implementation
-- Creates tables for site-specific search functionality using Jina AI

-- Site-specific search configurations
CREATE TABLE IF NOT EXISTS site_search_configs (
    id SERIAL PRIMARY KEY,
    site_key VARCHAR(100) UNIQUE NOT NULL,
    site_url VARCHAR(500) NOT NULL,
    site_name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    language VARCHAR(10) DEFAULT 'ja',
    country VARCHAR(10) DEFAULT 'JP',
    is_active BOOLEAN DEFAULT true,
    max_results INTEGER DEFAULT 10,
    timeout_seconds INTEGER DEFAULT 30,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial site configurations for the three target sites
INSERT INTO site_search_configs (site_key, site_url, site_name, category, language, country, max_results, timeout_seconds) 
VALUES 
    ('otoriyose.net', 'https://www.otoriyose.net', 'Otoriyose Gourmet Ordering', 'food_ordering', 'ja', 'JP', 10, 30),
    ('ippin.gnavi.co.jp', 'https://ippin.gnavi.co.jp', 'Yamazaki Bread Products', 'bread_products', 'ja', 'JP', 10, 30),
    ('gurusuguri.com', 'https://gurusuguri.com', 'Gurusuguri Premium Food', 'premium_food', 'ja', 'JP', 10, 30)
ON CONFLICT (site_key) DO NOTHING;

-- Site-specific search results storage
CREATE TABLE IF NOT EXISTS site_search_results (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    site_key VARCHAR(100) NOT NULL,
    query TEXT NOT NULL,
    title TEXT,
    url TEXT,
    description TEXT,
    content TEXT,
    metadata JSONB,
    tokens_used INTEGER,
    response_time_ms INTEGER,
    search_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_site_search_results_site_key 
        FOREIGN KEY (site_key) REFERENCES site_search_configs(site_key)
        ON DELETE CASCADE ON UPDATE CASCADE
);

-- Search performance metrics for monitoring and optimization
CREATE TABLE IF NOT EXISTS search_performance_metrics (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    search_type VARCHAR(50) NOT NULL, -- 'general_web', 'site_specific', 'rag', 'hybrid'
    site_key VARCHAR(100), -- NULL for non-site-specific searches
    query TEXT NOT NULL,
    response_time_ms INTEGER,
    results_count INTEGER,
    tokens_used INTEGER,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_search_performance_site_key 
        FOREIGN KEY (site_key) REFERENCES site_search_configs(site_key)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- Create indexes for optimal query performance
CREATE INDEX IF NOT EXISTS idx_site_search_configs_site_key ON site_search_configs(site_key);
CREATE INDEX IF NOT EXISTS idx_site_search_configs_active ON site_search_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_site_search_configs_category ON site_search_configs(category);

CREATE INDEX IF NOT EXISTS idx_site_search_results_session_id ON site_search_results(session_id);
CREATE INDEX IF NOT EXISTS idx_site_search_results_site_key ON site_search_results(site_key);
CREATE INDEX IF NOT EXISTS idx_site_search_results_timestamp ON site_search_results(search_timestamp);
CREATE INDEX IF NOT EXISTS idx_site_search_results_query ON site_search_results USING gin(to_tsvector('english', query));

CREATE INDEX IF NOT EXISTS idx_search_performance_session_id ON search_performance_metrics(session_id);
CREATE INDEX IF NOT EXISTS idx_search_performance_type ON search_performance_metrics(search_type);
CREATE INDEX IF NOT EXISTS idx_search_performance_site_key ON search_performance_metrics(site_key);
CREATE INDEX IF NOT EXISTS idx_search_performance_timestamp ON search_performance_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_search_performance_success ON search_performance_metrics(success);

-- Create a view for easy access to active site configurations
CREATE OR REPLACE VIEW active_site_configs AS
SELECT 
    site_key,
    site_url,
    site_name,
    category,
    language,
    country,
    max_results,
    timeout_seconds
FROM site_search_configs 
WHERE is_active = true
ORDER BY site_name;

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_site_config_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
DROP TRIGGER IF EXISTS trigger_update_site_config_updated_at ON site_search_configs;
CREATE TRIGGER trigger_update_site_config_updated_at
    BEFORE UPDATE ON site_search_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_site_config_updated_at();

-- Add comments for documentation
COMMENT ON TABLE site_search_configs IS 'Configuration for site-specific search targets using Jina AI';
COMMENT ON TABLE site_search_results IS 'Storage for site-specific search results and metadata';
COMMENT ON TABLE search_performance_metrics IS 'Performance monitoring for all search types including site-specific';

COMMENT ON COLUMN site_search_configs.site_key IS 'Unique identifier for the site (e.g., otoriyose.net)';
COMMENT ON COLUMN site_search_configs.site_url IS 'Base URL for the target site';
COMMENT ON COLUMN site_search_configs.category IS 'Category classification for the site (e.g., food_ordering)';
COMMENT ON COLUMN site_search_results.metadata IS 'JSON metadata from Jina AI response including usage info';
COMMENT ON COLUMN search_performance_metrics.search_type IS 'Type of search performed: general_web, site_specific, rag, or hybrid';

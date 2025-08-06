-- Migration V003: Create source_reliability table
-- This table tracks reliability scores and feedback for different information sources
-- Created: 2025-01-31

CREATE TABLE IF NOT EXISTS source_reliability (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    reliability_score FLOAT DEFAULT 0.5,
    total_citations INTEGER DEFAULT 0,
    positive_feedback INTEGER DEFAULT 0,
    negative_feedback INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW(),
    
    -- Add constraints
    CONSTRAINT chk_reliability_score_range CHECK (reliability_score >= 0.0 AND reliability_score <= 1.0),
    CONSTRAINT chk_total_citations_positive CHECK (total_citations >= 0),
    CONSTRAINT chk_positive_feedback_positive CHECK (positive_feedback >= 0),
    CONSTRAINT chk_negative_feedback_positive CHECK (negative_feedback >= 0),
    CONSTRAINT chk_feedback_consistency CHECK (positive_feedback + negative_feedback <= total_citations * 2)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_source_reliability_domain ON source_reliability(domain);
CREATE INDEX IF NOT EXISTS idx_source_reliability_score ON source_reliability(reliability_score);
CREATE INDEX IF NOT EXISTS idx_source_reliability_last_updated ON source_reliability(last_updated);

-- Add comments for documentation
COMMENT ON TABLE source_reliability IS 'Tracks reliability scores and user feedback for information sources';
COMMENT ON COLUMN source_reliability.domain IS 'Domain name of the information source (e.g., wikipedia.org)';
COMMENT ON COLUMN source_reliability.reliability_score IS 'Calculated reliability score between 0.0 and 1.0';
COMMENT ON COLUMN source_reliability.total_citations IS 'Total number of times this source has been cited';
COMMENT ON COLUMN source_reliability.positive_feedback IS 'Number of positive feedback instances';
COMMENT ON COLUMN source_reliability.negative_feedback IS 'Number of negative feedback instances';
COMMENT ON COLUMN source_reliability.last_updated IS 'Timestamp of last score update';

-- Insert default source reliability scores for common domains
INSERT INTO source_reliability (domain, reliability_score, total_citations, positive_feedback, negative_feedback) VALUES
    ('wikipedia.org', 0.9, 100, 85, 10),
    ('github.com', 0.8, 50, 40, 8),
    ('stackoverflow.com', 0.8, 75, 60, 12),
    ('arxiv.org', 0.95, 30, 28, 1),
    ('nature.com', 0.95, 25, 24, 1),
    ('sciencedirect.com', 0.9, 20, 18, 2),
    ('pubmed.ncbi.nlm.nih.gov', 0.95, 15, 14, 1),
    ('reuters.com', 0.85, 40, 32, 6),
    ('bbc.com', 0.85, 35, 28, 5),
    ('cnn.com', 0.75, 30, 22, 7),
    ('medium.com', 0.7, 45, 30, 12),
    ('reddit.com', 0.6, 60, 30, 25),
    ('quora.com', 0.65, 35, 20, 12)
ON CONFLICT (domain) DO NOTHING;

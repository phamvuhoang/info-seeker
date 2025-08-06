-- Migration V004: Create search_feedback table
-- This table collects user feedback on search results to improve system performance
-- Created: 2025-01-31

CREATE TABLE IF NOT EXISTS search_feedback (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    query TEXT NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    sources_helpful JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Additional fields for enhanced feedback tracking
    response_quality_score FLOAT,
    response_accuracy_score FLOAT,
    response_completeness_score FLOAT,
    user_agent TEXT,
    ip_address INET,
    
    -- Add constraints
    CONSTRAINT chk_rating_range CHECK (rating >= 1 AND rating <= 5),
    CONSTRAINT chk_quality_score_range CHECK (response_quality_score IS NULL OR (response_quality_score >= 0.0 AND response_quality_score <= 1.0)),
    CONSTRAINT chk_accuracy_score_range CHECK (response_accuracy_score IS NULL OR (response_accuracy_score >= 0.0 AND response_accuracy_score <= 1.0)),
    CONSTRAINT chk_completeness_score_range CHECK (response_completeness_score IS NULL OR (response_completeness_score >= 0.0 AND response_completeness_score <= 1.0)),
    
    -- Foreign key to user sessions (soft reference, allows orphaned feedback)
    CONSTRAINT fk_search_feedback_session FOREIGN KEY (session_id) REFERENCES user_sessions(session_id) ON DELETE SET NULL
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_search_feedback_session_id ON search_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_search_feedback_rating ON search_feedback(rating);
CREATE INDEX IF NOT EXISTS idx_search_feedback_created_at ON search_feedback(created_at);
CREATE INDEX IF NOT EXISTS idx_search_feedback_query ON search_feedback USING gin(to_tsvector('english', query));

-- Composite index for analytics queries
CREATE INDEX IF NOT EXISTS idx_search_feedback_rating_created ON search_feedback(rating, created_at);

-- Add comments for documentation
COMMENT ON TABLE search_feedback IS 'User feedback on search results for system improvement and analytics';
COMMENT ON COLUMN search_feedback.session_id IS 'Reference to the user session that provided feedback';
COMMENT ON COLUMN search_feedback.query IS 'The original search query that was evaluated';
COMMENT ON COLUMN search_feedback.rating IS 'Overall rating from 1 (poor) to 5 (excellent)';
COMMENT ON COLUMN search_feedback.feedback_text IS 'Optional text feedback from the user';
COMMENT ON COLUMN search_feedback.sources_helpful IS 'JSON array of sources the user found helpful';
COMMENT ON COLUMN search_feedback.response_quality_score IS 'Automated quality assessment score';
COMMENT ON COLUMN search_feedback.response_accuracy_score IS 'Automated accuracy assessment score';
COMMENT ON COLUMN search_feedback.response_completeness_score IS 'Automated completeness assessment score';
COMMENT ON COLUMN search_feedback.user_agent IS 'Browser user agent string for analytics';
COMMENT ON COLUMN search_feedback.ip_address IS 'User IP address for analytics (anonymized)';

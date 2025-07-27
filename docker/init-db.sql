-- Initialize InfoSeeker database with PgVector extension

-- Create the vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create enhanced documents table for vector storage
CREATE TABLE IF NOT EXISTS infoseeker_documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    embedding vector(3072),  -- text-embedding-3-large dimensions
    content_hash VARCHAR(32) UNIQUE,
    source_type VARCHAR(50) NOT NULL DEFAULT 'unknown',
    indexed_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_content_hash UNIQUE (content_hash)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON infoseeker_documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_documents_source_type ON infoseeker_documents (source_type);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON infoseeker_documents USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_documents_indexed_at ON infoseeker_documents (indexed_at);

-- Create user sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_data JSONB DEFAULT '{}',
    last_activity TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create source reliability scores table
CREATE TABLE IF NOT EXISTS source_scores (
    domain VARCHAR(255) PRIMARY KEY,
    reliability_score FLOAT DEFAULT 0.5,
    user_feedback_count INTEGER DEFAULT 0,
    positive_feedback INTEGER DEFAULT 0,
    negative_feedback INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Agent workflow sessions
CREATE TABLE IF NOT EXISTS agent_workflow_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    workflow_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    result JSONB DEFAULT '{}'
);

-- Agent execution logs
CREATE TABLE IF NOT EXISTS agent_execution_logs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL,
    step_name VARCHAR(255),
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    error_message TEXT,
    execution_time_ms INTEGER,
    FOREIGN KEY (session_id) REFERENCES agent_workflow_sessions(session_id)
);

-- Source reliability tracking
CREATE TABLE IF NOT EXISTS source_reliability (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    reliability_score FLOAT DEFAULT 0.5,
    total_citations INTEGER DEFAULT 0,
    positive_feedback INTEGER DEFAULT 0,
    negative_feedback INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW()
);

-- User feedback on search results
CREATE TABLE IF NOT EXISTS search_feedback (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    query TEXT NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    sources_helpful JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create search history table
CREATE TABLE IF NOT EXISTS search_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255),
    query TEXT NOT NULL,
    response TEXT,
    sources JSONB DEFAULT '[]',
    processing_time FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES user_sessions(session_id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_user_sessions_last_activity ON user_sessions(last_activity);
CREATE INDEX IF NOT EXISTS idx_search_history_session_id ON search_history(session_id);
CREATE INDEX IF NOT EXISTS idx_search_history_created_at ON search_history(created_at);
CREATE INDEX IF NOT EXISTS idx_source_scores_reliability ON source_scores(reliability_score);

-- Insert some default source reliability scores
INSERT INTO source_scores (domain, reliability_score, user_feedback_count) VALUES
    ('wikipedia.org', 0.9, 100),
    ('github.com', 0.8, 50),
    ('stackoverflow.com', 0.8, 75),
    ('arxiv.org', 0.95, 30),
    ('nature.com', 0.95, 25),
    ('sciencedirect.com', 0.9, 20),
    ('pubmed.ncbi.nlm.nih.gov', 0.95, 15),
    ('reuters.com', 0.85, 40),
    ('bbc.com', 0.85, 35),
    ('cnn.com', 0.75, 30)
ON CONFLICT (domain) DO NOTHING;

-- Initialize InfoSeeker database with PgVector extension

-- Create the vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create documents table for vector storage
CREATE TABLE IF NOT EXISTS infoseeker_documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS infoseeker_documents_embedding_idx 
ON infoseeker_documents USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

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

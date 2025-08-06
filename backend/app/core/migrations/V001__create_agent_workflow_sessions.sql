-- Migration V001: Create agent_workflow_sessions table
-- This table tracks multi-agent workflow execution sessions
-- Created: 2025-01-31

CREATE TABLE IF NOT EXISTS agent_workflow_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    workflow_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    result JSONB DEFAULT '{}',
    
    -- Add constraints
    CONSTRAINT chk_workflow_status CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT chk_completed_at_after_started CHECK (completed_at IS NULL OR completed_at >= started_at)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_agent_workflow_sessions_session_id ON agent_workflow_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_workflow_sessions_status ON agent_workflow_sessions(status);
CREATE INDEX IF NOT EXISTS idx_agent_workflow_sessions_started_at ON agent_workflow_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_agent_workflow_sessions_workflow_name ON agent_workflow_sessions(workflow_name);

-- Add comments for documentation
COMMENT ON TABLE agent_workflow_sessions IS 'Tracks multi-agent workflow execution sessions with status and results';
COMMENT ON COLUMN agent_workflow_sessions.session_id IS 'Unique identifier for the workflow session';
COMMENT ON COLUMN agent_workflow_sessions.workflow_name IS 'Name of the workflow being executed';
COMMENT ON COLUMN agent_workflow_sessions.status IS 'Current status of the workflow execution';
COMMENT ON COLUMN agent_workflow_sessions.metadata IS 'Additional metadata about the workflow execution';
COMMENT ON COLUMN agent_workflow_sessions.result IS 'Final result data from the workflow execution';

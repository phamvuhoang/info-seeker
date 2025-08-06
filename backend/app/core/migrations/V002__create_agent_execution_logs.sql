-- Migration V002: Create agent_execution_logs table
-- This table tracks detailed execution logs for individual agents within workflows
-- Created: 2025-01-31

-- Check if table exists and create only if it doesn't
DO $$
BEGIN
    -- Check if the table exists
    IF NOT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'agent_execution_logs'
    ) THEN
        -- Create the table
        CREATE TABLE agent_execution_logs (
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

            -- Add constraints
            CONSTRAINT chk_agent_status CHECK (status IN ('started', 'completed', 'failed', 'cancelled')),
            CONSTRAINT chk_execution_completed_at_after_started CHECK (completed_at IS NULL OR completed_at >= started_at),
            CONSTRAINT chk_execution_time_positive CHECK (execution_time_ms IS NULL OR execution_time_ms >= 0)
        );
    ELSE
        -- Table exists, ensure it has the correct structure
        -- Add missing columns if they don't exist
        IF NOT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'agent_execution_logs'
            AND column_name = 'execution_time_ms'
        ) THEN
            ALTER TABLE agent_execution_logs ADD COLUMN execution_time_ms INTEGER;
        END IF;

        -- Ensure constraints exist (this will fail silently if they already exist)
        BEGIN
            ALTER TABLE agent_execution_logs ADD CONSTRAINT chk_agent_status CHECK (status IN ('started', 'completed', 'failed', 'cancelled'));
        EXCEPTION WHEN duplicate_object THEN
            -- Constraint already exists, ignore
        END;

        BEGIN
            ALTER TABLE agent_execution_logs ADD CONSTRAINT chk_execution_completed_at_after_started CHECK (completed_at IS NULL OR completed_at >= started_at);
        EXCEPTION WHEN duplicate_object THEN
            -- Constraint already exists, ignore
        END;

        BEGIN
            ALTER TABLE agent_execution_logs ADD CONSTRAINT chk_execution_time_positive CHECK (execution_time_ms IS NULL OR execution_time_ms >= 0);
        EXCEPTION WHEN duplicate_object THEN
            -- Constraint already exists, ignore
        END;
    END IF;
END $$;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_agent_execution_logs_session_id ON agent_execution_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_execution_logs_agent_name ON agent_execution_logs(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_execution_logs_status ON agent_execution_logs(status);
CREATE INDEX IF NOT EXISTS idx_agent_execution_logs_started_at ON agent_execution_logs(started_at);
CREATE INDEX IF NOT EXISTS idx_agent_execution_logs_step_name ON agent_execution_logs(step_name);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_agent_execution_logs_session_agent ON agent_execution_logs(session_id, agent_name);

-- Add comments for documentation
COMMENT ON TABLE agent_execution_logs IS 'Detailed execution logs for individual agents within multi-agent workflows';
COMMENT ON COLUMN agent_execution_logs.session_id IS 'Reference to the workflow session';
COMMENT ON COLUMN agent_execution_logs.agent_name IS 'Name of the agent that executed this step';
COMMENT ON COLUMN agent_execution_logs.step_name IS 'Name of the specific step or operation';
COMMENT ON COLUMN agent_execution_logs.status IS 'Execution status of this agent step';
COMMENT ON COLUMN agent_execution_logs.input_data IS 'Input data provided to the agent';
COMMENT ON COLUMN agent_execution_logs.output_data IS 'Output data produced by the agent';
COMMENT ON COLUMN agent_execution_logs.error_message IS 'Error message if execution failed';
COMMENT ON COLUMN agent_execution_logs.execution_time_ms IS 'Execution time in milliseconds';

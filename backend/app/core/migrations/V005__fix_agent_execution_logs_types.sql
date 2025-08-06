-- Migration V005: Fix agent_execution_logs table type inconsistencies
-- This migration addresses type mismatches that cause parameter type errors
-- Created: 2025-01-31

-- Fix any type inconsistencies in the agent_execution_logs table
DO $$
BEGIN
    -- Check if the table exists
    IF EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'agent_execution_logs'
    ) THEN
        -- Ensure all columns have the correct types
        
        -- Fix session_id type if needed
        IF EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'agent_execution_logs' 
            AND column_name = 'session_id'
            AND data_type != 'character varying'
        ) THEN
            ALTER TABLE agent_execution_logs ALTER COLUMN session_id TYPE VARCHAR(255);
        END IF;
        
        -- Fix agent_name type if needed
        IF EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'agent_execution_logs' 
            AND column_name = 'agent_name'
            AND data_type != 'character varying'
        ) THEN
            ALTER TABLE agent_execution_logs ALTER COLUMN agent_name TYPE VARCHAR(255);
        END IF;
        
        -- Fix step_name type if needed
        IF EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'agent_execution_logs' 
            AND column_name = 'step_name'
            AND data_type != 'character varying'
        ) THEN
            ALTER TABLE agent_execution_logs ALTER COLUMN step_name TYPE VARCHAR(255);
        END IF;
        
        -- Fix status type if needed (this is likely the problematic column)
        IF EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'agent_execution_logs' 
            AND column_name = 'status'
            AND data_type != 'character varying'
        ) THEN
            ALTER TABLE agent_execution_logs ALTER COLUMN status TYPE VARCHAR(50);
        END IF;
        
        -- Fix error_message type if needed
        IF EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'agent_execution_logs' 
            AND column_name = 'error_message'
            AND data_type != 'text'
        ) THEN
            ALTER TABLE agent_execution_logs ALTER COLUMN error_message TYPE TEXT;
        END IF;
        
        -- Ensure execution_time_ms is integer
        IF EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'agent_execution_logs' 
            AND column_name = 'execution_time_ms'
            AND data_type != 'integer'
        ) THEN
            ALTER TABLE agent_execution_logs ALTER COLUMN execution_time_ms TYPE INTEGER;
        END IF;
        
        RAISE NOTICE 'Fixed agent_execution_logs table types';
    ELSE
        RAISE NOTICE 'agent_execution_logs table does not exist, skipping type fixes';
    END IF;
END $$;

-- Ensure indexes exist for better performance
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

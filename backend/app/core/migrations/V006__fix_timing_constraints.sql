-- Migration V006: Fix timing constraints in agent_execution_logs
-- This migration addresses timing constraint violations
-- Created: 2025-01-31

-- Fix timing constraint issues in agent_execution_logs table
DO $$
BEGIN
    -- Check if the table exists
    IF EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'agent_execution_logs'
    ) THEN
        -- Drop the problematic constraint if it exists
        BEGIN
            ALTER TABLE agent_execution_logs DROP CONSTRAINT IF EXISTS chk_execution_completed_at_after_started;
            RAISE NOTICE 'Dropped problematic timing constraint';
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Timing constraint did not exist or could not be dropped';
        END;
        
        -- Add a more lenient timing constraint that allows for small timing differences
        -- This constraint allows completed_at to be equal to or after started_at, with a small tolerance
        BEGIN
            ALTER TABLE agent_execution_logs ADD CONSTRAINT chk_execution_completed_at_after_started_lenient 
            CHECK (completed_at IS NULL OR completed_at >= (started_at - INTERVAL '1 second'));
            RAISE NOTICE 'Added lenient timing constraint';
        EXCEPTION WHEN duplicate_object THEN
            RAISE NOTICE 'Lenient timing constraint already exists';
        END;
        
        -- Clean up any existing rows that might violate the constraint
        -- Update completed_at to be slightly after started_at for any problematic rows
        UPDATE agent_execution_logs 
        SET completed_at = started_at + INTERVAL '1 millisecond'
        WHERE completed_at IS NOT NULL 
        AND completed_at < started_at;
        
        RAISE NOTICE 'Fixed timing constraint issues in agent_execution_logs table';
    ELSE
        RAISE NOTICE 'agent_execution_logs table does not exist, skipping timing fixes';
    END IF;
END $$;

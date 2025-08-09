#!/usr/bin/env python3
"""
Migration runner script for InfoSeeker
Runs the V010 migration to create site-specific search tables
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.core.migrations import MigrationManager

async def main():
    """Run the database migrations"""
    print("🚀 Starting InfoSeeker database migration...")
    
    migration_manager = MigrationManager()
    
    try:
        success = await migration_manager.run_migrations()
        
        if success:
            print("✅ All migrations completed successfully!")
            print("📊 Site-specific search tables are now ready:")
            print("   - site_search_configs")
            print("   - site_search_results") 
            print("   - search_performance_metrics")
            return 0
        else:
            print("❌ Migration failed. Check the logs for details.")
            return 1
            
    except Exception as e:
        print(f"💥 Migration error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

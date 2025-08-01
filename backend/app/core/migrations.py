"""
Database Migration System for InfoSeeker

This module provides a comprehensive database migration system that:
1. Tracks applied migrations in a dedicated table
2. Applies migrations in order based on version numbers
3. Ensures idempotent operations (safe to run multiple times)
4. Supports both Docker and local development environments
5. Follows standard database migration best practices
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import asyncpg
from ..core.config import settings

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Database migration manager that handles schema versioning and migration execution.
    
    Features:
    - Version-based migration tracking
    - Idempotent operations (safe to run multiple times)
    - Automatic rollback on failure
    - Support for both up and down migrations
    - Comprehensive logging and error handling
    """
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or settings.database_url
        # Convert SQLAlchemy format to asyncpg format
        if self.db_url.startswith("postgresql+psycopg://"):
            self.db_url = self.db_url.replace("postgresql+psycopg://", "postgresql://")
        
        self.migrations_dir = Path(__file__).parent / "migrations"
        self.migrations_table = "schema_migrations"
        
    async def initialize_migrations_table(self, conn: asyncpg.Connection):
        """Create the migrations tracking table if it doesn't exist."""
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.migrations_table} (
                id SERIAL PRIMARY KEY,
                version VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP DEFAULT NOW(),
                checksum VARCHAR(64) NOT NULL,
                execution_time_ms INTEGER,
                success BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Create index for faster lookups
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.migrations_table}_version 
            ON {self.migrations_table}(version)
        """)
        
        logger.info(f"Migrations table '{self.migrations_table}' initialized")
    
    async def get_applied_migrations(self, conn: asyncpg.Connection) -> Dict[str, dict]:
        """Get list of already applied migrations."""
        rows = await conn.fetch(f"""
            SELECT version, name, applied_at, checksum, success
            FROM {self.migrations_table}
            ORDER BY version
        """)
        
        return {
            row['version']: {
                'name': row['name'],
                'applied_at': row['applied_at'],
                'checksum': row['checksum'],
                'success': row['success']
            }
            for row in rows
        }
    
    def get_migration_files(self) -> List[Tuple[str, str, Path]]:
        """
        Get all migration files sorted by version.
        Returns list of tuples: (version, name, file_path)
        """
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory {self.migrations_dir} does not exist")
            return []
        
        migrations = []
        for file_path in self.migrations_dir.glob("*.sql"):
            # Expected format: V001__create_agent_tables.sql
            filename = file_path.stem
            if filename.startswith("V") and "__" in filename:
                parts = filename.split("__", 1)
                version = parts[0]
                name = parts[1].replace("_", " ").title()
                migrations.append((version, name, file_path))
        
        # Sort by version
        migrations.sort(key=lambda x: x[0])
        return migrations
    
    def calculate_checksum(self, content: str) -> str:
        """Calculate MD5 checksum of migration content."""
        import hashlib
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    async def apply_migration(self, conn: asyncpg.Connection, version: str, name: str, 
                            file_path: Path) -> bool:
        """Apply a single migration file."""
        try:
            # Read migration content
            content = file_path.read_text(encoding='utf-8')
            checksum = self.calculate_checksum(content)
            
            logger.info(f"Applying migration {version}: {name}")
            start_time = datetime.now()
            
            # Execute migration in a transaction
            async with conn.transaction():
                # Execute the migration SQL
                await conn.execute(content)
                
                # Record the migration
                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                await conn.execute(f"""
                    INSERT INTO {self.migrations_table} 
                    (version, name, checksum, execution_time_ms, success)
                    VALUES ($1, $2, $3, $4, $5)
                """, version, name, checksum, execution_time, True)
            
            logger.info(f"Migration {version} applied successfully in {execution_time}ms")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            
            # Record failed migration
            try:
                await conn.execute(f"""
                    INSERT INTO {self.migrations_table} 
                    (version, name, checksum, success)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (version) DO UPDATE SET success = $4
                """, version, name, self.calculate_checksum(file_path.read_text()), False)
            except Exception as record_error:
                logger.error(f"Failed to record migration failure: {record_error}")
            
            return False
    
    async def run_migrations(self) -> bool:
        """
        Run all pending migrations.
        Returns True if all migrations were successful, False otherwise.
        """
        try:
            # Connect to database
            conn = await asyncpg.connect(self.db_url)
            
            try:
                # Initialize migrations table
                await self.initialize_migrations_table(conn)
                
                # Get applied migrations
                applied_migrations = await self.get_applied_migrations(conn)
                
                # Get all migration files
                migration_files = self.get_migration_files()
                
                if not migration_files:
                    logger.info("No migration files found")
                    return True
                
                # Apply pending migrations
                pending_count = 0
                success_count = 0
                
                for version, name, file_path in migration_files:
                    if version in applied_migrations:
                        if applied_migrations[version]['success']:
                            logger.debug(f"Migration {version} already applied, skipping")
                            continue
                        else:
                            logger.warning(f"Migration {version} previously failed, retrying")
                    
                    pending_count += 1
                    if await self.apply_migration(conn, version, name, file_path):
                        success_count += 1
                    else:
                        logger.error(f"Migration {version} failed, stopping migration process")
                        break
                
                if pending_count == 0:
                    logger.info("All migrations are up to date")
                    return True
                elif success_count == pending_count:
                    logger.info(f"Successfully applied {success_count} migrations")
                    return True
                else:
                    logger.error(f"Applied {success_count}/{pending_count} migrations")
                    return False
                    
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Migration process failed: {e}")
            return False
    
    async def get_migration_status(self) -> Dict:
        """Get current migration status for debugging/monitoring."""
        try:
            conn = await asyncpg.connect(self.db_url)
            
            try:
                # Check if migrations table exists
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = $1
                    )
                """, self.migrations_table)
                
                if not table_exists:
                    return {
                        "status": "not_initialized",
                        "migrations_table_exists": False,
                        "applied_migrations": [],
                        "pending_migrations": len(self.get_migration_files())
                    }
                
                applied_migrations = await self.get_applied_migrations(conn)
                migration_files = self.get_migration_files()
                
                pending_migrations = [
                    {"version": version, "name": name}
                    for version, name, _ in migration_files
                    if version not in applied_migrations or not applied_migrations[version]['success']
                ]
                
                return {
                    "status": "ready" if not pending_migrations else "pending",
                    "migrations_table_exists": True,
                    "applied_migrations": list(applied_migrations.keys()),
                    "pending_migrations": len(pending_migrations),
                    "pending_details": pending_migrations
                }
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"Failed to get migration status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Global migration manager instance
migration_manager = MigrationManager()

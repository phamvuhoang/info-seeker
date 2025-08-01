from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional, Union
import asyncpg
import logging
from ..core.config import settings
from ..core.migrations import migration_manager
from pydantic import BaseModel
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Optional[str] = None


class TableInfo(BaseModel):
    table_name: str
    row_count: int
    columns: List[ColumnInfo]
    description: Optional[str] = None


class TableDataResponse(BaseModel):
    table_name: str
    columns: List[str]
    data: List[Dict[str, Any]]
    total_rows: int
    page: int
    page_size: int
    total_pages: int


class UpdateRowRequest(BaseModel):
    row_data: Dict[str, Any]


class DeleteRowResponse(BaseModel):
    success: bool
    message: str


class UpdateRowResponse(BaseModel):
    success: bool
    message: str
    updated_row: Optional[Dict[str, Any]] = None


class DatabaseConnection:
    """Database connection manager for database viewer operations"""
    
    def __init__(self):
        self.connection_pool = None
    
    async def get_connection(self):
        """Get database connection"""
        if not self.connection_pool:
            # Parse database URL to get connection parameters
            db_url = settings.database_url
            # Convert from SQLAlchemy format to asyncpg format
            if db_url.startswith("postgresql+psycopg://"):
                db_url = db_url.replace("postgresql+psycopg://", "postgresql://")
            
            self.connection_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)
        
        return self.connection_pool.acquire()


db_manager = DatabaseConnection()


@router.get("/tables", response_model=List[TableInfo])
async def list_tables():
    """Get list of all database tables with basic information"""
    try:
        async with await db_manager.get_connection() as conn:
            # Get all tables in the public schema
            tables_query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """
            
            table_names = await conn.fetch(tables_query)
            table_info_list = []
            
            for table_record in table_names:
                table_name = table_record['table_name']
                
                # Get row count
                count_query = f"SELECT COUNT(*) as count FROM {table_name};"
                count_result = await conn.fetchrow(count_query)
                row_count = count_result['count']
                
                # Get column information
                columns_query = """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position;
                """
                
                columns = await conn.fetch(columns_query, table_name)
                column_info = [
                    ColumnInfo(
                        name=col['column_name'],
                        type=col['data_type'],
                        nullable=col['is_nullable'] == 'YES',
                        default=col['column_default']
                    )
                    for col in columns
                ]
                
                # Add description based on table name
                descriptions = {
                    'infoseeker_documents': 'Vector documents with embeddings for RAG search',
                    'user_sessions': 'User session tracking and data',
                    'source_scores': 'Source reliability scores and feedback',
                    'agent_workflow_sessions': 'Agent workflow execution sessions',
                    'agent_execution_logs': 'Detailed agent execution logs',
                    'source_reliability': 'Source reliability tracking',
                    'search_feedback': 'User feedback on search results',
                    'search_history': 'Search query history and responses'
                }
                
                table_info = TableInfo(
                    table_name=table_name,
                    row_count=row_count,
                    columns=column_info,
                    description=descriptions.get(table_name, f"Database table: {table_name}")
                )
                
                table_info_list.append(table_info)
            
            logger.info(f"Retrieved information for {len(table_info_list)} tables")
            return table_info_list
            
    except Exception as e:
        logger.error(f"Failed to list tables: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve table information: {str(e)}")


@router.get("/tables/{table_name}/data", response_model=TableDataResponse)
async def get_table_data(
    table_name: str,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Number of rows per page"),
    sort_by: Optional[str] = Query(None, description="Column to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    search: Optional[str] = Query(None, description="Search term for text columns")
):
    """Get paginated data from a specific table"""
    try:
        async with await db_manager.get_connection() as conn:
            # Verify table exists
            table_exists_query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = $1
                );
            """

            table_exists = await conn.fetchval(table_exists_query, table_name)
            if not table_exists:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

            # Get column information
            columns_query = """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position;
            """

            columns = await conn.fetch(columns_query, table_name)
            column_names = [col['column_name'] for col in columns]
            column_types = {col['column_name']: col['data_type'] for col in columns}

            # Build WHERE clause for search
            where_clause = ""
            search_params = []
            param_count = 1

            if search:
                # Search in text columns
                text_columns = [
                    col['column_name'] for col in columns
                    if col['data_type'] in ['text', 'character varying', 'varchar']
                ]

                if text_columns:
                    search_conditions = []
                    for col in text_columns:
                        search_conditions.append(f"{col}::text ILIKE ${param_count}")
                        search_params.append(f"%{search}%")
                        param_count += 1

                    where_clause = f"WHERE {' OR '.join(search_conditions)}"

            # Build ORDER BY clause
            order_clause = ""
            if sort_by and sort_by in column_names:
                order_clause = f"ORDER BY {sort_by} {sort_order.upper()}"
            elif 'id' in column_names:
                order_clause = "ORDER BY id ASC"
            elif 'created_at' in column_names:
                order_clause = "ORDER BY created_at DESC"

            # Get total count
            count_query = f"SELECT COUNT(*) as count FROM {table_name} {where_clause};"
            total_rows = await conn.fetchval(count_query, *search_params)

            # Calculate pagination
            offset = (page - 1) * page_size
            total_pages = (total_rows + page_size - 1) // page_size

            # Get data
            data_query = f"""
                SELECT * FROM {table_name}
                {where_clause}
                {order_clause}
                LIMIT {page_size} OFFSET {offset};
            """

            rows = await conn.fetch(data_query, *search_params)

            # Convert rows to dictionaries with proper JSON serialization
            data = []
            for row in rows:
                row_dict = {}
                for col_name in column_names:
                    value = row[col_name]

                    # Handle special data types
                    if value is None:
                        row_dict[col_name] = None
                    elif isinstance(value, datetime):
                        row_dict[col_name] = value.isoformat()
                    elif column_types[col_name] == 'jsonb':
                        row_dict[col_name] = value if isinstance(value, (dict, list)) else json.loads(str(value))
                    elif column_types[col_name] == 'vector':
                        # Convert vector to list for JSON serialization
                        row_dict[col_name] = f"Vector({len(str(value).split(','))} dimensions)" if value else None
                    else:
                        row_dict[col_name] = value

                data.append(row_dict)

            response = TableDataResponse(
                table_name=table_name,
                columns=column_names,
                data=data,
                total_rows=total_rows,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )

            logger.info(f"Retrieved {len(data)} rows from {table_name} (page {page}/{total_pages})")
            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get table data for {table_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve table data: {str(e)}")


@router.delete("/tables/{table_name}/rows/{row_id}", response_model=DeleteRowResponse)
async def delete_row(table_name: str, row_id: str):
    """Delete a row from a table by ID"""
    try:
        async with await db_manager.get_connection() as conn:
            # Verify table exists
            table_exists_query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = $1
                );
            """

            table_exists = await conn.fetchval(table_exists_query, table_name)
            if not table_exists:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

            # Check if table has an 'id' column
            id_column_query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1 AND column_name = 'id'
                );
            """

            has_id_column = await conn.fetchval(id_column_query, table_name)
            if not has_id_column:
                raise HTTPException(status_code=400, detail=f"Table '{table_name}' does not have an 'id' column for deletion")

            # Delete the row
            delete_query = f"DELETE FROM {table_name} WHERE id = $1 RETURNING id;"

            try:
                # Convert row_id to appropriate type (try int first, then string)
                try:
                    row_id_value = int(row_id)
                except ValueError:
                    row_id_value = row_id

                deleted_id = await conn.fetchval(delete_query, row_id_value)

                if deleted_id is None:
                    raise HTTPException(status_code=404, detail=f"Row with id '{row_id}' not found in table '{table_name}'")

                logger.info(f"Deleted row {row_id} from table {table_name}")
                return DeleteRowResponse(
                    success=True,
                    message=f"Successfully deleted row with id {row_id}"
                )

            except Exception as e:
                logger.error(f"Error deleting row {row_id} from {table_name}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to delete row: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete row from {table_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete row: {str(e)}")


@router.put("/tables/{table_name}/rows/{row_id}", response_model=UpdateRowResponse)
async def update_row(table_name: str, row_id: str, update_data: UpdateRowRequest):
    """Update a row in a table by ID"""
    try:
        async with await db_manager.get_connection() as conn:
            # Verify table exists
            table_exists_query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = $1
                );
            """

            table_exists = await conn.fetchval(table_exists_query, table_name)
            if not table_exists:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

            # Check if table has an 'id' column
            id_column_query = """
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1 AND column_name = 'id'
                );
            """

            has_id_column = await conn.fetchval(id_column_query, table_name)
            if not has_id_column:
                raise HTTPException(status_code=400, detail=f"Table '{table_name}' does not have an 'id' column for updates")

            # Get column information to validate update data
            columns_query = """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position;
            """

            columns = await conn.fetch(columns_query, table_name)
            valid_columns = {col['column_name']: col['data_type'] for col in columns}

            # Filter update data to only include valid columns (excluding id)
            filtered_data = {}
            for key, value in update_data.row_data.items():
                if key in valid_columns and key != 'id':
                    # Handle JSON data types
                    if valid_columns[key] == 'jsonb' and isinstance(value, (dict, list)):
                        filtered_data[key] = json.dumps(value)
                    else:
                        filtered_data[key] = value

            if not filtered_data:
                raise HTTPException(status_code=400, detail="No valid columns to update")

            # Build update query
            set_clauses = []
            values = []
            param_count = 1

            for key, value in filtered_data.items():
                set_clauses.append(f"{key} = ${param_count}")
                values.append(value)
                param_count += 1

            # Convert row_id to appropriate type
            try:
                row_id_value = int(row_id)
            except ValueError:
                row_id_value = row_id

            values.append(row_id_value)

            update_query = f"""
                UPDATE {table_name}
                SET {', '.join(set_clauses)}
                WHERE id = ${param_count}
                RETURNING *;
            """

            try:
                updated_row = await conn.fetchrow(update_query, *values)

                if updated_row is None:
                    raise HTTPException(status_code=404, detail=f"Row with id '{row_id}' not found in table '{table_name}'")

                # Convert row to dictionary with proper JSON serialization
                row_dict = {}
                for col_name in valid_columns.keys():
                    value = updated_row[col_name]

                    if value is None:
                        row_dict[col_name] = None
                    elif isinstance(value, datetime):
                        row_dict[col_name] = value.isoformat()
                    elif valid_columns[col_name] == 'jsonb':
                        row_dict[col_name] = value if isinstance(value, (dict, list)) else json.loads(str(value))
                    else:
                        row_dict[col_name] = value

                logger.info(f"Updated row {row_id} in table {table_name}")
                return UpdateRowResponse(
                    success=True,
                    message=f"Successfully updated row with id {row_id}",
                    updated_row=row_dict
                )

            except Exception as e:
                logger.error(f"Error updating row {row_id} in {table_name}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to update row: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update row in {table_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update row: {str(e)}")


@router.get("/migrations/status")
async def get_migration_status():
    """Get the current status of database migrations"""
    try:
        status = await migration_manager.get_migration_status()
        return {
            "success": True,
            "migration_status": status
        }
    except Exception as e:
        logger.error(f"Failed to get migration status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get migration status: {str(e)}")


@router.post("/migrations/run")
async def run_migrations():
    """Manually trigger database migrations"""
    try:
        logger.info("Manual migration run requested")
        success = await migration_manager.run_migrations()

        if success:
            return {
                "success": True,
                "message": "Migrations completed successfully"
            }
        else:
            return {
                "success": False,
                "message": "Some migrations failed - check logs for details"
            }
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run migrations: {str(e)}")

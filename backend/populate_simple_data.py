#!/usr/bin/env python3
"""
Simple script to populate the vector database with sample data using direct SQL
"""

import asyncio
import sys
import os
import json
import hashlib
from datetime import datetime, timezone

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

import psycopg
from app.core.config import settings


async def populate_simple_data():
    """Populate the database with sample documents using direct SQL"""
    
    sample_documents = [
        {
            "content": """
            Ho Chi Minh City (HCMC), formerly known as Saigon, is the largest city in Vietnam and a major economic hub. 
            The city is famous for its vibrant street life, delicious food, and rich history. Key attractions include 
            the War Remnants Museum, Independence Palace, Notre-Dame Cathedral Basilica of Saigon, and the bustling 
            Ben Thanh Market. The city offers a perfect blend of traditional Vietnamese culture and modern urban development.
            """,
            "metadata": {
                "title": "Ho Chi Minh City Overview",
                "source_type": "knowledge_base",
                "category": "travel",
                "location": "Vietnam"
            }
        },
        {
            "content": """
            Top 5 Tourist Attractions in Ho Chi Minh City:
            1. War Remnants Museum - A powerful museum documenting the Vietnam War
            2. Independence Palace (Reunification Palace) - Historic presidential palace
            3. Notre-Dame Cathedral Basilica of Saigon - Beautiful French colonial architecture
            4. Ben Thanh Market - Famous central market for shopping and street food
            5. Cu Chi Tunnels - Historic underground tunnel network (day trip from city)
            """,
            "metadata": {
                "title": "Top 5 HCMC Tourist Spots",
                "source_type": "knowledge_base",
                "category": "travel",
                "location": "Vietnam"
            }
        },
        {
            "content": """
            Artificial Intelligence (AI) has seen remarkable developments in recent years. Key areas include:
            - Large Language Models (LLMs) like GPT-4, Claude, and Gemini
            - Computer Vision advances in image recognition and generation
            - Robotics integration with AI for autonomous systems
            - AI in healthcare for drug discovery and diagnosis
            - Autonomous vehicles and transportation
            - AI ethics and safety research
            """,
            "metadata": {
                "title": "Recent AI Developments",
                "source_type": "knowledge_base",
                "category": "technology",
                "topic": "artificial_intelligence"
            }
        },
        {
            "content": """
            Machine Learning best practices include:
            1. Data Quality - Ensure clean, representative datasets
            2. Feature Engineering - Select and transform relevant features
            3. Model Selection - Choose appropriate algorithms for the problem
            4. Cross-Validation - Use proper validation techniques
            5. Hyperparameter Tuning - Optimize model parameters
            6. Regularization - Prevent overfitting
            7. Model Monitoring - Track performance in production
            """,
            "metadata": {
                "title": "Machine Learning Best Practices",
                "source_type": "knowledge_base",
                "category": "technology",
                "topic": "machine_learning"
            }
        },
        {
            "content": """
            Python programming best practices:
            1. Follow PEP 8 style guidelines
            2. Write clear, descriptive variable and function names
            3. Use type hints for better code documentation
            4. Implement proper error handling with try-except blocks
            5. Write unit tests for your code
            6. Use virtual environments for dependency management
            7. Document your code with docstrings
            8. Keep functions small and focused on single responsibilities
            """,
            "metadata": {
                "title": "Python Programming Best Practices",
                "source_type": "knowledge_base",
                "category": "programming",
                "topic": "python"
            }
        }
    ]
    
    print("Starting to populate sample data using direct SQL...")
    
    try:
        # Fix the database URL format for psycopg
        db_url = settings.database_url.replace('postgresql+psycopg://', 'postgresql://')
        print(f"Connecting to database: {db_url}")
        
        # Connect to database
        conn = await psycopg.AsyncConnection.connect(db_url)
        print("Connected to database successfully")
        
        # Check if table exists
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = %s
            """, (settings.vector_table_name,))
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                print(f"Table {settings.vector_table_name} does not exist. Please create it first.")
                return
            
            print(f"Table {settings.vector_table_name} exists. Proceeding with data insertion...")
            
            # Clear existing data (optional)
            await cursor.execute(f"DELETE FROM {settings.vector_table_name} WHERE meta_data->>'source_type' = 'knowledge_base'")
            deleted_count = cursor.rowcount
            print(f"Deleted {deleted_count} existing knowledge_base documents")
            
            # Insert sample documents
            for i, doc in enumerate(sample_documents, 1):
                content = doc["content"].strip()
                metadata = doc["metadata"]
                
                # Add additional metadata
                metadata['content_hash'] = hashlib.md5(content.encode()).hexdigest()
                metadata['indexed_at'] = datetime.now(timezone.utc).isoformat()
                
                print(f"Inserting document {i}/{len(sample_documents)}: {metadata['title']}")
                
                # Insert without embedding for now (embeddings can be generated later)
                await cursor.execute(f"""
                    INSERT INTO {settings.vector_table_name} (id, name, content, meta_data, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                """, (metadata['content_hash'], metadata['title'], content, json.dumps(metadata)))
            
            # Commit the transaction
            await conn.commit()
            
            # Check final count
            await cursor.execute(f"SELECT COUNT(*) FROM {settings.vector_table_name}")
            total_count = (await cursor.fetchone())[0]
            print(f"\n✅ Successfully inserted {len(sample_documents)} documents!")
            print(f"Total documents in table: {total_count}")
        
        await conn.close()
        print("\n🎉 Sample data population completed successfully!")
        
    except Exception as e:
        print(f"❌ Error populating sample data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(populate_simple_data())

import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from datetime import datetime, timezone
from typing import Dict, Any
from ..scrapers.engine import scraping_engine

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing scheduled scraping tasks"""
    
    def __init__(self):
        self.scheduler = None
        self.is_running = False
    
    def initialize(self):
        """Initialize the scheduler"""
        try:
            # Configure job stores and executors
            jobstores = {
                'default': MemoryJobStore()
            }
            
            executors = {
                'default': AsyncIOExecutor()
            }
            
            job_defaults = {
                'coalesce': False,
                'max_instances': 1,
                'misfire_grace_time': 300  # 5 minutes
            }
            
            # Create scheduler
            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone='UTC'
            )
            
            logger.info("Scheduler initialized")
            
        except Exception as e:
            logger.error(f"Error initializing scheduler: {e}")
            raise
    
    async def start(self):
        """Start the scheduler and add jobs"""
        try:
            if not self.scheduler:
                self.initialize()
            
            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            
            # Add scheduled scraping job
            await self.schedule_scraping_jobs()
            
            logger.info("Scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            raise
    
    async def stop(self):
        """Stop the scheduler"""
        try:
            if self.scheduler and self.is_running:
                self.scheduler.shutdown(wait=True)
                self.is_running = False
                logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    
    async def schedule_scraping_jobs(self):
        """Schedule scraping jobs based on configuration"""
        try:
            # Schedule main scraping job to run every hour
            # This will check which sources are due for scraping
            self.scheduler.add_job(
                func=self.run_scheduled_scraping,
                trigger=IntervalTrigger(hours=1),
                id='scheduled_scraping',
                name='Scheduled Content Scraping',
                replace_existing=True,
                next_run_time=datetime.now(timezone.utc)
            )
            
            # Schedule a daily cleanup job at 2 AM UTC
            self.scheduler.add_job(
                func=self.cleanup_old_data,
                trigger=CronTrigger(hour=2, minute=0),
                id='daily_cleanup',
                name='Daily Data Cleanup',
                replace_existing=True
            )
            
            logger.info("Scraping jobs scheduled")
            
        except Exception as e:
            logger.error(f"Error scheduling scraping jobs: {e}")
    
    async def run_scheduled_scraping(self):
        """Run scheduled scraping for all due sources"""
        try:
            logger.info("Starting scheduled scraping job")
            
            # Run the scraping engine
            result = await scraping_engine.run_scheduled_scraping()
            
            # Log results
            if result.get('status') == 'completed':
                logger.info(
                    f"Scheduled scraping completed: "
                    f"{result.get('sources_successful', 0)}/{result.get('sources_processed', 0)} successful"
                )
            else:
                logger.error(f"Scheduled scraping failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in scheduled scraping job: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'started_at': datetime.now(timezone.utc).isoformat()
            }
    
    async def cleanup_old_data(self):
        """Clean up old scraped data (optional maintenance task)"""
        try:
            logger.info("Starting daily cleanup job")
            
            # This could include:
            # - Removing duplicate entries
            # - Archiving old data
            # - Updating statistics
            # For now, just log that cleanup ran
            
            logger.info("Daily cleanup completed")
            
        except Exception as e:
            logger.error(f"Error in daily cleanup job: {e}")
    
    async def trigger_manual_scraping(self, source_name: str) -> Dict[str, Any]:
        """Manually trigger scraping for a specific source"""
        try:
            logger.info(f"Manually triggering scraping for {source_name}")
            
            # Run scraper immediately
            result = await scraping_engine.run_scraper(source_name)
            
            logger.info(f"Manual scraping for {source_name} completed: {result.get('status')}")
            return result
            
        except Exception as e:
            error_msg = f"Error in manual scraping for {source_name}: {e}"
            logger.error(error_msg)
            return {
                'source_name': source_name,
                'status': 'failed',
                'error': error_msg,
                'started_at': datetime.now(timezone.utc).isoformat()
            }
    
    def get_job_status(self) -> Dict[str, Any]:
        """Get status of scheduled jobs"""
        try:
            if not self.scheduler or not self.is_running:
                return {
                    'scheduler_running': False,
                    'jobs': []
                }
            
            jobs = []
            for job in self.scheduler.get_jobs():
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger)
                })
            
            return {
                'scheduler_running': True,
                'jobs': jobs
            }
            
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return {
                'scheduler_running': False,
                'error': str(e),
                'jobs': []
            }
    
    async def add_custom_job(self, source_name: str, cron_expression: str) -> bool:
        """Add a custom scheduled job for a specific source"""
        try:
            if not self.scheduler or not self.is_running:
                logger.error("Scheduler not running")
                return False
            
            # Parse cron expression and create trigger
            # Format: "minute hour day month day_of_week"
            parts = cron_expression.split()
            if len(parts) != 5:
                logger.error(f"Invalid cron expression: {cron_expression}")
                return False
            
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            )
            
            # Add job
            job_id = f"custom_scraping_{source_name}"
            self.scheduler.add_job(
                func=lambda: scraping_engine.run_scraper(source_name),
                trigger=trigger,
                id=job_id,
                name=f"Custom Scraping - {source_name}",
                replace_existing=True
            )
            
            logger.info(f"Added custom job for {source_name}: {cron_expression}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding custom job for {source_name}: {e}")
            return False
    
    async def remove_custom_job(self, source_name: str) -> bool:
        """Remove a custom scheduled job for a specific source"""
        try:
            if not self.scheduler or not self.is_running:
                logger.error("Scheduler not running")
                return False
            
            job_id = f"custom_scraping_{source_name}"
            self.scheduler.remove_job(job_id)
            
            logger.info(f"Removed custom job for {source_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing custom job for {source_name}: {e}")
            return False


# Global instance
scheduler_service = SchedulerService()

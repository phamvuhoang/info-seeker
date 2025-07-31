import time
import asyncio
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from functools import wraps

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor and log performance metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.active_operations: Dict[str, float] = {}
    
    @asynccontextmanager
    async def measure_operation(self, operation_name: str, session_id: str = None):
        """Context manager to measure operation performance"""
        start_time = time.time()
        operation_key = f"{operation_name}_{session_id}" if session_id else operation_name
        
        self.active_operations[operation_key] = start_time
        
        try:
            yield
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            # Remove from active operations
            self.active_operations.pop(operation_key, None)
            
            # Store metrics
            if operation_name not in self.metrics:
                self.metrics[operation_name] = {
                    'total_calls': 0,
                    'total_time': 0,
                    'min_time': float('inf'),
                    'max_time': 0,
                    'avg_time': 0
                }
            
            metrics = self.metrics[operation_name]
            metrics['total_calls'] += 1
            metrics['total_time'] += duration
            metrics['min_time'] = min(metrics['min_time'], duration)
            metrics['max_time'] = max(metrics['max_time'], duration)
            metrics['avg_time'] = metrics['total_time'] / metrics['total_calls']
            
            # Log performance if operation takes too long
            if duration > 10:  # Log operations taking more than 10 seconds
                logger.warning(f"Slow operation detected: {operation_name} took {duration:.2f}s")
            elif duration > 5:  # Info for operations taking more than 5 seconds
                logger.info(f"Operation {operation_name} took {duration:.2f}s")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return {
            'metrics': self.metrics,
            'active_operations': len(self.active_operations),
            'active_operation_details': {
                op: time.time() - start_time 
                for op, start_time in self.active_operations.items()
            }
        }
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics.clear()
        logger.info("Performance metrics reset")


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def monitor_performance(operation_name: str):
    """Decorator to monitor function performance"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with performance_monitor.measure_operation(operation_name):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    if duration > 5:
                        logger.info(f"Operation {operation_name} took {duration:.2f}s")
            return sync_wrapper
    return decorator


async def log_performance_summary():
    """Log a summary of performance metrics"""
    metrics = performance_monitor.get_metrics()
    
    if not metrics['metrics']:
        logger.info("No performance metrics available")
        return
    
    logger.info("=== Performance Summary ===")
    for operation, data in metrics['metrics'].items():
        logger.info(f"{operation}: {data['total_calls']} calls, "
                   f"avg: {data['avg_time']:.2f}s, "
                   f"min: {data['min_time']:.2f}s, "
                   f"max: {data['max_time']:.2f}s")
    
    if metrics['active_operations'] > 0:
        logger.info(f"Active operations: {metrics['active_operations']}")
        for op, duration in metrics['active_operation_details'].items():
            logger.info(f"  {op}: running for {duration:.2f}s")

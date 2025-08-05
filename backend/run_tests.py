#!/usr/bin/env python3
"""
Test runner script for InfoSeeker backend tests
"""
import sys
import subprocess
import os
from pathlib import Path

def run_tests():
    """Run all tests with appropriate configuration"""
    
    # Set environment variables for testing
    os.environ['TESTING'] = 'true'
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://test:test@localhost:5433/test_infoseeker'
    
    # Change to backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    # Run pytest with coverage if available
    try:
        # Try to run with coverage
        result = subprocess.run([
            sys.executable, '-m', 'pytest',
            '--cov=app',
            '--cov-report=html',
            '--cov-report=term-missing',
            'tests/'
        ], check=False)
    except FileNotFoundError:
        # Fallback to basic pytest
        print("Coverage not available, running basic tests...")
        result = subprocess.run([
            sys.executable, '-m', 'pytest',
            'tests/'
        ], check=False)
    
    return result.returncode

def run_specific_test(test_path):
    """Run a specific test file or test function"""
    os.environ['TESTING'] = 'true'
    os.environ['DATABASE_URL'] = 'postgresql+psycopg://test:test@localhost:5433/test_infoseeker'
    
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    result = subprocess.run([
        sys.executable, '-m', 'pytest',
        '-v',
        test_path
    ], check=False)
    
    return result.returncode

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        # Run specific test
        test_path = sys.argv[1]
        return run_specific_test(test_path)
    else:
        # Run all tests
        return run_tests()

if __name__ == '__main__':
    sys.exit(main())

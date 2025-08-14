#!/bin/bash

# Script to run Celery worker for background tasks

echo "Starting Celery worker for Billion Dollar Company..."
echo "=============================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ Virtual environment activated"
fi

# Check if Redis is running
redis-cli ping > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Redis is running"
else
    echo "⚠️  Redis is not running. Starting Redis..."
    redis-server --daemonize yes
    sleep 2
    redis-cli ping > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✓ Redis started successfully"
    else
        echo "❌ Failed to start Redis. Please install Redis:"
        echo "   macOS: brew install redis"
        echo "   Ubuntu: sudo apt-get install redis-server"
        exit 1
    fi
fi

echo ""
echo "Starting Celery worker..."
echo "Press Ctrl+C to stop"
echo ""

# Run Celery worker with info logging
celery -A celery_tasks.celery_app worker --loglevel=info --concurrency=4
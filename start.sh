#!/bin/bash

# Complete startup script for Billion Dollar Company

echo "🚀 Billion Dollar Company - AI-Powered Business Automation"
echo "==========================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python
python3 --version > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Python3 found"
else
    echo -e "${RED}❌${NC} Python3 not found. Please install Python 3.8+"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Install/upgrade dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✓${NC} Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓${NC} .env file created"
    echo ""
    echo -e "${YELLOW}⚠️  Please edit .env and add your API keys:${NC}"
    echo "   - OPENAI_API_KEY"
    echo "   - ANTHROPIC_API_KEY"
    echo "   - GOOGLE_API_KEY"
    echo ""
fi

# Check Redis
redis-cli ping > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Redis is running"
else
    echo -e "${YELLOW}Starting Redis...${NC}"
    
    # Try different methods to start Redis
    if command -v brew &> /dev/null; then
        # macOS with Homebrew
        brew services start redis > /dev/null 2>&1
        sleep 2
    elif command -v systemctl &> /dev/null; then
        # Linux with systemd
        sudo systemctl start redis > /dev/null 2>&1
        sleep 2
    else
        # Fallback to direct start
        redis-server --daemonize yes > /dev/null 2>&1
        sleep 2
    fi
    
    redis-cli ping > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Redis started"
    else
        echo -e "${YELLOW}⚠️${NC} Redis not available (optional for background tasks)"
        echo "   To enable async AI execution, install Redis:"
        echo "   macOS: brew install redis && brew services start redis"
        echo "   Ubuntu: sudo apt-get install redis-server"
        echo ""
        echo "   Continuing with synchronous mode only..."
        REDIS_AVAILABLE=false
    fi
fi

# Start Celery worker in background (if Redis is available)
redis-cli ping > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${YELLOW}Starting Celery worker...${NC}"
    celery -A celery_tasks.celery_app worker --loglevel=error --logfile=celery.log --detach
    sleep 2
    echo -e "${GREEN}✓${NC} Celery worker started in background"
fi

echo ""
echo "=============================================="
echo -e "${GREEN}✅ All systems ready!${NC}"
echo ""
echo "Starting Flask application on http://localhost:5001"
echo ""
echo "Features enabled:"
echo "  • Real-time updates via WebSocket"
if redis-cli ping > /dev/null 2>&1; then
    echo "  • Background AI task processing"
fi
echo "  • Multi-provider AI support (OpenAI, Anthropic, Google)"
echo ""
echo "Press Ctrl+C to stop all services"
echo "=============================================="
echo ""

# Start Flask with Socket.IO
python app.py
#!/bin/bash

# Vitso Dev Orchestrator - Setup Script
# This script will set up everything you need to run VDO

set -e  # Exit on error

echo "================================================"
echo "  Vitso Dev Orchestrator - Setup"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check for required tools
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    echo "Please install Docker Compose"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose found${NC}"

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker is not running${NC}"
    echo "Please start Docker Desktop"
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"

echo ""
echo "================================================"
echo "  Step 1: Environment Configuration"
echo "================================================"

# Create .env file if it doesn't exist
if [ ! -f backend/.env ]; then
    echo -e "${YELLOW}Creating environment configuration...${NC}"
    cp backend/.env.template backend/.env
    
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: You need to add your API keys!${NC}"
    echo ""
    echo "Please edit backend/.env and add your API keys:"
    echo "  - ANTHROPIC_API_KEY=your_key_here"
    echo "  - OPENAI_API_KEY=your_key_here (optional)"
    echo "  - GOOGLE_API_KEY=your_key_here (optional)"
    echo ""
    read -p "Press Enter after you've added your API keys..."
fi

echo -e "${GREEN}✓ Environment configured${NC}"

echo ""
echo "================================================"
echo "  Step 2: Building Docker Containers"
echo "================================================"

echo -e "${YELLOW}Building containers (this may take a few minutes)...${NC}"
docker-compose build

echo -e "${GREEN}✓ Containers built${NC}"

echo ""
echo "================================================"
echo "  Step 3: Starting Services"
echo "================================================"

echo -e "${YELLOW}Starting all services...${NC}"
docker-compose up -d

echo -e "${GREEN}✓ Services started${NC}"

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check service health
echo ""
echo "Service Status:"
docker-compose ps

echo ""
echo "================================================"
echo "  ✅ Setup Complete!"
echo "================================================"
echo ""
echo "Vitso Dev Orchestrator is now running!"
echo ""
echo "📊 Dashboard: http://localhost:3000"
echo "🔧 API: http://localhost:8000"
echo "📝 API Docs: http://localhost:8000/docs"
echo ""
echo "Useful Commands:"
echo "  View logs:        docker-compose logs -f"
echo "  Stop services:    docker-compose down"
echo "  Restart services: docker-compose restart"
echo "  View status:      docker-compose ps"
echo ""
echo "================================================"
echo ""

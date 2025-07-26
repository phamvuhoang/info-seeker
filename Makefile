# InfoSeeker Makefile
# Common development and deployment tasks

.PHONY: help install dev build test clean deploy logs stop

# Default target
help:
	@echo "InfoSeeker Development Commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install     - Install all dependencies"
	@echo "  make dev         - Start development environment"
	@echo "  make test        - Run all tests"
	@echo "  make lint        - Run code linting"
	@echo "  make format      - Format code"
	@echo ""
	@echo "Docker:"
	@echo "  make build       - Build Docker images"
	@echo "  make up          - Start all services with Docker"
	@echo "  make down        - Stop all services"
	@echo "  make logs        - View service logs"
	@echo "  make restart     - Restart all services"
	@echo ""
	@echo "Production:"
	@echo "  make deploy      - Deploy to production"
	@echo "  make prod-logs   - View production logs"
	@echo "  make backup      - Backup database"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean       - Clean up containers and volumes"
	@echo "  make reset       - Reset development environment"

# Development commands
install:
	@echo "Installing backend dependencies..."
	cd backend && python -m pip install -r requirements.txt
	cd backend && playwright install chromium
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "Dependencies installed!"

dev:
	@echo "Starting development environment..."
	docker-compose up -d postgres redis
	@echo "Database services started. Now start backend and frontend manually:"
	@echo "Backend: cd backend && python -m uvicorn app.main:app --reload"
	@echo "Frontend: cd frontend && npm start"

# Docker commands
build:
	@echo "Building Docker images..."
	docker-compose build

up:
	@echo "Starting all services..."
	docker-compose up -d

down:
	@echo "Stopping all services..."
	docker-compose down

logs:
	@echo "Viewing service logs..."
	docker-compose logs -f

restart:
	@echo "Restarting all services..."
	docker-compose restart

# Testing
test:
	@echo "Running backend tests..."
	cd backend && python -m pytest tests/ -v
	@echo "Running frontend tests..."
	cd frontend && npm test -- --watchAll=false

test-backend:
	@echo "Running backend tests..."
	cd backend && python -m pytest tests/ -v

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && npm test -- --watchAll=false

# Code quality
lint:
	@echo "Linting backend code..."
	cd backend && python -m flake8 app/
	@echo "Linting frontend code..."
	cd frontend && npm run lint

format:
	@echo "Formatting backend code..."
	cd backend && python -m black app/
	cd backend && python -m isort app/
	@echo "Formatting frontend code..."
	cd frontend && npm run format

# Production commands
deploy:
	@echo "Deploying to production..."
	docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

prod-logs:
	@echo "Viewing production logs..."
	docker-compose -f docker-compose.prod.yml logs -f

backup:
	@echo "Creating database backup..."
	docker exec infoseeker-postgres-prod pg_dump -U infoseeker infoseeker > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup created: backup_$(shell date +%Y%m%d_%H%M%S).sql"

# Utility commands
clean:
	@echo "Cleaning up Docker resources..."
	docker-compose down -v
	docker system prune -f
	@echo "Cleanup complete!"

reset: clean
	@echo "Resetting development environment..."
	docker-compose up -d postgres redis
	@echo "Environment reset complete!"

# Database commands
db-shell:
	@echo "Connecting to database..."
	docker exec -it infoseeker-postgres psql -U infoseeker -d infoseeker

redis-shell:
	@echo "Connecting to Redis..."
	docker exec -it infoseeker-redis redis-cli

# Health checks
health:
	@echo "Checking service health..."
	@curl -f http://localhost:8000/health || echo "Backend: DOWN"
	@curl -f http://localhost:3000 || echo "Frontend: DOWN"

# Setup commands
setup: install
	@echo "Setting up InfoSeeker..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file. Please edit it with your configuration."; \
	fi
	@echo "Setup complete! Run 'make dev' to start development."

# InfoSeeker Development Guide

This guide provides detailed instructions for setting up and running InfoSeeker in development mode.

## 🏗️ Project Structure

```
info-seeker/
├── backend/                 # FastAPI backend application
│   ├── app/
│   │   ├── agents/         # Agno agent configurations
│   │   ├── api/            # FastAPI routes
│   │   ├── core/           # Configuration and settings
│   │   ├── models/         # Pydantic models
│   │   ├── services/       # Business logic services
│   │   └── tools/          # Custom tools for agents
│   └── requirements.txt    # Python dependencies
├── frontend/               # React frontend application
│   ├── public/            # Static assets
│   ├── src/               # React source code
│   │   ├── components/    # React components
│   │   └── services/      # API services
│   └── package.json       # Node.js dependencies
├── docker/                # Docker configuration files
├── docs/                  # Documentation
├── .env.example          # Environment variables template
├── docker-compose.yml    # Docker Compose configuration
└── README.md             # Main documentation
```

## 🚀 Quick Start

### Prerequisites

1. **Python 3.13+**
   ```bash
   python --version  # Should be 3.13 or higher
   ```

2. **Node.js 18+**
   ```bash
   node --version    # Should be 18 or higher
   npm --version
   ```

3. **Docker & Docker Compose**
   ```bash
   docker --version
   docker-compose --version
   ```

4. **OpenAI API Key**
   - Sign up at https://platform.openai.com/
   - Create an API key
   - Keep it secure for environment configuration

### Environment Setup

1. **Clone and navigate to the project**
   ```bash
   git clone <repository-url>
   cd info-seeker
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Edit .env file with your configuration**
   ```bash
   # Required: Add your OpenAI API key
   OPENAI_API_KEY=sk-your-openai-api-key-here
   
   # Optional: Customize other settings
   DEBUG=true
   DATABASE_URL=postgresql+psycopg://infoseeker:infoseeker@localhost:5432/infoseeker
   REDIS_URL=redis://localhost:6379/0
   ```

## 🐳 Docker Development (Recommended)

### Full Stack with Docker

1. **Start all services**
   ```bash
   docker-compose up -d
   ```

2. **View logs**
   ```bash
   docker-compose logs -f
   ```

3. **Stop services**
   ```bash
   docker-compose down
   ```

4. **Rebuild after changes**
   ```bash
   docker-compose up -d --build
   ```

### Individual Services

**Start only database services:**
```bash
docker-compose up -d postgres redis
```

**Start only backend:**
```bash
docker-compose up -d backend
```

## 💻 Local Development

### Backend Development

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # On macOS/Linux:
   source venv/bin/activate
   
   # On Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

5. **Start database services (if not using Docker for everything)**
   ```bash
   # PostgreSQL with PgVector
   docker run -d --name infoseeker-postgres \
     -p 5432:5432 \
     -e POSTGRES_DB=infoseeker \
     -e POSTGRES_USER=infoseeker \
     -e POSTGRES_PASSWORD=infoseeker \
     -v $(pwd)/docker/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql \
     pgvector/pgvector:pg16
   
   # Redis
   docker run -d --name infoseeker-redis \
     -p 6379:6379 \
     redis:7-alpine
   ```

6. **Run the backend server**
   ```bash
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Access backend**
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - Health check: http://localhost:8000/health

### Frontend Development

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start development server**
   ```bash
   npm start
   ```

4. **Access frontend**
   - Application: http://localhost:3000
   - Auto-reloads on file changes

## 🧪 Testing

### Backend Testing

1. **Install test dependencies**
   ```bash
   cd backend
   pip install pytest pytest-asyncio httpx
   ```

2. **Run tests**
   ```bash
   python -m pytest tests/ -v
   ```

3. **Run with coverage**
   ```bash
   python -m pytest tests/ --cov=app --cov-report=html
   ```

### Frontend Testing

1. **Run tests**
   ```bash
   cd frontend
   npm test
   ```

2. **Run tests with coverage**
   ```bash
   npm test -- --coverage
   ```

## 🔧 Development Tools

### Code Quality

**Backend (Python):**
```bash
# Install development tools
pip install black isort flake8 mypy

# Format code
black app/
isort app/

# Lint code
flake8 app/
mypy app/
```

**Frontend (JavaScript):**
```bash
# Install development tools
npm install --save-dev eslint prettier

# Format code
npm run format

# Lint code
npm run lint
```

### Database Management

**Connect to PostgreSQL:**
```bash
docker exec -it infoseeker-postgres psql -U infoseeker -d infoseeker
```

**Connect to Redis:**
```bash
docker exec -it infoseeker-redis redis-cli
```

**Reset database:**
```bash
docker-compose down -v
docker-compose up -d postgres
```

## 🐛 Debugging

### Backend Debugging

1. **Enable debug mode**
   ```bash
   export DEBUG=true
   ```

2. **View detailed logs**
   ```bash
   python -m uvicorn app.main:app --reload --log-level debug
   ```

3. **Use debugger**
   ```python
   import pdb; pdb.set_trace()  # Add to code for breakpoints
   ```

### Frontend Debugging

1. **Use React Developer Tools**
   - Install browser extension
   - Inspect component state and props

2. **View network requests**
   - Open browser developer tools
   - Check Network tab for API calls

3. **Console debugging**
   ```javascript
   console.log('Debug info:', data);
   ```

## 🔄 Common Development Tasks

### Adding New API Endpoints

1. **Create route in `backend/app/api/`**
2. **Add Pydantic models in `backend/app/models/`**
3. **Include router in `backend/app/main.py`**
4. **Add frontend API call in `frontend/src/services/api.js`**

### Adding New React Components

1. **Create component in `frontend/src/components/`**
2. **Add to routing if needed**
3. **Update parent components**
4. **Add tests**

### Database Schema Changes

1. **Update `docker/init-db.sql`**
2. **Restart database container**
3. **Update Pydantic models**
4. **Test migrations**

## 🚨 Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Find process using port
lsof -i :8000
# Kill process
kill -9 <PID>
```

**Docker issues:**
```bash
# Clean up Docker
docker system prune -a
docker-compose down -v
```

**Python dependency issues:**
```bash
# Recreate virtual environment
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Node.js dependency issues:**
```bash
# Clear npm cache and reinstall
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

### Getting Help

1. Check the logs: `docker-compose logs -f`
2. Verify environment variables: `cat .env`
3. Test API endpoints: http://localhost:8000/docs
4. Check database connection: `docker exec -it infoseeker-postgres pg_isready`
5. Verify Redis connection: `docker exec -it infoseeker-redis redis-cli ping`

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://reactjs.org/docs/)
- [Agno Framework](https://github.com/agno-ai/agno)
- [Playwright Documentation](https://playwright.dev/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)

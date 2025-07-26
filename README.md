# InfoSeeker - AI-Powered Search Platform

InfoSeeker is an open-source AI-powered search platform designed to deliver junk-free, personalized information retrieval and answer generation. It leverages trusted online sources and stored data to provide concise, accurate, and contextually relevant answers.

## 🚀 Features

- **Web Search Automation**: Real-time web searches using browser automation (Playwright)
- **AI Answer Generation**: Context-aware answers using advanced AI with Retrieval-Augmented Generation (RAG)
- **Stored Data Search**: Semantic search through stored content using vector embeddings
- **Session Management**: Persistent context across user interactions
- **Clean Architecture**: Built with FastAPI, React, and modern technologies

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web UI/API    │    │   Agent Core    │    │  Knowledge Base │
│   (FastAPI)     │◄──►│   (Agno)        │◄──►│   (PgVector)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Session       │    │   Web Search    │    │   Content       │
│   Management    │    │   (Playwright)  │    │   Processing    │
│   (Redis)       │    └─────────────────┘    │   Pipeline      │
└─────────────────┘                           └─────────────────┘
```

- **Backend**: FastAPI with Agno framework for AI agents
- **Frontend**: React with Tailwind CSS
- **Database**: PostgreSQL with PgVector for vector storage
- **Cache**: Redis for session management
- **AI**: OpenAI GPT-4 for answer generation
- **Web Automation**: Playwright for web scraping

## 📋 Prerequisites

- Python 3.13+
- Node.js 18+
- Docker and Docker Compose
- OpenAI API key

## 🛠️ Installation & Setup

### Option 1: Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd info-seeker
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

3. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Option 2: Local Development

#### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

5. **Set up environment variables**
   ```bash
   cp ../.env.example ../.env
   # Edit .env and configure your settings
   ```

6. **Start PostgreSQL and Redis**
   ```bash
   # Using Docker
   docker run -d --name infoseeker-postgres -p 5432:5432 \
     -e POSTGRES_DB=infoseeker \
     -e POSTGRES_USER=infoseeker \
     -e POSTGRES_PASSWORD=infoseeker \
     pgvector/pgvector:pg16

   docker run -d --name infoseeker-redis -p 6379:6379 redis:7-alpine
   ```

7. **Run the backend**
   ```bash
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

#### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start the development server**
   ```bash
   npm start
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://infoseeker:infoseeker@localhost:5432/infoseeker` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `DEBUG` | Enable debug mode | `false` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `MAX_SEARCH_RESULTS` | Maximum search results | `10` |
| `RESPONSE_TIMEOUT` | Response timeout (seconds) | `30` |

## 📖 API Documentation

### Search Endpoint

**POST** `/api/v1/search`

```json
{
  "query": "What are the latest AI developments?",
  "max_results": 10,
  "include_web": true,
  "include_stored": true
}
```

**Response:**
```json
{
  "query": "What are the latest AI developments?",
  "answer": "Based on recent information...",
  "sources": [
    {
      "title": "Source Title",
      "content": "Source content...",
      "url": "https://example.com",
      "source": "DuckDuckGo",
      "relevance_score": 0.95,
      "timestamp": "2024-01-01T00:00:00Z"
    }
  ],
  "processing_time": 2.34,
  "session_id": "uuid-string"
}
```

### Health Check

**GET** `/health`

Returns application health status.

## 🧪 Testing

### Backend Tests
```bash
cd backend
python -m pytest tests/
```

### Frontend Tests
```bash
cd frontend
npm test
```

## 🚀 Deployment

### Production Docker Setup

1. **Build production images**
   ```bash
   docker-compose -f docker-compose.prod.yml build
   ```

2. **Deploy**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Environment-specific Configuration

- Set `DEBUG=false` for production
- Use strong passwords for database
- Configure proper CORS settings
- Set up SSL/TLS certificates
- Configure monitoring and logging

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- Documentation: [Link to docs]
- Issues: [GitHub Issues]
- Discussions: [GitHub Discussions]

## 🗺️ Roadmap

- [x] **Milestone 1**: Foundational Setup and Core Backend
- [x] **Milestone 2**: Web Search and Content Processing
- [ ] **Milestone 3**: Vector Search and RAG Implementation
- [ ] **Milestone 4**: Advanced Features and UI Polish
- [ ] **Milestone 5**: Production Optimization and Scaling

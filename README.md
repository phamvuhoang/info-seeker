# InfoSeeker - AI-Powered Search Platform

InfoSeeker is an open-source AI-powered search platform designed to deliver junk-free, personalized information retrieval and answer generation. It leverages a multi-agent system to consult trusted online sources and stored data, providing concise, accurate, and contextually relevant answers with real-time progress updates.

## 🚀 Features

### Core Search Capabilities
- **Multi-Agent Hybrid Search**: A team of specialized AI agents collaborates to combine vector-based RAG with real-time web search.
- **Real-time Progress Updates**: WebSocket-based communication provides live updates on agent status and progress.
- **Web Search Automation**: Real-time web searches using browser automation (Playwright).
- **Stored Data Search**: Semantic search through stored content using PgVector and vector embeddings.
- **AI Answer Generation**: Context-aware answers using advanced AI with Retrieval-Augmented Generation (RAG).
- **Intelligent Storage**: Automatically vectorizes and stores search results for future learning.

### Predefined Content Scraping (New in v3.1)
- **Automated Content Scraping**: Scheduled scraping of hotels from Agoda and restaurants from Tabelog.
- **Manual Scraping Triggers**: Admin endpoints for on-demand scraping operations.
- **Content Browse Interface**: Dedicated UI for browsing and searching scraped content.
- **Advanced Filtering**: Search by rating, location, price, cuisine type, and more.
- **Real-time Statistics**: Live statistics dashboard showing scraped content metrics.

### System Features
- **Multi-Language Support**: Automatic detection and response in 60+ languages.
- **Session Management**: Persistent context across user interactions.
- **Clean Architecture**: Built with FastAPI, React, and modern technologies.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Frontend (React + WebSocket)                      │
│                        Real-time Agent Progress Updates                     │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────────────────┐
│                      FastAPI Backend + WebSocket                            │
│                    Orchestrator Agent (Team Leader)                         │
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────────────────┐
│                    Multi-Agent Search Team                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐│
│  │ RAG Agent   │ │ Web Agent   │ │ Synthesis   │ │ Validation  │ │ Answer  ││
│  │ (Vector     │ │ (Playwright │ │ Agent       │ │ Agent       │ │ Agent   ││
│  │ Search)     │ │ Search)     │ │ (Combine)   │ │ (Verify)    │ │ (Final) ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘│
└─────────────────────────┬───────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────────────────┐
│                    Knowledge & Storage Layer                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ PgVector    │ │ Redis       │ │ Session     │ │ Agent       │           │
│  │ (Embeddings)│ │ (Cache)     │ │ Memory      │ │ Workflows   │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Backend**: FastAPI with Agno framework for AI agents
- **Frontend**: React with Tailwind CSS
- **Database**: PostgreSQL with PgVector for vector storage
- **Cache**: Redis for session management
- **AI**: OpenAI GPT-4 for answer generation
- **Web Automation**: Playwright for web scraping

## 📋 Prerequisites

- Python 3.11+
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
   docker-compose up -d postgres redis
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
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://infoseeker:infoseeker@localhost:5433/infoseeker` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `DEBUG` | Enable debug mode | `false` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `MAX_SEARCH_RESULTS` | Maximum search results | `10` |
| `RESPONSE_TIMEOUT` | Response timeout (seconds) | `30` |

## 📖 API Documentation

### Hybrid Search Endpoint

**POST** `/api/v1/search/hybrid`

```json
{
  "query": "What are the latest developments in AI?",
  "session_id": "unique-session-id",
  "include_web": true,
  "include_rag": true,
  "max_results": 10
}
```

**Response:**
The final response is delivered via WebSocket, but the initial HTTP response will be:
```json
{
  "status": "started",
  "session_id": "unique-session-id",
  "message": "Multi-agent search initiated. Connect to WebSocket for real-time updates."
}
```

### Predefined Content API Endpoints

#### Search Hotels
**GET** `/api/v1/predefined_content/hotels`

Query parameters:
- `search`: Text search in hotel name and address
- `min_rating`: Minimum rating filter (0-5)
- `max_rating`: Maximum rating filter (0-5)
- `city`: Filter by city name
- `source_name`: Filter by source website (e.g., 'agoda')
- `min_price`: Minimum price per night
- `max_price`: Maximum price per night
- `page`: Page number (default: 1)
- `size`: Page size (default: 20, max: 100)

#### Search Restaurants
**GET** `/api/v1/predefined_content/restaurants`

Query parameters:
- `search`: Text search in restaurant name and address
- `min_rating`: Minimum rating filter (0-5)
- `max_rating`: Maximum rating filter (0-5)
- `city`: Filter by city name
- `source_name`: Filter by source website (e.g., 'tabelog')
- `cuisine_type`: Filter by cuisine type
- `page`: Page number (default: 1)
- `size`: Page size (default: 20, max: 100)

#### Manual Scraping
**POST** `/api/v1/predefined_content/scrape/{source_name}`

Trigger manual scraping for a specific source (`agoda` or `tabelog`).

#### Scraping Status
**GET** `/api/v1/predefined_content/scraping/status`

Get the current status of the scraping scheduler and jobs.

For detailed API documentation, visit `/docs` when the server is running.

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

### Validation Scripts
```bash
# Test multi-agent system functionality
python info-seeker/backend/test_multi_agent_system.py

# Validate deployment
python info-seeker/validate_deployment.py
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
- [x] **Milestone 3**: Multi-Agent Hybrid Search Implementation
- [ ] **Milestone 4**: Advanced Features and UI Polish
- [ ] **Milestone 5**: Production Optimization and Scaling

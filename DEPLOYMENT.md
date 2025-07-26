# InfoSeeker Deployment Guide

This guide covers deploying InfoSeeker in production environments.

## 🚀 Quick Start (Docker)

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- OpenAI API key
- Domain name (for production)

### 1. Environment Setup

```bash
# Clone repository
git clone <repository-url>
cd info-seeker

# Create production environment file
cp .env.example .env.prod
```

### 2. Configure Environment Variables

Edit `.env.prod`:

```bash
# Required
OPENAI_API_KEY=sk-your-openai-api-key-here

# Database (use strong passwords in production)
POSTGRES_DB=infoseeker
POSTGRES_USER=infoseeker
POSTGRES_PASSWORD=your-strong-password-here

# Redis (optional password)
REDIS_PASSWORD=your-redis-password

# Application
DEBUG=false
REACT_APP_API_URL=https://your-domain.com

# Optional: Custom ports
# POSTGRES_PORT=5432
# REDIS_PORT=6379
# BACKEND_PORT=8000
# FRONTEND_PORT=3000
```

### 3. Deploy with Docker Compose

```bash
# Production deployment
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 4. Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# Frontend
curl http://localhost:3000

# API documentation
open http://localhost:8000/docs
```

## 🔧 Production Configuration

### SSL/TLS Setup

1. **Obtain SSL certificates** (Let's Encrypt recommended):
   ```bash
   # Using certbot
   sudo certbot certonly --standalone -d your-domain.com
   ```

2. **Configure Nginx** (uncomment HTTPS section in `nginx/nginx.conf`):
   ```nginx
   server {
       listen 443 ssl http2;
       server_name your-domain.com;
       
       ssl_certificate /etc/nginx/ssl/cert.pem;
       ssl_certificate_key /etc/nginx/ssl/key.pem;
       # ... rest of configuration
   }
   ```

3. **Mount certificates**:
   ```yaml
   # In docker-compose.prod.yml
   nginx:
     volumes:
       - /etc/letsencrypt/live/your-domain.com:/etc/nginx/ssl:ro
   ```

### Database Security

1. **Use strong passwords**
2. **Limit network access**:
   ```yaml
   postgres:
     ports: [] # Remove external port exposure
   ```

3. **Enable SSL** (for external connections):
   ```yaml
   postgres:
     command: postgres -c ssl=on -c ssl_cert_file=/var/lib/postgresql/server.crt
   ```

### Application Security

1. **Environment variables**:
   ```bash
   # Use secrets management in production
   OPENAI_API_KEY_FILE=/run/secrets/openai_api_key
   ```

2. **CORS configuration**:
   ```python
   # In backend/app/main.py
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-domain.com"],  # Specific domains only
       allow_credentials=True,
       allow_methods=["GET", "POST"],
       allow_headers=["*"],
   )
   ```

## 🌐 Cloud Deployment

### AWS Deployment

#### Using ECS (Elastic Container Service)

1. **Build and push images**:
   ```bash
   # Build images
   docker build -t infoseeker-backend .
   docker build -t infoseeker-frontend -f frontend/Dockerfile .
   
   # Tag for ECR
   docker tag infoseeker-backend:latest 123456789012.dkr.ecr.region.amazonaws.com/infoseeker-backend:latest
   docker tag infoseeker-frontend:latest 123456789012.dkr.ecr.region.amazonaws.com/infoseeker-frontend:latest
   
   # Push to ECR
   aws ecr get-login-password --region region | docker login --username AWS --password-stdin 123456789012.dkr.ecr.region.amazonaws.com
   docker push 123456789012.dkr.ecr.region.amazonaws.com/infoseeker-backend:latest
   docker push 123456789012.dkr.ecr.region.amazonaws.com/infoseeker-frontend:latest
   ```

2. **Create ECS task definition**
3. **Set up RDS for PostgreSQL**
4. **Configure ElastiCache for Redis**
5. **Set up Application Load Balancer**

#### Using EC2

1. **Launch EC2 instance** (t3.medium or larger recommended)
2. **Install Docker and Docker Compose**
3. **Clone repository and deploy**
4. **Configure security groups** (ports 80, 443, 22)

### Google Cloud Platform

#### Using Cloud Run

1. **Build and push to Container Registry**
2. **Deploy services to Cloud Run**
3. **Set up Cloud SQL for PostgreSQL**
4. **Configure Memorystore for Redis**

### DigitalOcean

#### Using App Platform

1. **Connect GitHub repository**
2. **Configure build settings**
3. **Set up managed database**
4. **Configure environment variables**

## 📊 Monitoring & Logging

### Application Monitoring

1. **Health checks**:
   ```bash
   # Add to crontab for monitoring
   */5 * * * * curl -f http://localhost:8000/health || echo "Service down" | mail admin@example.com
   ```

2. **Prometheus metrics** (optional):
   ```python
   # Add to requirements.txt
   prometheus-fastapi-instrumentator==6.1.0
   
   # In main.py
   from prometheus_fastapi_instrumentator import Instrumentator
   Instrumentator().instrument(app).expose(app)
   ```

### Log Management

1. **Centralized logging**:
   ```yaml
   # In docker-compose.prod.yml
   services:
     backend:
       logging:
         driver: "json-file"
         options:
           max-size: "10m"
           max-file: "3"
   ```

2. **Log aggregation** (ELK Stack, Fluentd, etc.)

### Database Monitoring

1. **PostgreSQL monitoring**:
   ```sql
   -- Monitor connections
   SELECT count(*) FROM pg_stat_activity;
   
   -- Monitor slow queries
   SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
   ```

2. **Automated backups**:
   ```bash
   # Daily backup script
   #!/bin/bash
   docker exec infoseeker-postgres-prod pg_dump -U infoseeker infoseeker > backup_$(date +%Y%m%d).sql
   ```

## 🔄 Updates & Maintenance

### Rolling Updates

1. **Backend updates**:
   ```bash
   # Build new image
   docker-compose -f docker-compose.prod.yml build backend
   
   # Rolling update
   docker-compose -f docker-compose.prod.yml up -d --no-deps backend
   ```

2. **Frontend updates**:
   ```bash
   docker-compose -f docker-compose.prod.yml build frontend
   docker-compose -f docker-compose.prod.yml up -d --no-deps frontend
   ```

### Database Migrations

1. **Backup before migration**:
   ```bash
   docker exec infoseeker-postgres-prod pg_dump -U infoseeker infoseeker > pre_migration_backup.sql
   ```

2. **Apply migrations**:
   ```bash
   # Update init-db.sql with new schema
   # Restart database container
   docker-compose -f docker-compose.prod.yml restart postgres
   ```

### Scaling

1. **Horizontal scaling**:
   ```yaml
   # In docker-compose.prod.yml
   backend:
     deploy:
       replicas: 3
   ```

2. **Load balancing**:
   ```nginx
   upstream backend {
       server backend_1:8000;
       server backend_2:8000;
       server backend_3:8000;
   }
   ```

## 🚨 Troubleshooting

### Common Issues

1. **Service won't start**:
   ```bash
   # Check logs
   docker-compose -f docker-compose.prod.yml logs backend
   
   # Check environment variables
   docker-compose -f docker-compose.prod.yml config
   ```

2. **Database connection issues**:
   ```bash
   # Test database connection
   docker exec infoseeker-postgres-prod pg_isready -U infoseeker
   
   # Check network connectivity
   docker exec infoseeker-backend-prod ping postgres
   ```

3. **High memory usage**:
   ```bash
   # Monitor resource usage
   docker stats
   
   # Limit container resources
   # Add to docker-compose.prod.yml:
   deploy:
     resources:
       limits:
         memory: 1G
         cpus: '0.5'
   ```

### Performance Optimization

1. **Database optimization**:
   ```sql
   -- Analyze query performance
   EXPLAIN ANALYZE SELECT * FROM infoseeker_documents WHERE ...;
   
   -- Update statistics
   ANALYZE;
   ```

2. **Redis optimization**:
   ```bash
   # Monitor Redis performance
   docker exec infoseeker-redis-prod redis-cli info memory
   ```

3. **Application optimization**:
   - Enable response caching
   - Optimize database queries
   - Use connection pooling
   - Implement rate limiting

## 📋 Checklist

### Pre-deployment

- [ ] Environment variables configured
- [ ] SSL certificates obtained
- [ ] Database passwords changed
- [ ] CORS settings updated
- [ ] Monitoring configured
- [ ] Backup strategy implemented

### Post-deployment

- [ ] Health checks passing
- [ ] SSL certificate valid
- [ ] Database accessible
- [ ] Redis functioning
- [ ] Logs being collected
- [ ] Monitoring alerts configured
- [ ] Backup tested

### Security

- [ ] Strong passwords used
- [ ] Unnecessary ports closed
- [ ] SSL/TLS configured
- [ ] Security headers enabled
- [ ] Rate limiting active
- [ ] Regular updates scheduled

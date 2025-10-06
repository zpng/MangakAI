# MangakAI - AI-Powered Manga Generation Platform

Transform your stories into manga panels with AI! MangakAI is a modern, scalable platform that uses advanced AI to generate beautiful manga-style illustrations from text stories.

## 🌟 Features

### Core Features
- **📝 Story-to-Manga Generation**: Convert text stories into visual manga panels
- **🎨 Customizable Art Styles**: Multiple art styles, moods, and visual preferences
- **🔄 Panel Regeneration**: Modify and regenerate specific panels with custom requests
- **📁 File Upload Support**: Upload .txt files for batch processing
- **📄 PDF Export**: Export completed manga as PDF files

### New Async Features (v2.0)
- **⚡ Asynchronous Processing**: Long-running tasks don't block the UI
- **📡 Real-time Progress Updates**: WebSocket-based live progress tracking
- **📊 Task Management**: View task history and manage multiple generations
- **☁️ Cloud Storage Integration**: Reliable image storage with S3/OSS support
- **🔄 Automatic Retry**: Robust error handling and task recovery
- **📈 Monitoring & Metrics**: Comprehensive system monitoring with Prometheus

## 🏗️ Architecture

MangakAI v2.0 features a modern, scalable architecture:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend│    │  FastAPI Server │    │   Celery Workers│
│                 │◄──►│                 │◄──►│                 │
│ - Real-time UI  │    │ - REST API      │    │ - Async Tasks   │
│ - WebSocket     │    │ - WebSocket     │    │ - Image Gen     │
│ - Task History  │    │ - Task Mgmt     │    │ - Progress      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │   Redis Queue   │              │
         └──────────────►│                 │◄─────────────┘
                        │ - Task Queue    │
                        │ - Progress      │
                        │ - Caching       │
                        └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │   PostgreSQL    │
                        │                 │
                        │ - Task Metadata │
                        │ - User Sessions │
                        │ - Panel Data    │
                        └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 16+
- Redis (for task queue)
- PostgreSQL (for data persistence)
- Docker (optional, for easy setup)

### Option 1: Automated Setup (Recommended)
```bash
# Clone the repository
git clone https://github.com/your-username/MangakAI.git
cd MangakAI

# Run the setup script
./scripts/setup.sh

# Edit environment variables
cp .env.example .env
# Edit .env with your API keys and configuration
```

### Option 2: Manual Setup

#### 1. Backend Setup
```bash
# Install Python dependencies
pip install uv  # Modern Python package manager
uv sync

# Setup database
# Create PostgreSQL database 'mangakai'
# Start Redis server

# Run database migrations
uv run alembic upgrade head

# Start the backend server
uv run uvicorn server:app --reload
```

#### 2. Start Celery Workers
```bash
# In a new terminal
uv run celery -A celery_app worker --loglevel=info

# Optional: Start Celery Beat for scheduled tasks
uv run celery -A celery_app beat --loglevel=info

# Optional: Start Flower for monitoring
uv run celery -A celery_app flower
```

#### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Option 3: Docker Setup
```bash
# Start all services with Docker Compose
docker-compose up -d

# Run database migrations
docker-compose exec backend alembic upgrade head
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# AI API Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# Database Configuration
DATABASE_URL=postgresql://mangakai:password@localhost:5432/mangakai
REDIS_URL=redis://localhost:6379/0

# Storage Configuration
STORAGE_TYPE=local  # Options: local, s3
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
S3_BUCKET=your-s3-bucket-name

# Application Configuration
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173
```

### API Keys Required
- **Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **AWS Credentials**: (Optional) For S3 storage integration

## 📖 Usage

### Web Interface
1. Open http://localhost:5173 in your browser
2. Choose between text input or file upload
3. Customize art style, mood, and other preferences
4. Click "Generate Manga" and watch real-time progress
5. View generated panels and regenerate specific ones if needed
6. Export as PDF when satisfied

### API Usage

#### Async Manga Generation
```python
import requests

# Create async task
response = requests.post('http://localhost:8000/api/async/generate-manga', json={
    'story_text': 'Your story here...',
    'num_scenes': 5,
    'art_style': 'Anime/Manga',
    'mood': 'Adventurous'
})

task_id = response.json()['task_id']

# Check task status
status_response = requests.get(f'http://localhost:8000/api/async/task/{task_id}/status')
print(status_response.json())
```

#### WebSocket for Real-time Updates
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/your-session-id');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'progress_update') {
        console.log('Progress:', data.data.progress + '%');
        console.log('Status:', data.data.message);
    }
};

// Subscribe to task updates
ws.send(JSON.stringify({
    type: 'subscribe_task',
    task_id: 'your-task-id'
}));
```

## 🛠️ Development

### Project Structure
```
MangakAI/
├── server.py              # FastAPI application
├── celery_app.py          # Celery configuration
├── database.py            # Database setup
├── models/                # SQLAlchemy models
├── tasks/                 # Celery tasks
├── api/                   # API endpoints
├── storage/               # Cloud storage integration
├── monitoring/            # Metrics and monitoring
├── websocket_manager.py   # WebSocket management
├── manga.py               # Core manga generation logic
├── utils.py               # Utility functions
├── frontend/              # React frontend
├── docs/                  # Technical documentation
├── k8s/                   # Kubernetes configurations
├── scripts/               # Setup and utility scripts
└── alembic/               # Database migrations
```

### Adding New Features

1. **Backend API**: Add endpoints in `api/`
2. **Async Tasks**: Add tasks in `tasks/`
3. **Database Models**: Add models in `models/`
4. **Frontend Components**: Add components in `frontend/src/components/`
5. **Monitoring**: Add metrics in `monitoring/metrics.py`

### Running Tests
```bash
# Backend tests
uv run pytest

# Frontend tests
cd frontend && npm test

# Integration tests
uv run pytest tests/integration/
```

## 📊 Monitoring

### Built-in Monitoring
- **Prometheus Metrics**: http://localhost:8001/metrics
- **Flower (Celery)**: http://localhost:5555
- **Health Checks**: http://localhost:8000/health

### Key Metrics
- Request rate and response time
- Task success/failure rates
- Queue lengths and processing times
- WebSocket connection counts
- Storage operations and sizes

## 🚀 Deployment

### Production Deployment

See detailed deployment guides in `docs/`:
- [Overseas Deployment Guide](docs/overseas-deployment-guide.md)
- [Technical Solution](docs/technical-solution.md)
- [Monitoring Guide](docs/monitoring-operations-guide.md)

### Quick Production Setup
```bash
# Using Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# Using Kubernetes
kubectl apply -f k8s/production/
```

## 🔍 Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check PostgreSQL is running
   pg_isready -h localhost -p 5432
   
   # Check connection string in .env
   echo $DATABASE_URL
   ```

2. **Redis Connection Failed**
   ```bash
   # Check Redis is running
   redis-cli ping
   
   # Check Redis URL in .env
   echo $REDIS_URL
   ```

3. **Celery Tasks Not Processing**
   ```bash
   # Check Celery worker is running
   uv run celery -A celery_app inspect active
   
   # Check queue status
   uv run celery -A celery_app inspect stats
   ```

4. **WebSocket Connection Issues**
   - Check CORS settings in server.py
   - Verify WebSocket URL in frontend
   - Check firewall/proxy settings

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Enable SQL query logging
export SQL_DEBUG=true

# Start with debug mode
uv run uvicorn server:app --reload --log-level debug
```

## 📚 Documentation

- [Technical Architecture](docs/technical-solution.md)
- [Async Implementation Guide](docs/async-solution-implementation.md)
- [Deployment Guide](docs/overseas-deployment-guide.md)
- [Monitoring & Operations](docs/monitoring-operations-guide.md)
- [API Documentation](http://localhost:8000/docs) (when server is running)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run tests: `uv run pytest`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Development Guidelines
- Follow PEP 8 for Python code
- Use TypeScript for new frontend components
- Add tests for new features
- Update documentation as needed
- Use conventional commit messages

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Google Gemini API for AI image generation
- FastAPI for the excellent web framework
- Celery for robust task processing
- React for the frontend framework
- All contributors and users of MangakAI

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/MangakAI/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/MangakAI/discussions)
- **Documentation**: [docs/](docs/)

---

**MangakAI v2.0** - Transform your imagination into visual stories with the power of AI! 🎨✨
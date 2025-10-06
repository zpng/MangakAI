#!/bin/bash

# MangakAI Setup Script
# This script sets up the development environment for MangakAI

set -e

echo "🚀 Setting up MangakAI development environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_warning "This script is optimized for macOS. Some steps may need adjustment for other systems."
fi

# Check for required tools
print_status "Checking for required tools..."

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
if [[ $(echo "$PYTHON_VERSION < 3.11" | bc -l) -eq 1 ]]; then
    print_error "Python 3.11 or higher is required. Current version: $PYTHON_VERSION"
    exit 1
fi

print_success "Python $PYTHON_VERSION found"

# Check Node.js
if ! command -v node &> /dev/null; then
    print_error "Node.js is required but not installed."
    print_status "Please install Node.js from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version)
print_success "Node.js $NODE_VERSION found"

# Check Docker (optional)
if command -v docker &> /dev/null; then
    print_success "Docker found"
    DOCKER_AVAILABLE=true
else
    print_warning "Docker not found. Some features may not be available."
    DOCKER_AVAILABLE=false
fi

# Check Redis (optional)
if command -v redis-server &> /dev/null; then
    print_success "Redis found"
    REDIS_AVAILABLE=true
else
    print_warning "Redis not found. Will use Docker for Redis if available."
    REDIS_AVAILABLE=false
fi

# Check PostgreSQL (optional)
if command -v psql &> /dev/null; then
    print_success "PostgreSQL found"
    POSTGRES_AVAILABLE=true
else
    print_warning "PostgreSQL not found. Will use Docker for PostgreSQL if available."
    POSTGRES_AVAILABLE=false
fi

# Setup Python environment
print_status "Setting up Python environment..."

# Check for uv (modern Python package manager)
if ! command -v uv &> /dev/null; then
    print_status "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Install Python dependencies
print_status "Installing Python dependencies..."
uv sync

print_success "Python dependencies installed"

# Setup frontend
print_status "Setting up frontend..."
cd frontend

if [ ! -f "package.json" ]; then
    print_error "Frontend package.json not found"
    exit 1
fi

print_status "Installing frontend dependencies..."
npm install

print_success "Frontend dependencies installed"
cd ..

# Setup environment variables
print_status "Setting up environment variables..."

if [ ! -f ".env" ]; then
    print_status "Creating .env file from template..."
    cp .env.example .env
    print_warning "Please edit .env file with your actual configuration values"
    print_status "Required: GEMINI_API_KEY"
    print_status "Optional: DATABASE_URL, REDIS_URL, AWS credentials"
else
    print_success ".env file already exists"
fi

# Setup database
print_status "Setting up database..."

if [ "$DOCKER_AVAILABLE" = true ]; then
    print_status "Starting database services with Docker..."
    
    # Create docker-compose override for development
    cat > docker-compose.override.yml << EOF
services:
  postgres:
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: mangakai
      POSTGRES_USER: mangakai
      POSTGRES_PASSWORD: password
  
  redis:
    ports:
      - "6379:6379"
EOF

    # Start only database services
    docker-compose up -d postgres redis
    
    print_status "Waiting for database to be ready..."
    sleep 10
    
    # Run database migrations
    print_status "Running database migrations..."
    uv run alembic upgrade head
    
    print_success "Database setup completed"
else
    print_warning "Docker not available. Please set up PostgreSQL and Redis manually."
    print_status "PostgreSQL: Create database 'mangakai' with user 'mangakai'"
    print_status "Redis: Start Redis server on default port 6379"
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p data/output
mkdir -p data/templates
mkdir -p data/examples
mkdir -p data/stories
mkdir -p data/cloud_storage
mkdir -p logs

print_success "Directories created"

# Setup git hooks (optional)
if [ -d ".git" ]; then
    print_status "Setting up git hooks..."
    
    # Pre-commit hook for code formatting
    cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Format Python code with black
if command -v black &> /dev/null; then
    black --check . || (echo "Run 'black .' to format code" && exit 1)
fi

# Format frontend code with prettier
if command -v prettier &> /dev/null; then
    cd frontend && prettier --check . || (echo "Run 'prettier --write .' to format code" && exit 1)
fi
EOF
    
    chmod +x .git/hooks/pre-commit
    print_success "Git hooks setup completed"
fi

# Generate initial migration (if needed)
if [ ! -d "alembic/versions" ] || [ -z "$(ls -A alembic/versions)" ]; then
    print_status "Generating initial database migration..."
    uv run alembic revision --autogenerate -m "Initial migration"
    print_success "Initial migration generated"
fi

# Test the setup
print_status "Testing the setup..."

# Test Python imports
python3 -c "
try:
    import fastapi
    import celery
    import sqlalchemy
    import redis
    print('✅ Python dependencies working')
except ImportError as e:
    print(f'❌ Python import error: {e}')
    exit(1)
"

# Test database connection (if available)
if [ "$DOCKER_AVAILABLE" = true ]; then
    python3 -c "
try:
    from database import check_db_connection
    if check_db_connection():
        print('✅ Database connection working')
    else:
        print('❌ Database connection failed')
except Exception as e:
    print(f'❌ Database test error: {e}')
"
fi

print_success "Setup completed successfully! 🎉"

echo ""
echo "📋 Next steps:"
echo "1. Edit .env file with your API keys and configuration"
echo "2. Start the development servers:"
echo "   Backend:  uv run uvicorn server:app --reload"
echo "   Frontend: cd frontend && npm run dev"
echo "   Celery:   uv run celery -A celery_app worker --loglevel=info"
echo ""
echo "3. Optional: Start monitoring services:"
echo "   Flower:   uv run celery -A celery_app flower"
echo ""
echo "📚 Documentation:"
echo "   - Technical docs: docs/"
echo "   - API docs: http://localhost:8000/docs (after starting backend)"
echo ""
echo "🐛 Troubleshooting:"
echo "   - Check logs in logs/ directory"
echo "   - Verify .env configuration"
echo "   - Ensure all services are running"

# Final checks and warnings
echo ""
print_status "Final checks..."

if [ ! -f ".env" ]; then
    print_error "Please create .env file before starting the application"
fi

if ! grep -q "GEMINI_API_KEY=your_gemini_api_key_here" .env 2>/dev/null; then
    print_warning "Remember to set your GEMINI_API_KEY in .env file"
fi

print_success "Setup script completed! Happy coding! 🚀"
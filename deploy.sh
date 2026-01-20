#!/bin/bash

# Organizer Service Deployment Script
# This script builds and deploys the Organizer Service using Docker Compose
# Works with existing nginx reverse proxy
#
# Usage:
#   ./deploy.sh              # Fast build (uses cache, minimal cleanup)
#   ./deploy.sh --clean      # Full cleanup and rebuild (slower, fixes corruption)
#   ./deploy.sh --help       # Show this help

set -e

# Parse command line arguments
CLEAN_BUILD=false
if [ "$1" = "--clean" ]; then
    CLEAN_BUILD=true
    echo "🚀 Starting Organizer Service Deployment (Clean Build Mode)..."
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --clean    Full cleanup and rebuild (slower, fixes image corruption)"
    echo "  --help     Show this help message"
    echo ""
    echo "Without --clean: Fast build using Docker cache (recommended for development)"
    exit 0
else
    echo "🚀 Starting Organizer Service Deployment (Fast Mode)..."
fi

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

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Determine docker compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    print_error "Docker Compose not found"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    echo
    print_status "Please run setup first:"
    echo "  ./setup-deployment.sh"
    echo
    print_status "Or create .env manually:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Edit with your API keys"
    exit 1
fi

# Check if .env has been configured (contains placeholder values)
if grep -q "your_google_api_key_here" .env 2>/dev/null; then
    print_error ".env file contains placeholder values!"
    echo
    print_status "Please update .env with your actual API keys before deploying."
    echo "  nano .env"
    echo
    print_status "You can use the migration script if you have existing secrets:"
    echo "  ./scripts/migrate-secrets.sh"
    exit 1
fi

# Verify required environment variables are set in .env file
print_status "Checking environment variables in .env file..."
REQUIRED_VARS=("GOOGLE_API_KEY" "OPENROUTER_API_KEY" "AZURE_CLIENT_ID" "AZURE_TENANT_ID" "AZURE_CLIENT_SECRET")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" .env 2>/dev/null || grep "^${var}=" .env | grep -q "your_.*_here\|placeholder\|empty"; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    print_warning "Missing or placeholder environment variables in .env:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    echo
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Deployment cancelled. Please update .env file."
        exit 1
    fi
fi

# Check file permissions
if [ -f ".env" ]; then
    PERMS=$(stat -c "%a" .env 2>/dev/null || stat -f "%Lp" .env 2>/dev/null)
    if [ "$PERMS" != "600" ]; then
        print_warning ".env permissions are $PERMS (should be 600 for security)"
        read -p "Fix permissions? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            chmod 600 .env
            print_success "Fixed .env permissions"
        fi
    fi
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p nginx/ssl nginx/logs

# Build and start services
print_status "Building and starting Docker containers..."

if [ "$CLEAN_BUILD" = true ]; then
    # Full cleanup for clean builds (fixes corruption issues)
    print_status "Performing full cleanup (this may take a moment)..."

    # Stop any running services
    print_status "Stopping existing services..."
    $DOCKER_COMPOSE down || true

    # Remove existing containers and images to ensure clean build
    print_status "Removing existing containers and images..."
    $DOCKER_COMPOSE rm -f || true
    docker rmi organizer-backend organizer-frontend 2>/dev/null || true

    # Clean up dangling resources
    print_status "Cleaning up Docker system..."
    docker system prune -f

    # Build flag for clean build
    BUILD_FLAG="--no-cache"
else
    # Fast build - minimal cleanup, use cache
    print_status "Performing quick cleanup..."
    $DOCKER_COMPOSE down || true
    BUILD_FLAG=""
fi

# Pull latest images (optional)
print_status "Pulling latest base images..."
$DOCKER_COMPOSE pull

# Build the services
if [ "$CLEAN_BUILD" = true ]; then
    print_status "Building services (clean build, no cache)..."
else
    print_status "Building services (fast build, using cache)..."
fi
$DOCKER_COMPOSE build $BUILD_FLAG

# Start services
print_status "Starting services..."
$DOCKER_COMPOSE up -d

# Wait for services to be healthy
print_status "Waiting for services to start and become healthy..."
sleep 10

# Check service status
print_status "Checking service status..."

# Check backend
if curl -f http://localhost:5263/health > /dev/null 2>&1; then
    print_success "Backend is running and healthy on port 5263"
else
    print_warning "Backend health check failed. Checking logs..."
    $DOCKER_COMPOSE logs backend
    print_warning "Backend may still be starting up..."
fi

# Check frontend
if curl -f http://localhost:5264 > /dev/null 2>&1; then
    print_success "Frontend is running on port 5264"
else
    print_warning "Frontend check failed. Checking logs..."
    $DOCKER_COMPOSE logs frontend
    print_warning "Frontend may still be starting up..."
fi

# Display deployment information
echo
print_status "Deployment Summary:"
echo "==================="
echo "Backend:    http://localhost:5263"
echo "Frontend:   http://localhost:5264"
echo
print_status "Your existing nginx should proxy to:"
echo "  - https://organaizer_backend.com2u.selfhost.eu → http://localhost:5263"
echo "  - https://organaizer.com2u.selfhost.eu → http://localhost:5264"
echo
print_status "CORS is configured for:"
echo "  - https://organaizer.com2u.selfhost.eu"
echo "  - https://organaizer_backend.com2u.selfhost.eu"
echo "  - http://localhost:5173, http://localhost:3000"
echo "  - http://192.168.0.95:5173, http://192.168.0.95:3000"
echo "  - http://100.117.42.75:5173, http://100.117.42.75:3000"
echo
print_status "To view logs: $DOCKER_COMPOSE logs -f"
print_status "To stop: $DOCKER_COMPOSE down"
print_status "To restart: $DOCKER_COMPOSE restart"
if [ "$CLEAN_BUILD" = false ]; then
    echo
    print_status "For faster rebuilds: ./deploy.sh"
    print_status "For fixing corruption issues: ./deploy.sh --clean"
fi
echo
print_success "Deployment completed successfully! 🎉"
echo
print_status "Next steps:"
echo "1. Test your deployment: ./test-deployment.sh"
echo "2. Configure your nginx reverse proxy"
echo "3. Check logs if needed: $DOCKER_COMPOSE logs -f"
echo
print_warning "Security reminders:"
echo "  - Keep .env file secure (permissions: 600)"
echo "  - Never commit .env to version control"
echo "  - Rotate API keys if you suspect exposure"
echo "  - See SECURITY.md for detailed security guide"
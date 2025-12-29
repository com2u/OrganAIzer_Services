#!/bin/bash

# Organizer Service Deployment Setup Script
# This script prepares the environment for Docker deployment
# Works with existing nginx reverse proxy

set -e

echo "🔧 Setting up Organizer Service Deployment Environment..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_warning "Running as root. This is usually not necessary for Docker deployment."
fi

# Install Docker (if not installed)
if ! command -v docker &> /dev/null; then
    print_status "Docker not found. Installing Docker..."
    
    # Check if we're on a supported OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [ "$ID" = "ubuntu" ] || [ "$ID" = "debian" ]; then
            # Install Docker on Ubuntu/Debian
            sudo apt-get update
            sudo apt-get install -y ca-certificates curl gnupg
            sudo install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/$ID/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            sudo chmod a+r /etc/apt/keyrings/docker.gpg
            echo \
              "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$ID \
              $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            sudo usermod -aG docker $USER
            print_warning "Added user to docker group. You may need to log out and back in for changes to take effect."
        elif [ "$ID" = "centos" ] || [ "$ID" = "rhel" ] || [ "$ID" = "fedora" ]; then
            # Install Docker on RHEL/Fedora/CentOS
            sudo dnf install -y dnf-plugins-core
            sudo dnf config-manager --add-repo https://download.docker.com/linux/$ID/docker-ce.repo
            sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker $USER
            print_warning "Added user to docker group. You may need to log out and back in for changes to take effect."
        else
            print_warning "Unsupported Linux distribution. Please install Docker manually."
        fi
    else
        print_warning "Cannot detect OS. Please install Docker manually from https://docker.com"
    fi
else
    print_success "Docker is already installed"
fi

# Install Docker Compose (if not installed)
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_status "Docker Compose not found. Installing..."
    
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y docker-compose-plugin
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y docker-compose-plugin
    else
        # Manual installation
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi
else
    print_success "Docker Compose is already installed"
fi

# Verify Docker installation
if docker info > /dev/null 2>&1; then
    print_success "Docker is running correctly"
else
    print_warning "Docker may not be running. Starting Docker service..."
    if command -v systemctl &> /dev/null; then
        sudo systemctl start docker
        sudo systemctl enable docker
    fi
fi

# Create necessary directories
print_status "Creating directory structure..."
mkdir -p backend frontend scripts

# Set proper permissions
chmod +x deploy.sh setup-deployment.sh scripts/migrate-secrets.sh scripts/clean-git-history.sh

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    print_status "Creating .env from template..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success ".env created from .env.example"
    else
        print_warning ".env.example not found, creating basic .env"
        cat > .env << 'EOF'
# Organizer Service Environment Variables
# Copy this file to .env and fill in your actual values

# API Keys
GOOGLE_API_KEY=your_google_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
MODEL=google/gemini-2.5-flash

# Azure Configuration
AZURE_CLIENT_ID=your_azure_client_id
AZURE_TENANT_ID=your_azure_tenant_id
AZURE_CLIENT_SECRET=your_azure_client_secret
EOF
    fi
    print_warning "Please update .env file with your actual API keys before deploying."
    print_status "You can use the migration script to merge existing secrets:"
    echo "  ./scripts/migrate-secrets.sh"
fi

# Set secure permissions on .env
if [ -f ".env" ]; then
    chmod 600 .env
    print_success "Set secure permissions on .env (600)"
fi

# Create a simple test script
cat > test-deployment.sh << 'EOF'
#!/bin/bash
echo "🧪 Testing Organizer Service Deployment..."

# Test backend
echo "Testing backend health endpoint..."
curl -f http://localhost:5263/health && echo " ✅ Backend OK" || echo " ❌ Backend FAILED"

# Test frontend
echo "Testing frontend..."
curl -f http://localhost:5264 > /dev/null && echo " ✅ Frontend OK" || echo " ❌ Frontend FAILED"

# Test CORS headers
echo "Testing CORS headers..."
curl -s -I http://localhost:5263/health | grep -i "access-control-allow-origin" && echo " ✅ CORS configured" || echo " ❌ CORS missing"

echo "Test completed!"
EOF

chmod +x test-deployment.sh

# Display setup summary
echo
echo "=========================================="
echo "Organizer Service Deployment Setup Complete"
echo "=========================================="
echo
print_status "Next steps:"
echo "1. Update the .env file with your actual API keys"
echo "   (Use: ./scripts/migrate-secrets.sh if you have existing secrets)"
echo "2. Run: ./deploy.sh to build and start the services"
echo "3. Test with: ./test-deployment.sh"
echo
print_status "Services will be available at:"
echo "  - Backend: http://localhost:5263"
echo "  - Frontend: http://localhost:5264"
echo
print_status "Configure your existing nginx to proxy:"
echo "  - https://organaizer_backend.com2u.selfhost.eu → http://localhost:5263"
echo "  - https://organaizer.com2u.selfhost.eu → http://localhost:5264"
echo
print_success "Setup completed! 🎉"
echo
print_warning "Security reminders:"
echo "  - Keep .env file secure (permissions: 600)"
echo "  - Never commit .env to version control"
echo "  - Rotate API keys regularly"
echo "  - See SECURITY.md for detailed security guide"
echo
print_status "Security tools available:"
echo "  - ./scripts/migrate-secrets.sh - Merge existing secrets"
echo "  - ./scripts/clean-git-history.sh - Remove secrets from git history"
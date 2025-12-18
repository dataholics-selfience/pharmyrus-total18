#!/bin/bash
# Pharmyrus V5.0 - Multi-Cloud Deployment Script
# Supports: Railway, GCP Cloud Run, AWS ECS, Azure Container Instances

set -e

echo "========================================"
echo "🚀 Pharmyrus V5.0 Deployment Script"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
function print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

function print_error() {
    echo -e "${RED}❌ $1${NC}"
}

function print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check prerequisites
function check_prerequisites() {
    echo "📋 Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker not installed"
        exit 1
    fi
    print_success "Docker found"
    
    if ! command -v git &> /dev/null; then
        print_warning "Git not found (optional)"
    else
        print_success "Git found"
    fi
}

# Load environment variables
function load_env() {
    echo ""
    echo "🔐 Loading environment variables..."
    
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
        print_success "Environment variables loaded from .env"
    else
        print_warning "No .env file found, using system environment"
    fi
    
    # Check required variables
    if [ -z "$EPO_CONSUMER_KEY" ]; then
        print_error "EPO_CONSUMER_KEY not set"
        exit 1
    fi
    
    if [ -z "$EPO_CONSUMER_SECRET" ]; then
        print_error "EPO_CONSUMER_SECRET not set"
        exit 1
    fi
    
    print_success "Required environment variables present"
}

# Build Docker image
function build_image() {
    echo ""
    echo "🏗️  Building Docker image..."
    
    docker build -t pharmyrus-v5:latest -t pharmyrus-v5:$(date +%Y%m%d-%H%M%S) .
    
    if [ $? -eq 0 ]; then
        print_success "Docker image built"
    else
        print_error "Docker build failed"
        exit 1
    fi
}

# Test locally
function test_local() {
    echo ""
    echo "🧪 Testing locally..."
    
    # Stop existing container
    docker stop pharmyrus-v5-test 2>/dev/null || true
    docker rm pharmyrus-v5-test 2>/dev/null || true
    
    # Run test container
    docker run -d \
        --name pharmyrus-v5-test \
        -p 8000:8000 \
        -e EPO_CONSUMER_KEY="$EPO_CONSUMER_KEY" \
        -e EPO_CONSUMER_SECRET="$EPO_CONSUMER_SECRET" \
        -e SERPAPI_KEY="$SERPAPI_KEY" \
        -e GROK_API_KEY="$GROK_API_KEY" \
        pharmyrus-v5:latest
    
    # Wait for startup
    echo "Waiting for server to start..."
    sleep 10
    
    # Test health endpoint
    response=$(curl -s http://localhost:8000/health)
    
    if echo "$response" | grep -q '"status":"healthy"'; then
        print_success "Local test passed"
    else
        print_error "Local test failed"
        docker logs pharmyrus-v5-test
        docker stop pharmyrus-v5-test
        exit 1
    fi
    
    # Cleanup
    docker stop pharmyrus-v5-test
    docker rm pharmyrus-v5-test
}

# Deploy to Railway
function deploy_railway() {
    echo ""
    echo "🚂 Deploying to Railway..."
    
    if ! command -v railway &> /dev/null; then
        print_error "Railway CLI not installed"
        echo "Install: npm install -g @railway/cli"
        exit 1
    fi
    
    # Check if logged in
    if ! railway whoami &> /dev/null; then
        print_error "Not logged in to Railway"
        echo "Run: railway login"
        exit 1
    fi
    
    # Deploy
    railway up
    
    if [ $? -eq 0 ]; then
        print_success "Deployed to Railway"
        
        # Set environment variables
        railway variables set EPO_CONSUMER_KEY="$EPO_CONSUMER_KEY"
        railway variables set EPO_CONSUMER_SECRET="$EPO_CONSUMER_SECRET"
        railway variables set SERPAPI_KEY="$SERPAPI_KEY"
        railway variables set GROK_API_KEY="$GROK_API_KEY"
        railway variables set USE_FIRESTORE="false"
        
        print_success "Environment variables set"
    else
        print_error "Railway deployment failed"
        exit 1
    fi
}

# Deploy to GCP Cloud Run
function deploy_gcp() {
    echo ""
    echo "☁️  Deploying to GCP Cloud Run..."
    
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI not installed"
        echo "Install: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    # Get project ID
    read -p "Enter GCP Project ID: " PROJECT_ID
    read -p "Enter region (default: us-central1): " REGION
    REGION=${REGION:-us-central1}
    
    # Build and push
    gcloud builds submit --tag gcr.io/$PROJECT_ID/pharmyrus-v5
    
    if [ $? -ne 0 ]; then
        print_error "GCP build failed"
        exit 1
    fi
    
    # Deploy
    gcloud run deploy pharmyrus-v5 \
        --image gcr.io/$PROJECT_ID/pharmyrus-v5 \
        --platform managed \
        --region $REGION \
        --allow-unauthenticated \
        --set-env-vars "EPO_CONSUMER_KEY=$EPO_CONSUMER_KEY,EPO_CONSUMER_SECRET=$EPO_CONSUMER_SECRET,SERPAPI_KEY=$SERPAPI_KEY,GROK_API_KEY=$GROK_API_KEY,USE_FIRESTORE=true,FIRESTORE_PROJECT_ID=$PROJECT_ID" \
        --memory 2Gi \
        --cpu 2 \
        --timeout 300
    
    if [ $? -eq 0 ]; then
        print_success "Deployed to GCP Cloud Run"
        
        # Get URL
        SERVICE_URL=$(gcloud run services describe pharmyrus-v5 --region $REGION --format 'value(status.url)')
        echo "Service URL: $SERVICE_URL"
    else
        print_error "GCP deployment failed"
        exit 1
    fi
}

# Deploy to AWS ECS
function deploy_aws() {
    echo ""
    echo "☁️  Deploying to AWS ECS..."
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not installed"
        echo "Install: https://aws.amazon.com/cli/"
        exit 1
    fi
    
    read -p "Enter AWS Region (default: us-east-1): " AWS_REGION
    AWS_REGION=${AWS_REGION:-us-east-1}
    
    read -p "Enter ECS Cluster name: " CLUSTER_NAME
    read -p "Enter ECR repository name: " ECR_REPO
    
    # Login to ECR
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Tag and push
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_URI=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO
    
    docker tag pharmyrus-v5:latest $ECR_URI:latest
    docker push $ECR_URI:latest
    
    if [ $? -eq 0 ]; then
        print_success "Image pushed to ECR"
        print_warning "Manual ECS task definition update required"
        echo "Update task definition with image: $ECR_URI:latest"
    else
        print_error "AWS deployment failed"
        exit 1
    fi
}

# Main menu
function main_menu() {
    echo ""
    echo "Select deployment target:"
    echo "1) Local (Docker)"
    echo "2) Railway"
    echo "3) GCP Cloud Run"
    echo "4) AWS ECS"
    echo "5) Test only (no deployment)"
    echo "6) Exit"
    echo ""
    read -p "Enter choice [1-6]: " choice
    
    case $choice in
        1)
            build_image
            test_local
            echo ""
            print_success "Local deployment complete"
            echo "Access: http://localhost:8000"
            ;;
        2)
            build_image
            test_local
            deploy_railway
            ;;
        3)
            deploy_gcp
            ;;
        4)
            build_image
            deploy_aws
            ;;
        5)
            build_image
            test_local
            ;;
        6)
            echo "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
}

# Run script
check_prerequisites
load_env
main_menu

echo ""
echo "========================================"
echo "🎉 Deployment Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Test health endpoint: curl https://your-url/health"
echo "2. Test search: curl -X POST https://your-url/api/v1/search -H 'Content-Type: application/json' -d '{\"molecule\":\"Aspirin\"}'"
echo "3. Monitor logs for errors"
echo "4. Set up monitoring/alerting"
echo ""

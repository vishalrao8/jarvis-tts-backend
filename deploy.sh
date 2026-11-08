#!/bin/bash
set -e

# Configuration
APP_NAME="jarvis-tts-api"
REGION="asia-south1"
REPO_NAME="jarvis-tts-repo"

echo "Checking GCP Project Configuration..."
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "Error: GCP Project not set."
    echo "Please run: gcloud config set project optimal-brand-514118-a5"
    exit 1
fi
echo "Using Project ID: $PROJECT_ID"

IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${APP_NAME}:latest"

echo "-----------------------------------"
echo "Checking if Artifact Registry repository exists..."
if ! gcloud artifacts repositories describe $REPO_NAME --location=$REGION >/dev/null 2>&1; then
    echo "Creating Artifact Registry repository: $REPO_NAME in $REGION..."
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="Docker repository for JARVIS TTS API"
else
    echo "Repository $REPO_NAME already exists."
fi

echo "-----------------------------------"
echo "Configuring Docker authentication for Artifact Registry..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

echo "-----------------------------------"
echo "Building Docker image ($IMAGE_URL)..."
docker build --platform linux/amd64 -t $IMAGE_URL .

echo "-----------------------------------"
echo "Pushing Docker image to Artifact Registry..."
docker push $IMAGE_URL

echo "-----------------------------------"
echo "Deploying to Cloud Run in Mumbai ($REGION)..."
gcloud run deploy $APP_NAME \
    --image $IMAGE_URL \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --port 8000 \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 5

echo "-----------------------------------"
echo "Deployment complete! Retrieving service URL..."
SERVICE_URL=$(gcloud run services describe $APP_NAME --platform managed --region $REGION --format 'value(status.url)')
echo "Service URL: $SERVICE_URL"

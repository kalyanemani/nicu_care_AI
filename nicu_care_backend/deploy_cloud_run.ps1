# Deploy script for NICU Care Assistant Backend to Google Cloud Run
# Strict GCP Free-Tier Compliance: 0 min instances (scale to zero), 512Mi RAM, 1 vCPU

param(
    [string]$ProjectId = "",
    [string]$Region = "us-central1",
    [string]$ServiceName = "nicu-care-backend"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   NICU Care Backend - GCP Cloud Run Deployment (Free Tier) " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Resolve GCP Project
if (-not $ProjectId) {
    $ProjectId = gcloud config get-value project 2>$null
    if (-not $ProjectId -or $ProjectId -eq "(unset)") {
        Write-Error "No GCP project set. Please run: gcloud config set project <PROJECT_ID> or pass -ProjectId <PROJECT_ID>"
        exit 1
    }
}

Write-Host "[1/5] Active GCP Project: $ProjectId" -ForegroundColor Green
Write-Host "[2/5] Target Region: $Region (GCP Free Tier Eligible)" -ForegroundColor Green

# 2. Enable necessary GCP APIs (Cloud Run, Cloud Build, Artifact Registry)
Write-Host "[3/5] Enabling Cloud Run and Cloud Build APIs..." -ForegroundColor Yellow
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project $ProjectId

# 3. Build & Submit Container Image via Google Cloud Build
$ImageTag = "gcr.io/$ProjectId/$ServiceName:latest"
Write-Host "[4/5] Building container image via Google Cloud Build ($ImageTag)..." -ForegroundColor Yellow
gcloud builds submit --tag $ImageTag --project $ProjectId .

# 4. Deploy to Cloud Run with Free-Tier Constraints
Write-Host "[5/5] Deploying to Cloud Run with scale-to-zero enforcement..." -ForegroundColor Yellow
gcloud run deploy $ServiceName `
    --image $ImageTag `
    --platform managed `
    --region $Region `
    --allow-unauthenticated `
    --min-instances 0 `
    --max-instances 2 `
    --memory 512Mi `
    --cpu 1 `
    --concurrency 80 `
    --timeout 60s `
    --set-env-vars "ENVIRONMENT=production,USE_CLOUD_SPEECH=false,USE_CLOUD_FIRESTORE=false" `
    --project $ProjectId

$ServiceUrl = gcloud run services describe $ServiceName --platform managed --region $Region --project $ProjectId --format "value(status.url)"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "SUCCESS! NICU Care Backend is live at:" -ForegroundColor Green
Write-Host "$ServiceUrl" -ForegroundColor White -BackgroundColor DarkGreen
Write-Host "Swagger Docs: $ServiceUrl/docs" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

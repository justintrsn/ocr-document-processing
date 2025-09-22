# Deployment Guide

## Architecture Overview

The OCR Document Processing System consists of two components:
1. **FastAPI Backend** - Handles OCR processing, LLM enhancement, and business logic
2. **Streamlit Frontend** - Provides web UI for document upload and processing

## Local Development with Docker

### Running Both Services Locally

1. Build and run with Docker Compose:
```bash
# Build and start services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

2. Access the services:
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Streamlit UI: http://localhost:8501

### Running API Only

```bash
# Build the API container
docker build -t ocr-api .

# Run the API container
docker run -d \
  --name ocr-api \
  -p 8000:8000 \
  -e HUAWEI_OCR_API_KEY="your_key_here" \
  -e HUAWEI_OCR_ENDPOINT="your_endpoint_here" \
  -e OPENAI_API_KEY="your_openai_key_here" \
  ocr-api
```

## Cloud Deployment

### Option 1: Deploy API on Cloud Platform + Streamlit Cloud

#### Step 1: Deploy API Backend

**AWS ECS/Fargate:**
```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin your-ecr-url
docker build -t ocr-api .
docker tag ocr-api:latest your-ecr-url/ocr-api:latest
docker push your-ecr-url/ocr-api:latest
```

**Google Cloud Run:**
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT-ID/ocr-api
gcloud run deploy ocr-api --image gcr.io/PROJECT-ID/ocr-api --platform managed
```

**Azure Container Instances:**
```bash
# Build and push to ACR
az acr build --registry yourregistry --image ocr-api .
az container create --resource-group myResourceGroup --name ocr-api --image yourregistry.azurecr.io/ocr-api:latest
```

**Heroku:**
```bash
# Deploy with Heroku container
heroku create your-app-name
heroku container:push web -a your-app-name
heroku container:release web -a your-app-name
```

#### Step 2: Deploy Streamlit Frontend

1. Fork or push this repository to GitHub

2. Go to [Streamlit Cloud](https://streamlit.io/cloud)

3. Create new app:
   - Repository: your-github-username/ocr-document-processing
   - Branch: main
   - Main file path: streamlit_app.py

4. Set environment variables in Streamlit Cloud:
   - Click on "Advanced settings"
   - Add: `OCR_API_URL = https://your-api-deployment-url.com`

5. Deploy!

### Option 2: Deploy Both Services on Same Platform

**Using Docker Compose on a VPS:**

1. SSH into your VPS
2. Install Docker and Docker Compose
3. Clone the repository
4. Create `.env` file with your credentials
5. Run:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

**Using Kubernetes:**

```yaml
# kubernetes-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ocr-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ocr-api
  template:
    metadata:
      labels:
        app: ocr-api
    spec:
      containers:
      - name: ocr-api
        image: your-registry/ocr-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: HUAWEI_OCR_API_KEY
          valueFrom:
            secretKeyRef:
              name: ocr-secrets
              key: huawei-key
---
apiVersion: v1
kind: Service
metadata:
  name: ocr-api-service
spec:
  selector:
    app: ocr-api
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
```

## Environment Variables

### Required for API:
```bash
HUAWEI_OCR_API_KEY=your_huawei_ocr_key
HUAWEI_OCR_ENDPOINT=your_huawei_endpoint
OPENAI_API_KEY=your_openai_key
```

### Required for Streamlit:
```bash
OCR_API_URL=https://your-api-url.com  # Defaults to http://localhost:8000
```

## Production Considerations

### 1. Security
- Use HTTPS for API endpoints
- Implement API authentication (add API keys)
- Use secrets management (AWS Secrets Manager, Azure Key Vault, etc.)
- Enable CORS only for your Streamlit domain

### 2. Scaling
- Use container orchestration (Kubernetes, ECS)
- Implement auto-scaling based on CPU/memory
- Use load balancer for multiple API instances
- Consider queue-based processing for large files

### 3. Monitoring
- Set up logging aggregation (CloudWatch, Stackdriver)
- Implement health checks
- Monitor API response times
- Set up alerts for failures

### 4. Performance
- Use CDN for static assets
- Implement caching for OCR results
- Use connection pooling
- Consider async processing for large documents

## Cost Optimization

### Free/Low-Cost Options:

1. **Railway.app** (API hosting):
   - $5/month for hobby plan
   - Easy deployment from GitHub
   - Automatic SSL

2. **Render.com** (API hosting):
   - Free tier available
   - Automatic deploys from GitHub
   - Built-in SSL

3. **Streamlit Cloud** (Frontend):
   - Free for public apps
   - Easy GitHub integration
   - No configuration needed

4. **Fly.io** (Both services):
   - Free tier with 3 shared VMs
   - Global deployment
   - Built-in SSL

### Example Deployment Commands

**Railway:**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and initialize
railway login
railway init

# Deploy
railway up
```

**Render:**
1. Connect GitHub repository
2. Create new Web Service
3. Set environment variables
4. Deploy automatically

**Fly.io:**
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Launch app
fly launch

# Deploy
fly deploy

# Set secrets
fly secrets set HUAWEI_OCR_API_KEY=xxx OPENAI_API_KEY=xxx
```

## Testing Deployment

After deployment, test your API:

```bash
# Health check
curl https://your-api-url.com/health

# Test OCR processing
curl -X POST https://your-api-url.com/api/v1/ocr \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "https://example.com/document.jpg",
    "processing_options": {
      "enable_ocr": true,
      "enable_llm_enhancement": false
    }
  }'
```

## Troubleshooting

### Common Issues:

1. **API timeout errors:**
   - Increase timeout settings in cloud platform
   - Implement async processing for large files

2. **CORS errors:**
   - Add Streamlit domain to CORS allowed origins
   - Check API gateway settings

3. **Memory issues:**
   - Increase container memory limits
   - Optimize image processing code
   - Implement file size limits

4. **Connection refused:**
   - Check security groups/firewall rules
   - Verify environment variables
   - Check health endpoint

## Support

For deployment issues:
1. Check logs in your cloud platform
2. Test API endpoints individually
3. Verify environment variables are set
4. Check resource limits and quotas
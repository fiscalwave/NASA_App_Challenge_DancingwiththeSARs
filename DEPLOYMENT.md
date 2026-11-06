# Deployment Guide

This guide covers deployment of the NISAR Flood & Wetland Mapping Application to production environments.

## Local Development Deployment

### Prerequisites

- Python 3.8+
- pip (Python package manager)
- Modern web browser

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd NASA_App_Challenge_DancingwiththeSARs
```

### Step 2: Setup Backend

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### Step 3: Configure Environment

Create `.env` file in `backend/` directory (never commit this file — it's gitignored):

```
ASF_USERNAME=your_earthdata_username
ASF_PASSWORD=your_earthdata_password
```

Real [NASA Earthdata](https://urs.earthdata.nasa.gov/) credentials are required — the application uses real ASF/NISAR data only, with no mock data fallback.

### Step 4: Start the Application

```bash
python app_real_api.py
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

This single command now serves both the API **and** the frontend (`index.html`) from one process — no separate frontend server is needed.

### Step 5: Access Application

Open browser to:
```
http://localhost:8000
```

---

## Render.com Deployment (Recommended — Auto-Deploy on Every Git Push)

This is the recommended option for active hackathon development: push code, and the live URL updates automatically within a minute or two, with zero manual redeploy steps.

### Why Render for this project
- One combined service serves both the frontend and the API from a single URL (same-origin, no CORS issues).
- Free tier is sufficient for team testing.
- `render.yaml` in the repo root is a Render "Blueprint" — Render reads it automatically and configures the service for you.
- `autoDeploy: true` means every `git push` to `main` triggers a fresh deployment automatically.

### One-time setup
1. Go to [render.com](https://dashboard.render.com) and sign in (GitHub login is simplest).
2. Click **New** → **Blueprint**.
3. Connect your GitHub account and select the `NASA_App_Challenge_DancingwiththeSARs` repository.
4. Render detects `render.yaml` automatically and shows the `nisar-flood-wetland-mapping` web service.
5. You will be prompted to enter two secret values (these are **not** stored in git, only in Render's dashboard):
   - `ASF_USERNAME` — your NASA Earthdata username
   - `ASF_PASSWORD` — your NASA Earthdata password
6. Click **Apply** / **Create Web Service**. The first build takes a few minutes (installing scientific Python packages).
7. Once live, Render gives you a public URL like `https://nisar-flood-wetland-mapping.onrender.com` — share this with your team.

### Every time you make changes afterward
```bash
git add -A
git commit -m "your change"
git push origin main
```
That's it — Render automatically rebuilds and redeploys. No dashboard steps required after the one-time setup above.

### Notes
- No mock data is used — the deployed app authenticates against real NASA Earthdata/ASF services using the credentials you entered, exactly like local development.
- Free tier services on Render "spin down" after 15 minutes of inactivity and take ~30-60 seconds to wake up on the next request — this is normal, not an error.
- To update credentials later, go to the service's **Environment** tab on the Render dashboard.

---

## Docker Deployment

### Prerequisites

- Docker installed and running
- Docker Compose (optional, for multi-container setup)

### Dockerfile

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["python", "app_real_api.py"]
```

### Building Docker Image

```bash
cd backend
docker build -t nisar-app:2.0 .
```

### Running Docker Container

```bash
docker run -p 8000:8000 \
  -e ASF_API_BASE_URL=https://api.daac.asf.alaska.edu \
  -e NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org \
  nisar-app:2.0
```

### Docker Compose Setup

Create `docker-compose.yml` in project root:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - ASF_API_BASE_URL=https://api.daac.asf.alaska.edu
      - NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org
      - LOG_LEVEL=INFO
    volumes:
      - ./backend/logs:/app/logs
      - ./data:/app/data
    networks:
      - nisar-network

  frontend:
    image: nginx:alpine
    ports:
      - "3000:80"
    volumes:
      - ./index.html:/usr/share/nginx/html/index.html:ro
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - backend
    networks:
      - nisar-network

networks:
  nisar-network:
    driver: bridge
```

### Nginx Configuration

Create `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }

    server {
        listen 80;
        server_name _;

        location / {
            root /usr/share/nginx/html;
            try_files $uri $uri/ =404;
        }

        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### Running with Docker Compose

```bash
docker-compose up -d
```

Access application at `http://localhost:3000`

---

## AWS EC2 Deployment

### Prerequisites

- AWS account
- EC2 instance (t2.medium or larger recommended)
- Ubuntu 20.04 LTS or similar

### Step 1: Launch EC2 Instance

1. Login to AWS Console
2. Create t2.medium instance with Ubuntu 20.04
3. Configure security group:
   - Port 80 (HTTP)
   - Port 443 (HTTPS)
   - Port 8000 (API, restricted)

### Step 2: SSH into Instance

```bash
ssh -i your-key.pem ubuntu@<instance-public-ip>
```

### Step 3: Install Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv nginx

# Install Git
sudo apt-get install -y git

# Clone repository
git clone <repository-url>
cd NASA_App_Challenge_DancingwiththeSARs
```

### Step 4: Setup Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 5: Create Environment File

```bash
sudo nano .env
```

Add:
```
ASF_API_BASE_URL=https://api.daac.asf.alaska.edu
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org
PORT=8000
HOST=127.0.0.1
```

### Step 6: Create Systemd Service

Create `/etc/systemd/system/nisar-backend.service`:

```ini
[Unit]
Description=NISAR Backend API
After=network.target

[Service]
Type=notify
User=ubuntu
WorkingDirectory=/home/ubuntu/NASA_App_Challenge_DancingwiththeSARs/backend
Environment="PATH=/home/ubuntu/NASA_App_Challenge_DancingwiththeSARs/backend/venv/bin"
ExecStart=/home/ubuntu/NASA_App_Challenge_DancingwiththeSARs/backend/venv/bin/python app_real_api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable nisar-backend
sudo systemctl start nisar-backend
```

### Step 7: Configure Nginx

Create `/etc/nginx/sites-available/nisar`:

```nginx
upstream backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name _;

    location / {
        root /home/ubuntu/NASA_App_Challenge_DancingwiththeSARs;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/nisar /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 8: Setup HTTPS (Optional)

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Access Application

```
http://<instance-public-ip>
https://your-domain.com (if HTTPS configured)
```

---

## Google Cloud Run Deployment

### Prerequisites

- Google Cloud account
- `gcloud` CLI installed

### Step 1: Create GCP Project

```bash
gcloud projects create nisar-app
gcloud config set project nisar-app
```

### Step 2: Create `cloudbuild.yaml`

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/nisar-backend:latest', 'backend/']

  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/nisar-backend:latest']

  - name: 'gcr.io/cloud-builders/gke-deploy'
    args:
      - run
      - --filename=k8s/
      - --location=us-central1
      - --filename=backend/

images:
  - 'gcr.io/$PROJECT_ID/nisar-backend:latest'
```

### Step 3: Deploy Backend

```bash
gcloud run deploy nisar-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 600
```

### Step 4: Deploy Frontend

```bash
gcloud storage buckets create gs://nisar-app-frontend
gsutil -m cp index.html gs://nisar-app-frontend/
gsutil -m cp *.js gs://nisar-app-frontend/
gsutil -m cp *.css gs://nisar-app-frontend/

gcloud storage buckets update gs://nisar-app-frontend --web-main-page-suffix=index.html
```

### Step 5: Configure Firewall Rules

```bash
gcloud compute firewall-rules create allow-nisar \
  --allow tcp:80,tcp:443 \
  --source-ranges 0.0.0.0/0
```

---

## Azure App Service Deployment

### Prerequisites

- Azure account
- Azure CLI installed

### Step 1: Create Resource Group

```bash
az group create --name nisar-rg --location eastus
```

### Step 2: Create App Service Plan

```bash
az appservice plan create \
  --name nisar-plan \
  --resource-group nisar-rg \
  --sku B2 \
  --is-linux
```

### Step 3: Create Web App

```bash
az webapp create \
  --resource-group nisar-rg \
  --plan nisar-plan \
  --name nisar-app \
  --runtime "PYTHON:3.11"
```

### Step 4: Configure Deployment

```bash
cd backend
az webapp deployment source config-zip \
  --resource-group nisar-rg \
  --name nisar-app \
  --src app.zip
```

### Step 5: Access Application

```
https://nisar-app.azurewebsites.net
```

---

## Production Checklist

Before deploying to production, verify:

### Backend
- [ ] `.env` file configured with production URLs
- [ ] Error logging enabled
- [ ] Database backups configured
- [ ] API rate limiting enabled
- [ ] HTTPS/SSL certificate installed
- [ ] CORS configured for allowed origins
- [ ] Health checks operational
- [ ] Database connections pooled
- [ ] Monitoring/alerting setup

### Frontend
- [ ] All API endpoints pointing to production servers
- [ ] Minified and optimized assets
- [ ] Caching headers configured
- [ ] CDN/CloudFlare enabled
- [ ] CORS headers set
- [ ] Performance optimized
- [ ] Analytics/monitoring configured

### Security
- [ ] API authentication enabled
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention verified
- [ ] XSS protection enabled
- [ ] CSRF tokens configured
- [ ] Secrets not committed to repository
- [ ] Firewall rules configured
- [ ] Regular security audits scheduled

### Performance
- [ ] Load testing completed
- [ ] Database indexed
- [ ] Caching strategy implemented
- [ ] CDN enabled for static assets
- [ ] API response times < 1 second
- [ ] Frontend page load < 3 seconds

### Monitoring
- [ ] Error tracking enabled (Sentry, etc.)
- [ ] Application performance monitoring
- [ ] Server health checks
- [ ] Database monitoring
- [ ] Uptime monitoring
- [ ] Alert thresholds set

---

## Troubleshooting Deployment

### Backend fails to start

```bash
# Check logs
tail -f backend/logs/app.log

# Verify Python version
python --version

# Check dependencies
pip list

# Reinstall requirements
pip install -r requirements.txt --force-reinstall
```

### API connection errors

```bash
# Test ASF API connectivity
curl https://api.daac.asf.alaska.edu/baseline

# Test Nominatim API
curl "https://nominatim.openstreetmap.org/search?q=Houston&format=json"
```

### Frontend not loading

```bash
# Check Nginx status
sudo systemctl status nginx

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
```

### High memory usage

- Reduce worker processes
- Implement request limiting
- Enable response compression
- Optimize imagery generation

### Slow API responses

- Check database query performance
- Implement caching
- Add database indexes
- Use connection pooling

---

## Backup & Recovery

### Daily Backups

```bash
#!/bin/bash
BACKUP_DIR="/backups/nisar"
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/app_$(date +%Y%m%d).tar.gz /app
```

### Recovery Procedure

```bash
cd /
tar -xzf /backups/nisar/app_20261115.tar.gz
systemctl restart nisar-backend
```

---

## Rollback Procedure

```bash
# Tag stable versions
git tag -a v2.0 -m "Production stable"
git push origin v2.0

# Rollback to previous version
git checkout v1.9
cd backend
pip install -r requirements.txt
systemctl restart nisar-backend
```

---

## Support & Monitoring

### Key Metrics to Monitor

- API response times
- Error rates
- Scene query success rate
- Imagery generation time
- Geocoding accuracy
- Server resource usage
- User session count

### Recommended Monitoring Tools

- **New Relic** - APM and infrastructure
- **Datadog** - Infrastructure and logs
- **Sentry** - Error tracking
- **CloudFlare** - CDN and DDoS protection
- **StatusPage** - Public status page

---

Last Updated: November 2026

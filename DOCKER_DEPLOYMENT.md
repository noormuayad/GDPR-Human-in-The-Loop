# Docker Deployment Guide

This guide explains how to deploy the GDPR Audit application using Docker.

## Prerequisites

- Docker installed on your system
- Docker Compose installed (for docker-compose deployment)
- Basic knowledge of Docker commands

## Quick Start (SQLite)

### 1. Build and Run

```bash
# Navigate to the website directory
cd website

# Build the Docker image
docker build -t gdpr-audit .

# Run the container
docker run -d -p 5000:5000 --name gdpr-audit -v $(pwd)/instance:/app/instance gdpr-audit
```

### 2. Using Docker Compose (Recommended)

```bash
# Build and start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

### 3. Initialize the Database

The first time you run the application, you need to import the data:

```bash
# Run the import script inside the container
docker-compose exec web python import_data.py

# Or if using docker run
docker exec -it gdpr-audit python import_data.py
```

### 4. Access the Application

Open your browser and navigate to: `http://localhost:5000`

**Default credentials:**
- Username: `admin`
- Password: `admin123`

**Important:** Change the default password immediately after first login!

## Production Setup (PostgreSQL)

For production, it's recommended to use PostgreSQL instead of SQLite.

### 1. Update docker-compose.yml

Uncomment the PostgreSQL service in `docker-compose.yml`:

```yaml
services:
  web:
    # ... existing config ...
    environment:
      - DATABASE_URL=postgresql://gdpr_audit:change-this-password@db:5432/gdpr_audit
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    container_name: gdpr_audit_db
    environment:
      - POSTGRES_USER=gdpr_audit
      - POSTGRES_PASSWORD=change-this-password
      - POSTGRES_DB=gdpr_audit
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```

### 2. Create .env File

Create a `.env` file in the website directory:

```bash
SECRET_KEY=your-super-secret-key-change-this-in-production
DATABASE_URL=postgresql://gdpr_audit:change-this-password@db:5432/gdpr_audit
POSTGRES_USER=gdpr_audit
POSTGRES_PASSWORD=change-this-password
POSTGRES_DB=gdpr_audit
```

### 3. Build and Run

```bash
docker-compose up -d
docker-compose exec web python import_data.py
```

## Environment Variables

Create a `.env` file with the following variables:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SECRET_KEY` | Flask secret key for sessions | `change-this-secret-key-in-production` | Yes |
| `DATABASE_URL` | Database connection string | `sqlite:///instance/gdpr_audit.db` | No |
| `POSTGRES_USER` | PostgreSQL username | `gdpr_audit` | No (if using PostgreSQL) |
| `POSTGRES_PASSWORD` | PostgreSQL password | `change-this-password` | No (if using PostgreSQL) |
| `POSTGRES_DB` | PostgreSQL database name | `gdpr_audit` | No (if using PostgreSQL) |

### Generating a Secure SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Docker Commands Reference

### Build

```bash
docker build -t gdpr-audit .
```

### Run

```bash
docker run -d -p 5000:5000 --name gdpr-audit gdpr-audit
```

### Stop

```bash
docker stop gdpr-audit
```

### Remove

```bash
docker rm gdpr-audit
```

### View Logs

```bash
docker logs -f gdpr-audit
```

### Execute Commands in Container

```bash
docker exec -it gdpr-audit bash
```

### Docker Compose Commands

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Rebuild
docker-compose up -d --build
```

## Production Considerations

### 1. Security

- **Change default credentials** immediately
- **Use strong SECRET_KEY** (generate with `secrets.token_hex(32)`)
- **Use PostgreSQL** instead of SQLite for production
- **Set up HTTPS** using a reverse proxy (nginx, traefik)
- **Restrict database access** (don't expose PostgreSQL port)

### 2. Performance

- **Adjust Gunicorn workers** based on CPU cores (default: 4)
- **Use a reverse proxy** (nginx, traefik) for SSL termination
- **Enable caching** for static assets
- **Use a CDN** for static assets if possible

### 3. Monitoring

- **Health checks** are enabled by default (every 30s)
- **Monitor logs** with `docker-compose logs -f`
- **Set up log aggregation** (ELK stack, Grafana, etc.)
- **Monitor resource usage** with `docker stats`

### 4. Backups

For PostgreSQL:

```bash
# Backup
docker-compose exec db pg_dump -U gdpr_audit gdpr_audit > backup.sql

# Restore
docker-compose exec -T db psql -U gdpr_audit gdpr_audit < backup.sql
```

For SQLite:

```bash
# Backup the instance directory
cp -r instance instance.backup
```

### 5. Updates

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Run migrations if needed
docker-compose exec web python add_review_complete_column.py
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs web

# Check if port 5000 is already in use
netstat -tulpn | grep 5000
```

### Database connection errors

- Ensure PostgreSQL container is running: `docker-compose ps`
- Check DATABASE_URL in .env file
- Verify database credentials

### Permission errors with SQLite

```bash
# Fix permissions on host
chmod -R 755 instance/
```

### Import data fails

- Ensure the project data exists in the parent directory
- Check that the CSV files are accessible from the container
- Verify the import script path is correct

## Reverse Proxy Setup (Optional)

### Using Nginx

Create an `nginx.conf`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Run nginx in a separate container:

```yaml
# Add to docker-compose.yml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
  volumes:
    - ./nginx.conf:/etc/nginx/conf.d/default.conf
  depends_on:
    - web
```

## Cloud Deployment

### Render

The `render.yaml` file is already configured for Render deployment. Simply connect your GitHub repository to Render and it will deploy automatically.

### AWS ECS

1. Push image to ECR
2. Create ECS task definition
3. Create ECS service
4. Set up ALB for load balancing

### Google Cloud Run

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT-ID/gdpr-audit

# Deploy to Cloud Run
gcloud run deploy gdpr-audit --image gcr.io/PROJECT-ID/gdpr-audit --platform managed
```

## Support

For issues or questions:
- Check Docker logs: `docker-compose logs -f`
- Review this documentation
- Check the main README.md

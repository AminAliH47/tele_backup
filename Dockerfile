# Tele-Backup Dockerfile
# Multi-stage build for production-ready container

# ==============================================================================
# Base Stage - Common dependencies
# ==============================================================================
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Database clients
    postgresql-client \
    mysql-client \
    sqlite3 \
    # Docker client for volume backups
    docker.io \
    # System utilities
    curl \
    wget \
    git \
    # Build tools (needed for some Python packages)
    gcc \
    g++ \
    libc6-dev \
    libffi-dev \
    libssl-dev \
    # Timezone data
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r tele_backup && useradd -r -g tele_backup tele_backup

# Create application directories
RUN mkdir -p /app /app/db /app/logs /app/backups /app/staticfiles && \
    chown -R tele_backup:tele_backup /app

# Set work directory
WORKDIR /app

# ==============================================================================
# Development Stage
# ==============================================================================
FROM base as development

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ /app/
COPY manage.py /app/

# Create media and static directories
RUN mkdir -p /app/media /app/static

# Set permissions
RUN chown -R tele_backup:tele_backup /app

# Switch to non-root user
USER tele_backup

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/admin/ || exit 1

# Default command for development
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ==============================================================================
# Production Stage
# ==============================================================================
FROM base as production

# Install production dependencies only
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copy application code
COPY src/ /app/
COPY manage.py /app/

# Copy entrypoint scripts
COPY docker/entrypoint.sh /app/entrypoint.sh
COPY docker/celery-entrypoint.sh /app/celery-entrypoint.sh

# Make scripts executable
RUN chmod +x /app/entrypoint.sh /app/celery-entrypoint.sh

# Collect static files
RUN python manage.py collectstatic --noinput --clear

# Set permissions
RUN chown -R tele_backup:tele_backup /app

# Switch to non-root user
USER tele_backup

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/admin/ || exit 1

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command for production (web server)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "config.wsgi:application"]

# ==============================================================================
# Worker Stage - For Celery workers
# ==============================================================================
FROM production as worker

# Health check for worker (different from web server)
HEALTHCHECK --interval=60s --timeout=30s --start-period=30s --retries=3 \
    CMD celery -A config inspect ping || exit 1

# Use celery entrypoint
ENTRYPOINT ["/app/celery-entrypoint.sh"]

# Default command for worker
CMD ["celery", "-A", "config", "worker", "--loglevel=info", "--concurrency=2"]

# ==============================================================================
# Scheduler Stage - For Celery Beat
# ==============================================================================
FROM production as scheduler

# Create celerybeat schedule directory
RUN mkdir -p /app/celerybeat && chown tele_backup:tele_backup /app/celerybeat

# Health check for scheduler
HEALTHCHECK --interval=60s --timeout=30s --start-period=30s --retries=3 \
    CMD test -f /app/celerybeat/celerybeat.pid || exit 1

# Use celery entrypoint
ENTRYPOINT ["/app/celery-entrypoint.sh"]

# Default command for scheduler
CMD ["celery", "-A", "config", "beat", "--loglevel=info", "--scheduler", "django_celery_beat.schedulers:DatabaseScheduler", "--pidfile=/app/celerybeat/celerybeat.pid"]

# ==============================================================================
# Build Arguments and Labels
# ==============================================================================
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=1.0.0

LABEL maintainer="Tele-Backup Team <team@tele-backup.com>" \
    org.label-schema.build-date=$BUILD_DATE \
    org.label-schema.name="Tele-Backup" \
    org.label-schema.description="Self-hosted backup solution with Telegram delivery" \
    org.label-schema.url="https://github.com/yourusername/tele-backup" \
    org.label-schema.vcs-ref=$VCS_REF \
    org.label-schema.vcs-url="https://github.com/yourusername/tele-backup" \
    org.label-schema.vendor="Tele-Backup" \
    org.label-schema.version=$VERSION \
    org.label-schema.schema-version="1.0" 
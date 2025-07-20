#!/bin/bash
# Tele-Backup Django Entrypoint Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Tele-Backup Django Application${NC}"

# Function to wait for database
wait_for_db() {
    echo -e "${YELLOW}⏳ Waiting for database to be ready...${NC}"
    
    python << END
import sys
import time
import psycopg2
import mysql.connector
from django.conf import settings
from django.core.management import execute_from_command_line

# Configure Django settings
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.db import connections
from django.db.utils import OperationalError

db_conn = connections['default']

# Try to connect to database with retries
for i in range(60):
    try:
        db_conn.ensure_connection()
        print("✅ Database is ready!")
        break
    except OperationalError:
        print(f"Database not ready, waiting... ({i+1}/60)")
        time.sleep(1)
else:
    print("❌ Database connection failed after 60 attempts")
    sys.exit(1)
END
}

# Function to run migrations
run_migrations() {
    echo -e "${YELLOW}🔄 Running database migrations...${NC}"
    python manage.py makemigrations --noinput
    python manage.py migrate --noinput
    echo -e "${GREEN}✅ Migrations completed${NC}"
}

# Function to collect static files
collect_static() {
    if [ "$TB_DEBUG" != "True" ]; then
        echo -e "${YELLOW}📦 Collecting static files...${NC}"
        python manage.py collectstatic --noinput --clear
        echo -e "${GREEN}✅ Static files collected${NC}"
    fi
}

# Function to create superuser if specified
create_superuser() {
    if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
        echo -e "${YELLOW}👤 Creating superuser...${NC}"
        python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()

if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser(
        username='$DJANGO_SUPERUSER_USERNAME',
        email='$DJANGO_SUPERUSER_EMAIL',
        password='$DJANGO_SUPERUSER_PASSWORD'
    )
    print("✅ Superuser created successfully")
else:
    print("ℹ️ Superuser already exists")
END
        echo -e "${GREEN}✅ Superuser setup completed${NC}"
    fi
}

# Function to check system requirements
check_requirements() {
    echo -e "${YELLOW}🔍 Checking system requirements...${NC}"
    
    # Check Docker socket if volume backups are configured
    if [ -S "/var/run/docker.sock" ]; then
        echo -e "${GREEN}✅ Docker socket available for volume backups${NC}"
    else
        echo -e "${YELLOW}⚠️ Docker socket not available - volume backups will not work${NC}"
    fi
    
    # Check database clients
    if command -v pg_dump >/dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL client available${NC}"
    fi
    
    if command -v mysqldump >/dev/null 2>&1; then
        echo -e "${GREEN}✅ MySQL client available${NC}"
    fi
    
    if command -v sqlite3 >/dev/null 2>&1; then
        echo -e "${GREEN}✅ SQLite client available${NC}"
    fi
    
    # Check required environment variables
    required_vars=("TB_SECRET_KEY" "TB_ENCRYPTION_KEY")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo -e "${RED}❌ Required environment variable $var is not set${NC}"
            exit 1
        fi
    done
    
    echo -e "${GREEN}✅ System requirements check passed${NC}"
}

# Function to perform system checks
system_checks() {
    echo -e "${YELLOW}🔧 Running Django system checks...${NC}"
    python manage.py check --deploy
    echo -e "${GREEN}✅ System checks passed${NC}"
}

# Function to show startup information
show_startup_info() {
    echo -e "${BLUE}📋 Tele-Backup Startup Information${NC}"
    echo -e "Debug Mode: ${TB_DEBUG:-False}"
    echo -e "Timezone: ${TB_TZ:-UTC}"
    echo -e "Database Engine: ${TB_DB_ENGINE:-sqlite3}"
    echo -e "Message Broker: ${MESSAGE_BROKER_URL:-Not configured}"
    echo -e "Version: ${VERSION:-Development}"
    echo -e "${BLUE}===========================================${NC}"
}

# Main execution
main() {
    show_startup_info
    check_requirements
    
    # Wait for database if not SQLite
    if [ "$TB_DB_ENGINE" != "django.db.backends.sqlite3" ]; then
        wait_for_db
    fi
    
    run_migrations
    collect_static
    create_superuser
    system_checks
    
    echo -e "${GREEN}🎉 Tele-Backup initialization completed successfully!${NC}"
    echo -e "${BLUE}🚀 Starting application with command: $@${NC}"
    
    # Execute the main command
    exec "$@"
}

# Handle signals
_term() {
    echo -e "${YELLOW}📛 Received SIGTERM, shutting down gracefully...${NC}"
    kill -TERM "$child" 2>/dev/null
}

trap _term SIGTERM

# Run main function
main "$@" 
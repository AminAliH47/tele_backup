#!/bin/bash
# Tele-Backup Celery Entrypoint Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}⚡ Starting Tele-Backup Celery Service${NC}"

# Function to wait for message broker
wait_for_broker() {
    echo -e "${YELLOW}⏳ Waiting for message broker (Redis) to be ready...${NC}"
    
    python << END
import sys
import time
import redis
from urllib.parse import urlparse

broker_url = "$MESSAGE_BROKER_URL"
if not broker_url:
    print("❌ MESSAGE_BROKER_URL not configured")
    sys.exit(1)

# Parse Redis URL
parsed = urlparse(broker_url)
host = parsed.hostname or 'localhost'
port = parsed.port or 6379
password = parsed.password

# Try to connect to Redis with retries
for i in range(60):
    try:
        r = redis.Redis(host=host, port=port, password=password, socket_connect_timeout=5)
        r.ping()
        print("✅ Message broker is ready!")
        break
    except Exception as e:
        print(f"Message broker not ready, waiting... ({i+1}/60): {e}")
        time.sleep(1)
else:
    print("❌ Message broker connection failed after 60 attempts")
    sys.exit(1)
END
}

# Function to wait for Django application
wait_for_django() {
    echo -e "${YELLOW}⏳ Waiting for Django application to be ready...${NC}"
    
    python << END
import sys
import time
import os

# Configure Django settings
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
        print("✅ Django application is ready!")
        break
    except OperationalError as e:
        print(f"Django not ready, waiting... ({i+1}/60): {e}")
        time.sleep(1)
else:
    print("❌ Django application connection failed after 60 attempts")
    sys.exit(1)
END
}

# Function to check Celery configuration
check_celery_config() {
    echo -e "${YELLOW}🔧 Checking Celery configuration...${NC}"
    
    python << END
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from celery import current_app

# Check broker connection
try:
    current_app.connection().ensure_connection(max_retries=3)
    print("✅ Celery broker connection OK")
except Exception as e:
    print(f"❌ Celery broker connection failed: {e}")
    exit(1)

# Check if tasks are discovered
tasks = current_app.tasks
task_count = len([name for name in tasks.keys() if not name.startswith('celery.')])
print(f"✅ Discovered {task_count} application tasks")

if task_count == 0:
    print("⚠️ No application tasks found - check task discovery")
END
    
    echo -e "${GREEN}✅ Celery configuration check passed${NC}"
}

# Function to show Celery information
show_celery_info() {
    echo -e "${BLUE}📋 Celery Service Information${NC}"
    echo -e "Broker URL: ${MESSAGE_BROKER_URL}"
    echo -e "Concurrency: ${CELERY_WORKER_CONCURRENCY:-2}"
    echo -e "Log Level: ${CELERY_LOG_LEVEL:-info}"
    echo -e "Service Type: $(basename "$1")"
    echo -e "${BLUE}======================================${NC}"
}

# Function to handle worker-specific initialization
init_worker() {
    echo -e "${YELLOW}🛠️ Initializing Celery worker...${NC}"
    
    # Set worker-specific environment variables
    export CELERY_WORKER_CONCURRENCY=${CELERY_WORKER_CONCURRENCY:-2}
    export CELERY_WORKER_PREFETCH_MULTIPLIER=${CELERY_WORKER_PREFETCH_MULTIPLIER:-4}
    
    echo -e "${GREEN}✅ Worker initialization completed${NC}"
}

# Function to handle beat-specific initialization
init_beat() {
    echo -e "${YELLOW}⏰ Initializing Celery beat scheduler...${NC}"
    
    # Ensure beat schedule directory exists
    mkdir -p /app/celerybeat
    
    # Clean up any stale pidfile
    if [ -f "/app/celerybeat/celerybeat.pid" ]; then
        echo -e "${YELLOW}🧹 Cleaning up stale beat pidfile...${NC}"
        rm -f /app/celerybeat/celerybeat.pid
    fi
    
    echo -e "${GREEN}✅ Beat scheduler initialization completed${NC}"
}

# Function to handle graceful shutdown
cleanup() {
    echo -e "${YELLOW}📛 Received shutdown signal, cleaning up...${NC}"
    
    # Kill background processes
    if [ ! -z "$child" ]; then
        kill -TERM "$child" 2>/dev/null || true
        wait "$child" 2>/dev/null || true
    fi
    
    # Clean up beat pidfile if it exists
    if [ -f "/app/celerybeat/celerybeat.pid" ]; then
        rm -f /app/celerybeat/celerybeat.pid
    fi
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Main execution
main() {
    show_celery_info "$@"
    wait_for_broker
    wait_for_django
    check_celery_config
    
    # Initialize based on command type
    if [[ "$1" == *"worker"* ]]; then
        init_worker
    elif [[ "$1" == *"beat"* ]]; then
        init_beat
    fi
    
    echo -e "${GREEN}🎉 Celery initialization completed successfully!${NC}"
    echo -e "${BLUE}⚡ Starting Celery with command: $@${NC}"
    
    # Execute the main command in background to handle signals
    "$@" &
    child=$!
    wait "$child"
}

# Check if command starts with celery
if [[ "$1" == "celery" ]]; then
    main "$@"
else
    echo -e "${RED}❌ This entrypoint is only for Celery commands${NC}"
    exit 1
fi 
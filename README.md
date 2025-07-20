# 📡 Tele-Backup

**A self-hosted, automated backup solution that delivers your database and Docker volume backups directly to Telegram channels.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-green.svg)](https://www.djangoproject.com/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 Overview

**Tele-Backup** is an open-source, self-hosted backup solution designed for developers and small teams. It runs as a Docker container alongside your existing projects, providing automated, scheduled backups of databases and Docker volumes. Backups are delivered directly to your designated Telegram channels, offering secure, off-site storage and instant notifications.

### ✨ Key Features

- **🗄️ Multiple Database Support**: PostgreSQL, MySQL/MariaDB, SQLite
- **📦 Docker Volume Backups**: Any named Docker volume
- **📅 Flexible Scheduling**: Powerful cron-based scheduling with Celery Beat
- **📱 Telegram Integration**: Direct delivery to Telegram channels with notifications
- **🔐 Security First**: Encrypted storage of sensitive credentials
- **🎛️ Django Admin Interface**: User-friendly web interface for management
- **📊 Execution Logging**: Detailed logs for every backup attempt
- **🌍 Internationalization**: Multi-language support
- **⚙️ Easy Configuration**: Environment variable based setup

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- A Telegram bot token and channel ID ([Setup Guide](#telegram-setup))

### 1. Clone the Repository

```bash
git clone https://github.com/aminalih47/tele-backup.git
cd tele-backup
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Run with Docker Compose

```bash
docker-compose up -d
```

### 4. Access the Admin Interface

1. Open `http://localhost:8000` in your browser
2. Create a superuser: `docker-compose exec tele-backup python manage.py createsuperuser`
3. Log in and configure your sources, destinations, and backup jobs

## 📋 Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Django Configuration
TB_SECRET_KEY=your-very-long-secret-key-here
TB_DEBUG=False
TB_ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com
TB_CSRF_TRUSTED_ORIGINS=https://your-domain.com
TB_TZ=UTC

# Database Configuration (SQLite is default)
TB_DB_ENGINE=django.db.backends.sqlite3
TB_DB_NAME=/app/db/db.sqlite3

# For PostgreSQL:
# TB_DB_ENGINE=django.db.backends.postgresql
# TB_DB_NAME=tele_backup
# TB_DB_USER=postgres
# TB_DB_PASSWORD=your-password
# TB_DB_HOST=postgres
# TB_DB_PORT=5432

# Message Broker (Redis for Celery)
MESSAGE_BROKER_URL=redis://redis:6379/0

# Encryption Key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
TB_ENCRYPTION_KEY=your-encryption-key-here
```

### 🔐 Telegram Setup

1. **Create a Telegram Bot:**

   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Use `/newbot` command and follow instructions
   - Save the bot token (e.g., `1234567890:ABCdefGHIjklMNOpqrSTUvwxyz`)
2. **Get Channel ID:**

   - Add your bot to the target channel as an administrator
   - Send a message to the channel
   - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your channel ID in the response (e.g., `-1001234567890`)
3. **Configure in Admin:**

   - Go to Destinations → Add Destination
   - Enter bot token and channel ID
   - Test the connection using admin actions

## 🗂️ Backup Sources

### Database Backups

**PostgreSQL:**

```
Host: your-postgres-host
Port: 5432
Database: your_database
User: your_user
Password: your_password
```

**MySQL/MariaDB:**

```
Host: your-mysql-host
Port: 3306
Database: your_database
User: your_user
Password: your_password
```

**SQLite:**

```
Database Path: /path/to/your/database.db
```

### Docker Volume Backups

Simply specify the volume name:

```
Volume Name: my_app_data
```

**Important:** The Tele-Backup container needs access to Docker socket:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

## ⏰ Scheduling

Tele-Backup uses cron expressions for scheduling. Here are common examples:

| Schedule         | Cron Expression                | Description                   |
| ---------------- | ------------------------------ | ----------------------------- |
| `0 2 * * *`    | Daily at 2:00 AM               | Most common for daily backups |
| `0 0 * * 0`    | Weekly on Sunday at midnight   | Weekly backups                |
| `0 0 1 * *`    | Monthly on the 1st at midnight | Monthly backups               |
| `0 */6 * * *`  | Every 6 hours                  | Frequent backups              |
| `30 3 * * 1-5` | 3:30 AM on weekdays            | Business day backups          |

### Cron Format

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

## 🐳 Docker Deployment

### Production Docker Compose

```yaml
version: '3.8'

services:
  tele-backup:
    image: telebackup/tele-backup:latest
    container_name: tele-backup
    environment:
      - TB_SECRET_KEY=${TB_SECRET_KEY}
      - TB_DEBUG=False
      - TB_ALLOWED_HOSTS=${TB_ALLOWED_HOSTS}
      - TB_TZ=${TB_TZ}
      - MESSAGE_BROKER_URL=redis://redis:6379/0
      - TB_ENCRYPTION_KEY=${TB_ENCRYPTION_KEY}
    volumes:
      - ./data:/app/db
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./backups:/app/backups
    ports:
      - "8000:8000"
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: tele-backup-redis
    volumes:
      - redis_data:/data
    restart: unless-stopped

  celery-worker:
    image: telebackup/tele-backup:latest
    container_name: tele-backup-worker
    command: celery -A config worker -l info
    environment:
      - TB_SECRET_KEY=${TB_SECRET_KEY}
      - MESSAGE_BROKER_URL=redis://redis:6379/0
      - TB_ENCRYPTION_KEY=${TB_ENCRYPTION_KEY}
    volumes:
      - ./data:/app/db
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./backups:/app/backups
    depends_on:
      - redis
    restart: unless-stopped

  celery-beat:
    image: telebackup/tele-backup:latest
    container_name: tele-backup-scheduler
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    environment:
      - TB_SECRET_KEY=${TB_SECRET_KEY}
      - MESSAGE_BROKER_URL=redis://redis:6379/0
      - TB_ENCRYPTION_KEY=${TB_ENCRYPTION_KEY}
    volumes:
      - ./data:/app/db
    depends_on:
      - redis
    restart: unless-stopped

volumes:
  redis_data:
```

### Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/tele-backup.git
cd tele-backup

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver

# In separate terminals, run Celery:
celery -A config worker -l info
celery -A config beat -l info
```

## 🛠️ Management Commands

Tele-Backup includes several management commands for testing and maintenance:

### Test Backup Flow

```bash
# Test complete backup and Telegram delivery
python manage.py test_backup_flow --source-id 1 --destination-id 1

# Test Telegram connection only
python manage.py test_backup_flow --test-connection

# Send test message
python manage.py test_backup_flow --test-message --destination-id 1
```

### Test Scheduling

```bash
# List all backup jobs
python manage.py test_scheduling --list-jobs

# Execute a specific job manually
python manage.py test_scheduling --job-id 1

# Test cron schedule for a job
python manage.py test_scheduling --test-schedule 1

# Check which jobs are due now
python manage.py test_scheduling --check-due
```

### Database Operations

```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files (for production)
python manage.py collectstatic --noinput
```

## 🔒 Security Considerations

### ⚠️ Important Security Notes

1. **Docker Socket Access**: Tele-Backup requires access to the Docker socket (`/var/run/docker.sock`) to backup Docker volumes. This provides significant access to your Docker environment. Only run Tele-Backup on trusted systems.
2. **Encrypted Credentials**: All sensitive data (Telegram tokens, database passwords) are encrypted in the database using the `TB_ENCRYPTION_KEY`. Keep this key secure and backed up.
3. **Network Security**:

   - Run behind a reverse proxy (nginx, Traefik) in production
   - Use HTTPS with proper SSL certificates
   - Restrict access to the admin interface
4. **Telegram Security**:

   - Use dedicated bot tokens for Tele-Backup
   - Ensure backup channels are private
   - Monitor channel access regularly

### Environment Security

```bash
# Generate a secure secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set proper file permissions
chmod 600 .env
chmod 700 data/
```

## 📊 Monitoring and Troubleshooting

### Admin Interface Features

- **Dashboard**: Overview of backup jobs, execution statistics, and recent activity
- **Execution Logs**: Detailed logs of every backup attempt
- **Real-time Actions**: Test connections, run backups manually, validate schedules
- **Status Indicators**: Visual status indicators for jobs, sources, and destinations

### Log Files

```bash
# Django application logs
docker-compose logs tele-backup

# Celery worker logs
docker-compose logs celery-worker

# Celery beat (scheduler) logs
docker-compose logs celery-beat
```

### Common Issues

**1. Telegram Connection Failed**

- Verify bot token and channel ID
- Ensure bot is added to channel as administrator
- Check network connectivity

**2. Database Connection Failed**

- Verify database credentials
- Check network connectivity to database host
- Ensure database is running and accessible

**3. Docker Volume Backup Failed**

- Verify volume name exists: `docker volume ls`
- Check Docker socket permissions
- Ensure sufficient disk space

**4. Celery Tasks Not Running**

- Check Redis connection
- Verify Celery worker is running
- Check for task queue backlog

## 🔧 Development

### Project Structure

```
tele-backup/
├── src/
│   ├── config/          # Django project configuration
│   ├── destinations/    # Telegram destination management
│   ├── sources/         # Backup source management
│   ├── jobs/           # Backup jobs and scheduling
│   └── static/         # Custom admin CSS/JS
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test sources
python manage.py test destinations
python manage.py test jobs

# Run with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run the test suite: `python manage.py test`
5. Commit your changes: `git commit -am 'Add feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

## 📚 API Reference

### Backup Formats

**SQL Format (`.sql`)**:

- Raw SQL dump files
- Smaller file size
- Human-readable
- Best for databases

**Archive Format (`.tar.gz`)**:

- Compressed archives
- Better for binary data
- Includes metadata
- Best for volumes and large databases

### Supported Databases

| Database   | Version | Notes                  |
| ---------- | ------- | ---------------------- |
| PostgreSQL | 12+     | Uses `pg_dump`       |
| MySQL      | 8.0+    | Uses `mysqldump`     |
| MariaDB    | 10.5+   | Uses `mysqldump`     |
| SQLite     | 3.x     | File copy or `.dump` |

## 🆘 Support

- **Documentation**: [GitHub Wiki](https://github.com/aminalih47/tele-backup/wiki)
- **Issues**: [GitHub Issues](https://github.com/aminalih47/tele-backup/issues)
- **Discussions**: [GitHub Discussions](https://github.com/aminalih47/tele-backup/discussions)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Django](https://www.djangoproject.com/) and [Celery](https://celeryproject.org/)
- Telegram integration via [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- Cron parsing with [croniter](https://github.com/kiorky/croniter)
- Database encryption with [cryptography](https://cryptography.io/)

---

**Tele-Backup** - Simple, secure, and reliable backups delivered to your Telegram! 📡✨

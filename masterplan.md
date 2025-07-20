
# Masterplan: "Tele-Backup" - A Dockerized Backup Bot

## 1. App Overview and Objectives

**Tele-Backup** is an open-source, self-hosted backup solution designed for developers and small teams. It runs as a Docker container alongside a user's existing projects, providing automated, scheduled backups of databases and Docker volumes. Backups are delivered directly to a designated Telegram channel, offering a secure, off-site, and easily accessible storage and notification system.

* **Primary Objective:** To provide a simple, secure, and reliable "set it and forget it" backup tool that integrates seamlessly into a Docker-based development workflow.
* **Core Principles:** Security-first, ease of use through the Django admin panel, and flexibility in configuration.
* **Key Differentiator:** Using Telegram as both the notification channel and the primary destination for backup files, simplifying off-site storage.

## 2. Target Audience

* **Primary:** Individual developers, freelancers, and small teams who manage their own servers and use Docker/Docker Compose for their projects.
* **Secondary:** DevOps engineers looking for a lightweight, scriptable backup solution for non-critical or development environments.

## 3. Core Features and Functionality

* **Backup Sources:**
  * **Databases:** PostgreSQL, MySQL/MariaDB, SQLite.
  * **Docker Volumes:** Any named Docker volume.
* **Backup Formats:**
  * Databases: Raw `.sql` dump or a compressed `.tar.gz` archive.
  * Volumes: Compressed `.tar.gz` archive.
* **Scheduling:** Powerful, cron-based scheduling for each backup job, powered by Celery Beat.
* **Destinations:** Securely upload backup files to one or more user-configured Telegram channels.
* **Notifications:**
  * Send a message to Telegram upon successful backup completion, including the file name and size.
  * Send an immediate, clear alert to Telegram upon any backup failure, including the error reason.
* **Management Interface:** All configuration (sources, destinations, jobs) is managed through the built-in Django admin panel.
* **Logging:** Detailed logs for every backup attempt (success or failure) are stored and viewable in the Django admin.
* **Internationalization (i18n):** The entire Django admin interface will be designed to support multiple languages from day one.

## 4. High-Level Technical Stack

* **Backend Framework:** Python 3 with Django (for the application logic and admin UI).
* **Task Queue & Scheduler:** Celery with Celery Beat (for running asynchronous backup jobs and schedules).
* **Database (Internal):** SQLite is sufficient for the app's own data, as it's lightweight and ships with Python. Can be swapped for PostgreSQL if preferred by the user.
* **Deployment:** Docker & Docker Compose. The application is distributed as a Docker image and designed to run as a service within a user's existing `docker-compose.yml`.
* **Dependencies:**
  * `python-telegram-bot`: To interact with the Telegram Bot API.
  * `cryptography`: For encrypting and decrypting secrets.
  * `croniter`: To parse cron expressions in the application logic.

## 5. Conceptual Data Model

The application will be structured around models split into logical apps:

1. **`Destinations`** (in `destinations` app): Represents a Telegram channel.
   * `name`: A friendly name (e.g., "My Project Channel").
   * `telegram_bot_token`: The bot's API token (encrypted).
   * `telegram_channel_id`: The target channel's ID (encrypted).
2. **`Sources`** (in `sources` app): Represents what to back up.
   * `name`: A friendly name (e.g., "Production DB").
   * `type`: Choice of `Database` or `Volume`.
   * **If Database:** `db_type` (Postgres, MySQL, SQLite), `db_host`, `db_port`, `db_name`, `db_user`, `db_password` (encrypted).
   * **If Volume:** `volume_name`.
3. **`BackupJobs`** (in `jobs` app): The central orchestrator.
   * `source`: ForeignKey to `sources.Sources`.
   * `destination`: ForeignKey to `destinations.Destinations`.
   * `schedule`: A cron expression string (e.g., `0 2 * * *`).
   * `output_format`: Choice of `.sql` or `.tar.gz`.
   * `is_active`: Boolean to easily enable/disable jobs.
4. **`ExecutionLogs`** (in `jobs` app): A record of each run.
   * `job`: ForeignKey to `jobs.BackupJobs`.
   * `timestamp`: The time of the execution.
   * `status`: Choice of `SUCCESS`, `FAILED`.
   * `details`: Text field for storing the output message or error details.
   * `file_size`: Size of the generated backup file.

## 6. Proposed Directory Structure

A modular, multi-app Django project structure is recommended for clarity and maintainability.

```
tele-backup/
├── .dockerignore
├── .gitignore
├── docker-compose.yml       # For development and as an example for users
├── Dockerfile               # Main application Dockerfile
├── manage.py
├── README.md                # CRUCIAL: Explains setup, env vars, and security
└── src/
    ├── destinations/        # App for managing backup destinations
    │   ├── admin.py
    │   ├── apps.py
    │   ├── migrations/
    │   ├── models.py        # Contains Destinations model
    │   └── services/
    │       └── telegram_sender.py
    ├── jobs/                # App for managing jobs, scheduling, and logs
    │   ├── admin.py
    │   ├── apps.py
    │   ├── migrations/
    │   ├── models.py        # Contains BackupJobs, ExecutionLogs models
    │   └── tasks.py         # Celery tasks are defined here
    ├── sources/             # App for managing backup sources
    │   ├── admin.py
    │   ├── apps.py
    │   ├── migrations/
    │   ├── models.py        # Contains Sources model
    │   └── services/
    │       └── backup_runner.py
    ├── config/      # The Django project configuration
    │   ├── __init__.py
    │   ├── asgi.py
    │   ├── celery.py        # Celery configuration
    │   ├── settings.py      # Main settings, i18n, INSTALLED_APPS updated here
    │   ├── urls.py
    │   └── wsgi.py
    └── requirements.txt

```

## 7. Security Considerations

* **Secrets Management:** All sensitive data (Telegram tokens, database passwords) **MUST** be encrypted in the database. Django fields can be customized to use a library like `cryptography` for automatic encryption/decryption.
* **Docker Socket Access:** To back up Docker volumes, the application's container will need the host's Docker socket (`/var/run/docker.sock`) mounted. This provides significant power and should be **clearly documented in the `README.md`** as a security consideration for the user to be aware of.
* **Environment Variables:** All initial configuration (like Django's `SECRET_KEY`) should be passed via environment variables, not hardcoded.

## 8. Development Phases (Detailed)

### Phase 1: Project Scaffolding & Core Models

* [ ] Set up Django project with the proposed multi-app directory structure.
* [ ] Initialize Docker and Docker Compose configuration for local development.
* [ ] Create the `destinations`, `sources`, and `jobs` Django apps and add them to `INSTALLED_APPS`.
* [ ] Define the `Destinations` model in the `destinations` app.
* [ ] Define the `Sources` model in the `sources` app.
* [ ] Define the `BackupJobs` and `ExecutionLogs` models in the `jobs` app.
* [ ] Register all models with the Django admin.
* [ ] Set up i18n configurations in `settings.py`.

### Phase 2: Core Backup Logic

* [ ] Create the `backup_runner.py` service in the `sources` app.
* [ ] Implement functions for PostgreSQL, MySQL, SQLite, and Docker Volume backups.
* [ ] Write unit tests for each backup method.

### Phase 3: Telegram Integration

* [ ] Create the `telegram_sender.py` service in the `destinations` app.
* [ ] Implement functions to upload a file and send a text message to Telegram.
* [ ] Create a temporary management command to test the end-to-end flow (backup + upload).
* [ ] Ensure proper error handling for Telegram API interactions.

### Phase 4: Scheduling and Task Integration

* [ ] Integrate Celery and Celery Beat into the Django project.
* [ ] Create a primary Celery task, `execute_backup_job`, that takes a `BackupJob` ID. This task will perform the backup, send the file to Telegram, and create an `ExecutionLog`. It is designed to be triggered on-demand.
* [ ] Create a second Celery Beat task, `check_due_jobs`, configured in `settings.py` to run on a one-minute schedule.
* [ ] In the `check_due_jobs` task, query all active `BackupJob`s. For each job, use a library like `croniter` to parse its `schedule` field and determine if it should run at the current minute.
* [ ] If a job is due, `check_due_jobs` will asynchronously call the `execute_backup_job` task with the appropriate `BackupJob` ID.

### Phase 5: Polishing, Documentation, and Release

* [ ] Refine the Django admin interface for better usability.
* [ ] Write a comprehensive `README.md` explaining the entire setup process.
* [ ] Create an example `docker-compose.yml` for users.
* [ ] Perform end-to-end testing of the entire workflow.
* [ ] Tag version `1.0.0` and publish the Docker image to a registry.

## 9. Potential Challenges and Solutions

* **Challenge:** Ensuring compatibility with different versions of Postgres/MySQL.
  * **Solution:** Use standard flags for `pg_dump` and `mysqldump` that are widely compatible. Document the tested versions.
* **Challenge:** Handling very large backup files that might exceed Telegram's file size limit (currently 2 GB for bots) or cause timeouts.
  * **Solution (v1):** Document the limitation.
  * **Solution (v2):** Implement multi-part compressed archives and upload them in chunks.
* **Challenge:** Security of the mounted Docker socket.
  * **Solution:** This is a feature, not a bug, but it must be addressed with clear, prominent documentation explaining the risk to the user.

## 10. Future Expansion Possibilities

* **More Destinations:** Add support for other backup destinations like AWS S3, Dropbox, or Google Drive. The `destinations` app is already structured to make this easy.
* **More Sources:** Add support for other databases like MongoDB or Redis within the `sources` app.
* **Retention Policy Enforcement:** Add a Celery task that runs daily to clean up old backups from Telegram channels based on a policy set in the `BackupJob`.
* **Web UI:** A simple front-end dashboard (using HTMX or a minimal JS framework) outside of the admin panel for viewing backup status.

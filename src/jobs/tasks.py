import os
import time
import logging
from datetime import datetime

from celery import shared_task
from croniter import croniter
from django.utils import timezone as django_timezone

from jobs.models import BackupJobs, ExecutionLogs
from sources.services.backup_runner import create_backup, BackupError
from destinations.services.telegram_sender import send_backup_notification_sync, TelegramError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def execute_backup_job(self, job_id: int) -> dict:
    """
    Primary Celery task that performs backup, uploads to Telegram, and creates ExecutionLog.

    Args:
        job_id: The ID of the BackupJob to execute

    Returns:
        dict: Execution result with status and details
    """
    start_time = time.time()
    execution_log = None
    backup_file_path = None

    try:
        # Get the backup job
        try:
            job = BackupJobs.objects.get(id=job_id, is_active=True)
        except BackupJobs.DoesNotExist:
            error_msg = f"BackupJob with ID {job_id} not found or inactive"
            logger.error(error_msg)
            return {
                'status': 'failed',
                'error': error_msg,
                'job_id': job_id
            }

        logger.info(f"Starting backup job: {job} (ID: {job_id})")

        # Create initial execution log
        execution_log = ExecutionLogs.objects.create(
            job=job,
            status='failed',  # Will be updated on success
            details='Backup job started'
        )

        try:
            # Step 1: Create backup
            logger.info(f"Creating backup for source: {job.source.name}")
            backup_file_path, file_size = create_backup(job.source, job.output_format)

            duration = time.time() - start_time
            logger.info(f"Backup created successfully: {backup_file_path} ({file_size} bytes) in {duration:.1f}s")

            # Step 2: Send to Telegram
            logger.info(f"Sending backup to Telegram destination: {job.destination.name}")

            source_type = job.source.get_type_display()
            if job.source.type == 'database' and job.source.db_type:
                source_type += f" ({job.source.get_db_type_display()})"

            telegram_success = send_backup_notification_sync(
                destination=job.destination,
                file_path=backup_file_path,
                source_name=job.source.name,
                backup_type=source_type,
                success=True,
                duration=duration
            )

            if not telegram_success:
                raise TelegramError("Failed to send backup notification to Telegram")

            # Step 3: Update execution log with success
            execution_log.status = 'success'
            execution_log.file_size = file_size
            execution_log.details = f"Backup completed successfully in {duration:.1f}s. File sent to Telegram."
            execution_log.save()

            logger.info(f"Backup job completed successfully: {job}")

            return {
                'status': 'success',
                'job_id': job_id,
                'file_size': file_size,
                'duration': duration,
                'backup_file': os.path.basename(backup_file_path) if backup_file_path else None
            }

        except BackupError as e:
            error_msg = f"Backup failed: {str(e)}"
            logger.error(f"Backup error for job {job_id}: {error_msg}")

            # Send failure notification to Telegram
            try:
                send_backup_notification_sync(
                    destination=job.destination,
                    source_name=job.source.name,
                    backup_type=source_type if 'source_type' in locals() else job.source.get_type_display(),
                    success=False,
                    error_message=str(e)
                )
            except Exception as telegram_error:
                logger.error(f"Failed to send failure notification to Telegram: {telegram_error}")

            # Update execution log
            if execution_log:
                execution_log.details = error_msg
                execution_log.save()

            return {
                'status': 'failed',
                'job_id': job_id,
                'error': error_msg
            }

        except TelegramError as e:
            error_msg = f"Telegram upload failed: {str(e)}"
            logger.error(f"Telegram error for job {job_id}: {error_msg}")

            # Update execution log
            if execution_log:
                execution_log.details = error_msg
                execution_log.save()

            return {
                'status': 'failed',
                'job_id': job_id,
                'error': error_msg
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error for job {job_id}: {error_msg}", exc_info=True)

            # Try to send failure notification
            try:
                send_backup_notification_sync(
                    destination=job.destination,
                    source_name=job.source.name,
                    backup_type=job.source.get_type_display(),
                    success=False,
                    error_message=str(e)
                )
            except Exception as telegram_error:
                logger.error(f"Failed to send failure notification to Telegram: {telegram_error}")

            # Update execution log
            if execution_log:
                execution_log.details = error_msg
                execution_log.save()

            # Retry the task if retries are available
            if self.request.retries < self.max_retries:
                logger.info(f"Retrying backup job {job_id} (attempt {self.request.retries + 1}/{self.max_retries})")
                raise self.retry(countdown=60 * (self.request.retries + 1))

            return {
                'status': 'failed',
                'job_id': job_id,
                'error': error_msg,
                'retries_exhausted': True
            }

    finally:
        # Clean up backup file
        if backup_file_path and os.path.exists(backup_file_path):
            try:
                os.unlink(backup_file_path)
                logger.debug(f"Cleaned up backup file: {backup_file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up backup file {backup_file_path}: {e}")


@shared_task
def check_due_jobs() -> dict:
    """
    Celery Beat task that runs every minute to check which BackupJobs should be executed.

    Uses croniter to parse cron expressions and determine if jobs are due.

    Returns:
        dict: Summary of jobs checked and triggered
    """
    now = django_timezone.now()
    logger.debug(f"Checking due jobs at {now}")

    triggered_jobs = []
    checked_jobs = 0
    errors = []

    try:
        # Get all active backup jobs
        active_jobs = BackupJobs.objects.filter(is_active=True).select_related('source', 'destination')

        for job in active_jobs:
            checked_jobs += 1

            try:
                # Parse the cron expression with timezone-naive datetime
                now_naive = now.replace(tzinfo=None)
                cron = croniter(job.schedule, now_naive)

                # Check if the job should run in the current minute
                # Get the most recent scheduled time
                prev_run_time = cron.get_prev(datetime)
                time_since_prev = (now_naive - prev_run_time).total_seconds()

                # If the previous scheduled time was within the last 70 seconds, run the job
                # (70 seconds gives some buffer for processing delays)
                if time_since_prev <= 70:
                    # Check if this job has already been executed recently to avoid duplicates
                    recent_executions = ExecutionLogs.objects.filter(
                        job=job,
                        created_at__gte=now - django_timezone.timedelta(minutes=2)
                    ).count()

                    if recent_executions == 0:
                        logger.info(f"Triggering backup job: {job} (scheduled: {job.schedule})")

                        # Execute the backup job asynchronously
                        result = execute_backup_job.delay(job.id)

                        triggered_jobs.append({
                            'job_id': job.id,
                            'job_name': str(job),
                            'schedule': job.schedule,
                            'task_id': result.id
                        })
                    else:
                        logger.debug(f"Skipping job {job} - already executed recently")

            except Exception as e:
                error_msg = f"Error processing job {job} (ID: {job.id}): {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

    except Exception as e:
        error_msg = f"Error in check_due_jobs: {str(e)}"
        logger.error(error_msg, exc_info=True)
        errors.append(error_msg)

    result = {
        'timestamp': now.isoformat(),
        'checked_jobs': checked_jobs,
        'triggered_jobs': len(triggered_jobs),
        'triggered_job_details': triggered_jobs,
        'errors': errors
    }

    if triggered_jobs:
        logger.info(f"Check due jobs completed: {len(triggered_jobs)} jobs triggered out of {checked_jobs} checked")
    else:
        logger.debug(f"Check due jobs completed: no jobs triggered out of {checked_jobs} checked")

    return result


@shared_task
def test_job_schedule(job_id: int, check_minutes: int = 60) -> dict:
    """
    Helper task to test when a job would run based on its cron schedule.

    Args:
        job_id: The ID of the BackupJob to test
        check_minutes: Number of minutes into the future to check

    Returns:
        dict: Schedule test results
    """
    try:
        job = BackupJobs.objects.get(id=job_id)
        now = django_timezone.now()

        # Parse the cron expression
        cron = croniter(job.schedule, now.replace(tzinfo=None))

        # Get next execution times
        next_runs = []
        for _ in range(10):  # Get next 10 scheduled times
            next_run = cron.get_next(datetime)
            if (next_run - now.replace(tzinfo=None)).total_seconds() > check_minutes * 60:
                break
            next_runs.append(next_run.isoformat())

        return {
            'job_id': job_id,
            'job_name': str(job),
            'schedule': job.schedule,
            'current_time': now.isoformat(),
            'next_runs': next_runs,
            'is_valid_cron': True
        }

    except BackupJobs.DoesNotExist:
        return {
            'job_id': job_id,
            'error': 'Job not found',
            'is_valid_cron': False
        }
    except Exception as e:
        return {
            'job_id': job_id,
            'error': str(e),
            'is_valid_cron': False
        }


@shared_task
def cleanup_old_execution_logs(days_to_keep: int = 30) -> dict:
    """
    Maintenance task to clean up old execution logs.

    Args:
        days_to_keep: Number of days of logs to retain

    Returns:
        dict: Cleanup results
    """
    cutoff_date = django_timezone.now() - django_timezone.timedelta(days=days_to_keep)

    try:
        deleted_count, _ = ExecutionLogs.objects.filter(
            created_at__lt=cutoff_date
        ).delete()

        logger.info(f"Cleaned up {deleted_count} execution logs older than {days_to_keep} days")

        return {
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat(),
            'days_kept': days_to_keep,
            'status': 'success'
        }

    except Exception as e:
        error_msg = f"Error cleaning up execution logs: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return {
            'error': error_msg,
            'status': 'failed'
        }

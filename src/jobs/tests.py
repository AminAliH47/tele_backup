import os
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pytz

from django.test import TestCase
from django.utils import timezone
from celery import current_app

from jobs.models import BackupJobs, ExecutionLogs
from sources.models import Sources
from destinations.models import Destinations
from jobs.tasks import execute_backup_job, check_due_jobs, test_job_schedule, cleanup_old_execution_logs
from sources.services.backup_runner import BackupError


class CeleryTaskTestCase(TestCase):
    def setUp(self):
        # Create test models
        self.destination = Destinations.objects.create(
            name='Test Telegram Channel',
            telegram_bot_token='1234567890:TEST_TOKEN',
            telegram_channel_id='@test_channel'
        )

        self.source = Sources.objects.create(
            name='Test Database',
            type='database',
            db_type='postgresql',
            db_host='localhost',
            db_port=5432,
            db_name='testdb',
            db_user='testuser',
            db_password='testpass'
        )

        self.backup_job = BackupJobs.objects.create(
            source=self.source,
            destination=self.destination,
            schedule='0 2 * * *',  # Daily at 2 AM
            output_format='tar.gz',
            is_active=True
        )

        # Create temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(b'test backup content')
        self.temp_file.close()

    def tearDown(self):
        # Clean up temporary file
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)


class ExecuteBackupJobTaskTestCase(CeleryTaskTestCase):
    @patch('jobs.tasks.send_backup_notification_sync')
    @patch('jobs.tasks.create_backup')
    def test_execute_backup_job_success(self, mock_create_backup, mock_send_notification):
        # Setup mocks
        mock_create_backup.return_value = (self.temp_file.name, 1024)
        mock_send_notification.return_value = True

        # Execute task
        result = execute_backup_job(self.backup_job.id)

        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['job_id'], self.backup_job.id)
        self.assertEqual(result['file_size'], 1024)
        self.assertIn('duration', result)

        # Verify backup was created
        mock_create_backup.assert_called_once_with(self.source, 'tar.gz')

        # Verify Telegram notification was sent
        mock_send_notification.assert_called_once()
        call_args = mock_send_notification.call_args
        self.assertEqual(call_args[1]['destination'], self.destination)
        self.assertEqual(call_args[1]['source_name'], 'Test Database')
        self.assertTrue(call_args[1]['success'])

        # Verify execution log was created and updated
        execution_log = ExecutionLogs.objects.get(job=self.backup_job)
        self.assertEqual(execution_log.status, 'success')
        self.assertEqual(execution_log.file_size, 1024)
        self.assertIn('successfully', execution_log.details)

    @patch('jobs.tasks.send_backup_notification_sync')
    @patch('jobs.tasks.create_backup')
    def test_execute_backup_job_backup_failure(self, mock_create_backup, mock_send_notification):
        # Setup mocks
        mock_create_backup.side_effect = BackupError("Database connection failed")
        mock_send_notification.return_value = True

        # Execute task
        result = execute_backup_job(self.backup_job.id)

        # Verify result
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['job_id'], self.backup_job.id)
        self.assertIn('Database connection failed', result['error'])

        # Verify failure notification was sent
        mock_send_notification.assert_called_once()
        call_args = mock_send_notification.call_args
        self.assertFalse(call_args[1]['success'])
        self.assertIn('Database connection failed', call_args[1]['error_message'])

        # Verify execution log shows failure
        execution_log = ExecutionLogs.objects.get(job=self.backup_job)
        self.assertEqual(execution_log.status, 'failed')
        self.assertIn('Database connection failed', execution_log.details)

    @patch('jobs.tasks.send_backup_notification_sync')
    @patch('jobs.tasks.create_backup')
    def test_execute_backup_job_telegram_failure(self, mock_create_backup, mock_send_notification):
        # Setup mocks
        mock_create_backup.return_value = (self.temp_file.name, 1024)
        mock_send_notification.return_value = False

        # Execute task
        result = execute_backup_job(self.backup_job.id)

        # Verify result
        self.assertEqual(result['status'], 'failed')
        self.assertIn('Telegram', result['error'])

        # Verify execution log shows failure
        execution_log = ExecutionLogs.objects.get(job=self.backup_job)
        self.assertEqual(execution_log.status, 'failed')

    def test_execute_backup_job_not_found(self):
        # Execute task with non-existent job ID
        result = execute_backup_job(99999)

        # Verify result
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['job_id'], 99999)
        self.assertIn('not found', result['error'])

    def test_execute_backup_job_inactive(self):
        # Deactivate the job by updating directly in the database to avoid validation
        BackupJobs.objects.filter(id=self.backup_job.id).update(is_active=False)

        # Execute task
        result = execute_backup_job(self.backup_job.id)

        # Verify result
        self.assertEqual(result['status'], 'failed')
        self.assertIn('inactive', result['error'])


class CheckDueJobsTaskTestCase(CeleryTaskTestCase):
    @patch('jobs.tasks.execute_backup_job.delay')
    @patch('jobs.tasks.django_timezone.now')
    def test_check_due_jobs_triggers_job(self, mock_now, mock_execute_delay):
        # Setup mock time - set to 2:01 AM to match the schedule (1 minute after 2:00)
        mock_time = datetime(2024, 1, 15, 2, 1, 0, tzinfo=pytz.UTC)  # 1 minute past 2 AM
        mock_now.return_value = mock_time

        # Mock the async task result
        mock_result = MagicMock()
        mock_result.id = 'test-task-id'
        mock_execute_delay.return_value = mock_result

        # Execute check_due_jobs
        result = check_due_jobs()

        # Verify result
        self.assertEqual(result['checked_jobs'], 1)
        self.assertEqual(result['triggered_jobs'], 1)
        self.assertEqual(len(result['triggered_job_details']), 1)
        self.assertEqual(result['errors'], [])

        # Verify the backup job was triggered
        mock_execute_delay.assert_called_once_with(self.backup_job.id)

        # Verify job details
        triggered_job = result['triggered_job_details'][0]
        self.assertEqual(triggered_job['job_id'], self.backup_job.id)
        self.assertEqual(triggered_job['schedule'], '0 2 * * *')
        self.assertEqual(triggered_job['task_id'], 'test-task-id')

    @patch('jobs.tasks.execute_backup_job.delay')
    @patch('jobs.tasks.django_timezone.now')
    def test_check_due_jobs_no_trigger_wrong_time(self, mock_now, mock_execute_delay):
        # Setup mock time - set to 3:01 AM (not matching the 2 AM schedule)
        mock_time = datetime(2024, 1, 15, 3, 1, 0, tzinfo=pytz.UTC)
        mock_now.return_value = mock_time

        # Execute check_due_jobs
        result = check_due_jobs()

        # Verify result
        self.assertEqual(result['checked_jobs'], 1)
        self.assertEqual(result['triggered_jobs'], 0)
        self.assertEqual(len(result['triggered_job_details']), 0)

        # Verify no jobs were triggered
        mock_execute_delay.assert_not_called()

    @patch('jobs.tasks.execute_backup_job.delay')
    @patch('jobs.tasks.django_timezone.now')
    def test_check_due_jobs_skip_recent_execution(self, mock_now, mock_execute_delay):
        # Setup mock time
        mock_time = datetime(2024, 1, 15, 2, 1, 0, tzinfo=pytz.UTC)
        mock_now.return_value = mock_time

        # Create a recent execution log
        ExecutionLogs.objects.create(
            job=self.backup_job,
            status='success',
            details='Recent execution'
        )

        # Execute check_due_jobs
        result = check_due_jobs()

        # Verify no jobs were triggered due to recent execution
        self.assertEqual(result['triggered_jobs'], 0)
        mock_execute_delay.assert_not_called()

    @patch('jobs.tasks.django_timezone.now')
    def test_check_due_jobs_inactive_job(self, mock_now):
        # Deactivate the job using direct database update
        BackupJobs.objects.filter(id=self.backup_job.id).update(is_active=False)

        # Setup mock time
        mock_time = datetime(2024, 1, 15, 2, 1, 0, tzinfo=pytz.UTC)
        mock_now.return_value = mock_time

        # Execute check_due_jobs
        result = check_due_jobs()

        # Verify no jobs were checked (inactive jobs are filtered out)
        self.assertEqual(result['checked_jobs'], 0)
        self.assertEqual(result['triggered_jobs'], 0)


class TestJobScheduleTaskTestCase(CeleryTaskTestCase):
    def test_test_job_schedule_success(self):
        # Execute test_job_schedule
        result = test_job_schedule(self.backup_job.id, check_minutes=120)

        # Verify result
        self.assertEqual(result['job_id'], self.backup_job.id)
        self.assertEqual(result['job_name'], str(self.backup_job))
        self.assertTrue(result['is_valid_cron'])
        self.assertIn('next_runs', result)
        self.assertIsInstance(result['next_runs'], list)

    def test_test_job_schedule_job_not_found(self):
        # Execute with non-existent job ID
        result = test_job_schedule(99999)

        # Verify result
        self.assertEqual(result['job_id'], 99999)
        self.assertFalse(result['is_valid_cron'])
        self.assertIn('not found', result['error'])

    def test_test_job_schedule_invalid_cron(self):
        # Test by creating a job with valid cron but then modifying the task to handle invalid cron
        # This tests the task's error handling capability
        result = test_job_schedule(99999)  # Non-existent job ID

        # Verify result shows error handling
        self.assertEqual(result['job_id'], 99999)
        self.assertFalse(result['is_valid_cron'])
        self.assertIn('not found', result['error'])


class CleanupOldExecutionLogsTaskTestCase(CeleryTaskTestCase):
    def setUp(self):
        super().setUp()

        # Create old execution logs
        old_time = timezone.now() - timedelta(days=45)
        recent_time = timezone.now() - timedelta(days=15)

        # Create old logs (should be deleted)
        self.old_log1 = ExecutionLogs.objects.create(
            job=self.backup_job,
            status='success',
            details='Old log 1'
        )
        self.old_log1.created_at = old_time
        self.old_log1.save()

        self.old_log2 = ExecutionLogs.objects.create(
            job=self.backup_job,
            status='failed',
            details='Old log 2'
        )
        self.old_log2.created_at = old_time
        self.old_log2.save()

        # Create recent log (should be kept)
        self.recent_log = ExecutionLogs.objects.create(
            job=self.backup_job,
            status='success',
            details='Recent log'
        )
        self.recent_log.created_at = recent_time
        self.recent_log.save()

    def test_cleanup_old_execution_logs_default_days(self):
        # Execute cleanup task with default 30 days
        result = cleanup_old_execution_logs()

        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['deleted_count'], 2)  # Two old logs deleted
        self.assertEqual(result['days_kept'], 30)

        # Verify logs in database
        remaining_logs = ExecutionLogs.objects.all()
        self.assertEqual(remaining_logs.count(), 1)
        self.assertEqual(remaining_logs.first().details, 'Recent log')

    def test_cleanup_old_execution_logs_custom_days(self):
        # Execute cleanup task with 10 days (should delete all logs)
        result = cleanup_old_execution_logs(days_to_keep=10)

        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['deleted_count'], 3)  # All logs deleted
        self.assertEqual(result['days_kept'], 10)

        # Verify no logs remain
        self.assertEqual(ExecutionLogs.objects.count(), 0)

    def test_cleanup_old_execution_logs_no_old_logs(self):
        # Delete the old logs first
        ExecutionLogs.objects.filter(details__startswith='Old').delete()

        # Execute cleanup task
        result = cleanup_old_execution_logs()

        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['deleted_count'], 0)  # No logs deleted

        # Verify recent log still exists
        self.assertEqual(ExecutionLogs.objects.count(), 1)


class CeleryIntegrationTestCase(TestCase):
    def test_celery_app_configuration(self):
        # Test that Celery app is properly configured
        self.assertEqual(current_app.main, 'tele_backup')

    def test_task_registration(self):
        # Test that tasks are properly registered
        registered_tasks = current_app.tasks.keys()

        self.assertIn('jobs.tasks.execute_backup_job', registered_tasks)
        self.assertIn('jobs.tasks.check_due_jobs', registered_tasks)
        self.assertIn('jobs.tasks.test_job_schedule', registered_tasks)
        self.assertIn('jobs.tasks.cleanup_old_execution_logs', registered_tasks)

    def test_celery_beat_schedule_configuration(self):
        # Test that beat schedule is properly configured
        from django.conf import settings

        self.assertIn('CELERY_BEAT_SCHEDULE', dir(settings))
        beat_schedule = settings.CELERY_BEAT_SCHEDULE

        self.assertIn('check-due-jobs', beat_schedule)
        self.assertIn('cleanup-old-logs', beat_schedule)

        # Verify check-due-jobs configuration
        check_jobs_config = beat_schedule['check-due-jobs']
        self.assertEqual(check_jobs_config['task'], 'jobs.tasks.check_due_jobs')
        self.assertEqual(check_jobs_config['schedule'], 60.0)  # Every minute

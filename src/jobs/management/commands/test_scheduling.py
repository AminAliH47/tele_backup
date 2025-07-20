import time
from django.core.management.base import BaseCommand, CommandError

from jobs.models import BackupJobs
from jobs.tasks import execute_backup_job, check_due_jobs, test_job_schedule


class Command(BaseCommand):
    help = 'Test the scheduling and task execution system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job-id',
            type=int,
            help='Execute a specific backup job by ID'
        )
        parser.add_argument(
            '--check-due',
            action='store_true',
            help='Run the check_due_jobs task manually'
        )
        parser.add_argument(
            '--test-schedule',
            type=int,
            help='Test the schedule for a specific job ID'
        )
        parser.add_argument(
            '--list-jobs',
            action='store_true',
            help='List all backup jobs'
        )

    def handle(self, *args, **options):
        job_id = options.get('job_id')
        check_due = options.get('check_due', False)
        test_schedule_id = options.get('test_schedule')
        list_jobs = options.get('list_jobs', False)

        if list_jobs:
            return self._list_jobs()

        if job_id:
            return self._execute_job(job_id)

        if check_due:
            return self._check_due_jobs()

        if test_schedule_id:
            return self._test_schedule(test_schedule_id)

        self.stdout.write(
            self.style.WARNING('Please specify an action: --job-id, --check-due, --test-schedule, or --list-jobs')
        )

    def _list_jobs(self):
        jobs = BackupJobs.objects.all().select_related('source', 'destination')

        if not jobs:
            self.stdout.write(self.style.WARNING('No backup jobs found'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {jobs.count()} backup jobs:'))
        self.stdout.write('')

        for job in jobs:
            status = "🟢 Active" if job.is_active else "🔴 Inactive"
            self.stdout.write(f"ID: {job.id}")
            self.stdout.write(f"  Source: {job.source.name} ({job.source.get_type_display()})")
            self.stdout.write(f"  Destination: {job.destination.name}")
            self.stdout.write(f"  Schedule: {job.schedule}")
            self.stdout.write(f"  Format: {job.output_format}")
            self.stdout.write(f"  Status: {status}")
            self.stdout.write('')

    def _execute_job(self, job_id):
        try:
            job = BackupJobs.objects.get(id=job_id)
        except BackupJobs.DoesNotExist:
            raise CommandError(f'Backup job with ID {job_id} does not exist')

        self.stdout.write(f'Executing backup job: {job}')

        start_time = time.time()
        result = execute_backup_job(job_id)
        duration = time.time() - start_time

        if result['status'] == 'success':
            self.stdout.write(
                self.style.SUCCESS(f'✅ Job completed successfully in {duration:.1f}s')
            )
            self.stdout.write(f"File size: {result.get('file_size', 'N/A')} bytes")
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Job failed: {result.get("error", "Unknown error")}')
            )

    def _check_due_jobs(self):
        self.stdout.write('Running check_due_jobs task...')

        result = check_due_jobs()

        self.stdout.write(f"Checked jobs: {result['checked_jobs']}")
        self.stdout.write(f"Triggered jobs: {result['triggered_jobs']}")

        if result['triggered_job_details']:
            self.stdout.write(self.style.SUCCESS('Triggered jobs:'))
            for job_detail in result['triggered_job_details']:
                self.stdout.write(f"  - Job {job_detail['job_id']}: {job_detail['job_name']}")
                self.stdout.write(f"    Schedule: {job_detail['schedule']}")
                self.stdout.write(f"    Task ID: {job_detail['task_id']}")

        if result['errors']:
            self.stdout.write(self.style.ERROR('Errors:'))
            for error in result['errors']:
                self.stdout.write(f"  - {error}")

    def _test_schedule(self, job_id):
        self.stdout.write(f'Testing schedule for job {job_id}...')

        result = test_job_schedule(job_id, check_minutes=1440)  # Check next 24 hours

        if not result['is_valid_cron']:
            self.stdout.write(
                self.style.ERROR(f'❌ Invalid cron or job not found: {result.get("error", "Unknown error")}')
            )
            return

        self.stdout.write(self.style.SUCCESS(f'✅ Schedule test successful'))
        self.stdout.write(f"Job: {result['job_name']}")
        self.stdout.write(f"Schedule: {result['schedule']}")
        self.stdout.write(f"Current time: {result['current_time']}")

        if result['next_runs']:
            self.stdout.write(f"Next runs:")
            for i, run_time in enumerate(result['next_runs'][:5], 1):
                self.stdout.write(f"  {i}. {run_time}")
        else:
            self.stdout.write("No runs scheduled in the next 24 hours")

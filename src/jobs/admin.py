from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from .models import BackupJobs, ExecutionLogs


class ExecutionLogsInline(admin.TabularInline):
    model = ExecutionLogs
    extra = 0
    readonly_fields = ('created_at', 'status', 'details', 'file_size_formatted')
    can_delete = False
    max_num = 10  # Show only recent 10 logs
    ordering = ('-created_at',)

    def has_add_permission(self, request, obj=None):
        return False

    def file_size_formatted(self, obj):
        """Format file size in human readable format"""
        if obj.file_size:
            for unit in ['B', 'KB', 'MB', 'GB']:
                if obj.file_size < 1024.0:
                    return f"{obj.file_size:.1f} {unit}"
                obj.file_size /= 1024.0
            return f"{obj.file_size:.1f} TB"
        return "-"
    file_size_formatted.short_description = _('File Size')


@admin.register(BackupJobs)
class BackupJobsAdmin(admin.ModelAdmin):
    list_display = ('job_summary', 'schedule_display', 'status_display',
                    'last_execution', 'next_run_estimate', 'created_at')
    list_filter = ('is_active', 'output_format', 'source__type', 'created_at')
    search_fields = ('source__name', 'destination__name')
    readonly_fields = ('created_at', 'updated_at', 'execution_summary')
    inlines = [ExecutionLogsInline]
    list_per_page = 25

    fieldsets = (
        (None, {
            'fields': ('source', 'destination', 'is_active'),
            'description': _('Basic job configuration')
        }),
        (_('Schedule Configuration'), {
            'fields': ('schedule', 'output_format'),
            'description': _('Backup scheduling and output format settings. Use cron format: minute hour day month weekday')
        }),
        (_('Execution Summary'), {
            'fields': ('execution_summary',),
            'classes': ('collapse',),
            'description': _('Recent execution statistics and information')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def job_summary(self, obj):
        """Enhanced job summary with icons and formatting"""
        source_icon = {'database': '💾', 'volume': '🗂️'}.get(obj.source.type, '❓')
        return format_html(
            '{} <strong>{}</strong> → 📱 {}',
            source_icon,
            obj.source.name,
            obj.destination.name
        )
    job_summary.short_description = _('Job')
    job_summary.admin_order_field = 'source__name'

    def schedule_display(self, obj):
        """Display schedule with tooltip"""
        schedule_descriptions = {
            '0 2 * * *': 'Daily at 2:00 AM',
            '0 0 * * *': 'Daily at midnight',
            '0 */6 * * *': 'Every 6 hours',
            '0 0 1 * *': 'Monthly on 1st',
            '0 0 * * 0': 'Weekly on Sunday'
        }
        description = schedule_descriptions.get(obj.schedule, 'Custom schedule')
        return format_html(
            '<code title="{}">{}</code>',
            description,
            obj.schedule
        )
    schedule_display.short_description = _('Schedule')

    def status_display(self, obj):
        """Display job status with visual indicators"""
        if obj.is_active:
            return format_html('<span class="status-active">Active</span>')
        else:
            return format_html('<span class="status-inactive">Inactive</span>')
    status_display.short_description = _('Status')

    def last_execution(self, obj):
        """Display last execution status and time"""
        last_log = obj.execution_logs.first()
        if last_log:
            if last_log.status == 'success':
                return format_html(
                    '<span class="status-success">Success</span><br><small>{}</small>',
                    last_log.created_at.strftime('%Y-%m-%d %H:%M')
                )
            else:
                return format_html(
                    '<span class="status-failed">Failed</span><br><small>{}</small>',
                    last_log.created_at.strftime('%Y-%m-%d %H:%M')
                )
        return format_html('<em>Never executed</em>')
    last_execution.short_description = _('Last Execution')

    def next_run_estimate(self, obj):
        """Estimate next run time based on cron schedule"""
        if not obj.is_active:
            return format_html('<em>Inactive</em>')

        try:
            from croniter import croniter
            now = timezone.now()
            cron = croniter(obj.schedule, now.replace(tzinfo=None))
            next_run = cron.get_next()
            next_run_dt = timezone.make_aware(next_run)

            # Calculate time difference
            diff = next_run_dt - now
            if diff.total_seconds() < 3600:  # Less than 1 hour
                minutes = int(diff.total_seconds() / 60)
                return format_html('<strong>{}m</strong>', minutes)
            elif diff.total_seconds() < 86400:  # Less than 1 day
                hours = int(diff.total_seconds() / 3600)
                return format_html('<strong>{}h</strong>', hours)
            else:
                days = diff.days
                return format_html('<strong>{}d</strong>', days)
        except Exception:
            return format_html('<em>Invalid cron</em>')
    next_run_estimate.short_description = _('Next Run')

    def execution_summary(self, obj):
        """Summary of recent executions"""
        logs = obj.execution_logs.all()[:10]
        if not logs:
            return "No executions yet"

        total = logs.count()
        success_count = logs.filter(status='success').count()
        failed_count = logs.filter(status='failed').count()

        success_rate = (success_count / max(total, 1)) * 100

        summary = f"Recent executions: {total} total, {success_count} successful, {failed_count} failed\n"
        summary += f"Success rate: {success_rate:.1f}%\n"

        if logs:
            last_log = logs[0]
            summary += f"Last execution: {last_log.created_at.strftime('%Y-%m-%d %H:%M')} ({last_log.status})"

        return summary
    execution_summary.short_description = _('Execution Summary')

    actions = ['run_backup_now', 'enable_jobs', 'disable_jobs', 'test_schedule']

    def run_backup_now(self, request, queryset):
        """Execute backup jobs immediately"""
        from jobs.tasks import execute_backup_job

        executed_count = 0
        for job in queryset:
            if job.is_active:
                try:
                    # Execute the backup job
                    result = execute_backup_job.delay(job.id)
                    executed_count += 1
                    self.message_user(
                        request,
                        f"✅ {job}: Backup started (Task ID: {result.id})",
                        level=messages.SUCCESS
                    )
                except Exception as e:
                    self.message_user(
                        request,
                        f"❌ {job}: Failed to start backup - {str(e)}",
                        level=messages.ERROR
                    )
            else:
                self.message_user(
                    request,
                    f"⚠️ {job}: Job is inactive, skipping",
                    level=messages.WARNING
                )

        if executed_count > 0:
            self.message_user(
                request,
                f"Started {executed_count} backup jobs. Check execution logs for results.",
                level=messages.SUCCESS
            )
    run_backup_now.short_description = _("Run backup now for selected jobs")

    def enable_jobs(self, request, queryset):
        """Enable selected jobs"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"✅ Enabled {updated} jobs.", level=messages.SUCCESS)
    enable_jobs.short_description = _("Enable selected jobs")

    def disable_jobs(self, request, queryset):
        """Disable selected jobs"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"⏸️ Disabled {updated} jobs.", level=messages.SUCCESS)
    disable_jobs.short_description = _("Disable selected jobs")

    def test_schedule(self, request, queryset):
        """Test schedule for selected jobs"""
        from jobs.tasks import test_job_schedule

        for job in queryset:
            try:
                result = test_job_schedule(job.id, check_minutes=1440)  # Next 24 hours
                if result['is_valid_cron']:
                    next_runs = result.get('next_runs', [])
                    next_run_info = f"Next runs: {', '.join(next_runs[:3])}" if next_runs else "No runs in next 24h"
                    self.message_user(
                        request,
                        f"✅ {job}: Valid schedule. {next_run_info}",
                        level=messages.SUCCESS
                    )
                else:
                    self.message_user(
                        request,
                        f"❌ {job}: Invalid schedule - {result.get('error', 'Unknown error')}",
                        level=messages.ERROR
                    )
            except Exception as e:
                self.message_user(
                    request,
                    f"❌ {job}: Error testing schedule - {str(e)}",
                    level=messages.ERROR
                )
    test_schedule.short_description = _("Test schedule for selected jobs")

    class Media:
        css = {
            'all': ('admin/css/tele_backup_admin.css',)
        }
        js = ('admin/js/tele_backup_admin.js',)


@admin.register(ExecutionLogs)
class ExecutionLogsAdmin(admin.ModelAdmin):
    list_display = ('job', 'status_display', 'file_size_display', 'created_at', 'details_short')
    list_filter = ('status', 'created_at', 'job__source__type')
    search_fields = ('job__source__name', 'job__destination__name', 'details')
    readonly_fields = ('job', 'status', 'details', 'file_size', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    list_per_page = 50

    def has_add_permission(self, request):
        return False  # Execution logs are created automatically

    def has_change_permission(self, request, obj=None):
        return False  # Execution logs should not be modified

    def status_display(self, obj):
        """Display status with visual indicators"""
        if obj.status == 'success':
            return format_html('<span class="status-success">Success</span>')
        else:
            return format_html('<span class="status-failed">Failed</span>')
    status_display.short_description = _('Status')

    def file_size_display(self, obj):
        """Display file size in human readable format"""
        if obj.file_size:
            size = obj.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return "-"
    file_size_display.short_description = _('File Size')

    def details_short(self, obj):
        """Display truncated details"""
        if obj.details:
            return obj.details[:100] + "..." if len(obj.details) > 100 else obj.details
        return "-"
    details_short.short_description = _('Details')

    class Media:
        css = {
            'all': ('admin/css/tele_backup_admin.css',)
        }
        js = ('admin/js/tele_backup_admin.js',)

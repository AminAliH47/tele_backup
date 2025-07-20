from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _


class TeleBackupAdminSite(AdminSite):
    site_title = _('Tele-Backup Administration')
    site_header = _('Tele-Backup')
    index_title = _('Backup Management Dashboard')
    site_url = None  # Remove "View site" link
    enable_nav_sidebar = True

    def index(self, request, extra_context=None):
        """
        Custom admin index page with backup statistics
        """
        from jobs.models import BackupJobs, ExecutionLogs
        from sources.models import Sources
        from destinations.models import Destinations
        from django.utils import timezone
        from datetime import timedelta

        # Get statistics
        total_jobs = BackupJobs.objects.count()
        active_jobs = BackupJobs.objects.filter(is_active=True).count()
        total_sources = Sources.objects.count()
        total_destinations = Destinations.objects.count()

        # Recent execution statistics
        last_24h = timezone.now() - timedelta(hours=24)
        recent_executions = ExecutionLogs.objects.filter(created_at__gte=last_24h)
        successful_executions = recent_executions.filter(status='success').count()
        failed_executions = recent_executions.filter(status='failed').count()

        # Next scheduled jobs (simplified)
        next_jobs = BackupJobs.objects.filter(is_active=True)[:5]

        extra_context = extra_context or {}
        extra_context.update({
            'statistics': {
                'total_jobs': total_jobs,
                'active_jobs': active_jobs,
                'inactive_jobs': total_jobs - active_jobs,
                'total_sources': total_sources,
                'total_destinations': total_destinations,
                'executions_24h': recent_executions.count(),
                'successful_24h': successful_executions,
                'failed_24h': failed_executions,
                'success_rate_24h': round((successful_executions / max(recent_executions.count(), 1)) * 100, 1) if recent_executions.count() > 0 else 0,
            },
            'next_jobs': next_jobs,
        })

        return super().index(request, extra_context)


# Create custom admin site instance
admin_site = TeleBackupAdminSite(name='telebackup_admin')

# Customize the default admin site as well
admin.site.site_title = _('Tele-Backup Administration')
admin.site.site_header = _('Tele-Backup')
admin.site.index_title = _('Backup Management Dashboard')

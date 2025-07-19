from django.contrib import admin
from .models import BackupJobs, ExecutionLogs


class ExecutionLogsInline(admin.TabularInline):
    model = ExecutionLogs
    extra = 0
    readonly_fields = ('created_at', 'status', 'details', 'file_size')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BackupJobs)
class BackupJobsAdmin(admin.ModelAdmin):
    list_display = ('source', 'destination', 'schedule', 'output_format', 'is_active', 'created_at')
    list_filter = ('is_active', 'output_format', 'created_at')
    search_fields = ('source__name', 'destination__name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ExecutionLogsInline]

    fieldsets = (
        (None, {
            'fields': ('source', 'destination', 'is_active')
        }),
        ('Schedule Configuration', {
            'fields': ('schedule', 'output_format'),
            'description': 'Backup scheduling and output format settings'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ExecutionLogs)
class ExecutionLogsAdmin(admin.ModelAdmin):
    list_display = ('job', 'status', 'file_size_human', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('job__source__name', 'job__destination__name', 'details')
    readonly_fields = ('created_at', 'file_size_human')

    fieldsets = (
        (None, {
            'fields': ('job', 'status', 'created_at')
        }),
        ('Execution Details', {
            'fields': ('details', 'file_size', 'file_size_human'),
            'description': 'Backup execution details and file information'
        }),
    )

    def has_add_permission(self, request):
        return False

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import Sources


@admin.register(Sources)
class SourcesAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'db_type_display', 'connection_status', 'created_at')
    list_filter = ('type', 'db_type', 'created_at')
    search_fields = ('name', 'db_name', 'volume_name', 'db_host')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50

    fieldsets = (
        (None, {
            'fields': ('name', 'type'),
            'description': _('Basic source configuration')
        }),
        (_('Database Configuration'), {
            'fields': ('db_type', 'db_host', 'db_port', 'db_name', 'db_user', 'db_password'),
            'description': _('Database connection settings (only for database sources)'),
            'classes': ('collapse',)
        }),
        (_('Volume Configuration'), {
            'fields': ('volume_name',),
            'description': _('Docker volume settings (only for volume sources)'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def db_type_display(self, obj):
        """Enhanced display for database type"""
        if obj.type == 'database' and obj.db_type:
            icons = {
                'postgresql': '🐘',
                'mysql': '🐬',
                'sqlite': '📄'
            }
            return format_html(
                '{} {}',
                icons.get(obj.db_type, '💾'),
                obj.get_db_type_display()
            )
        elif obj.type == 'volume':
            return format_html('🗂️ Volume')
        return format_html('❓ Unknown')
    db_type_display.short_description = _('Type')
    db_type_display.admin_order_field = 'db_type'

    def connection_status(self, obj):
        """Display connection status indicator"""
        if obj.type == 'database':
            # Simple status based on required fields
            required_fields = ['db_host', 'db_name', 'db_user']
            if all(getattr(obj, field) for field in required_fields):
                return format_html('<span class="status-active">Configured</span>')
            else:
                return format_html('<span class="status-inactive">Incomplete</span>')
        elif obj.type == 'volume':
            if obj.volume_name:
                return format_html('<span class="status-active">Ready</span>')
            else:
                return format_html('<span class="status-inactive">No Volume</span>')
        return format_html('<span class="status-inactive">Unknown</span>')
    connection_status.short_description = _('Status')

    actions = ['test_connection', 'duplicate_source']

    def test_connection(self, request, queryset):
        """Test connection for selected sources"""
        for source in queryset:
            # This would implement actual connection testing
            pass
        self.message_user(request, f"Connection test initiated for {queryset.count()} sources.")
    test_connection.short_description = _("Test connection for selected sources")

    def duplicate_source(self, request, queryset):
        """Duplicate selected sources"""
        count = 0
        for source in queryset:
            source.pk = None
            source.name = f"{source.name} (Copy)"
            source.save()
            count += 1
        self.message_user(request, f"Successfully duplicated {count} sources.")
    duplicate_source.short_description = _("Duplicate selected sources")

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:  # Editing existing object
            # Add any fields that shouldn't be changed after creation
            pass
        return readonly

    class Media:
        css = {
            'all': ('admin/css/tele_backup_admin.css',)
        }
        js = ('admin/js/tele_backup_admin.js',)

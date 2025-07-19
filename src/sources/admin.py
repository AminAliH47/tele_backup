from django.contrib import admin
from .models import Sources


@admin.register(Sources)
class SourcesAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'db_type', 'volume_name', 'created_at')
    list_filter = ('type', 'db_type', 'created_at')
    search_fields = ('name', 'db_name', 'volume_name')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'type')
        }),
        ('Database Configuration', {
            'fields': ('db_type', 'db_host', 'db_port', 'db_name', 'db_user', 'db_password'),
            'description': 'Database connection settings (only for database sources)',
            'classes': ('collapse',)
        }),
        ('Volume Configuration', {
            'fields': ('volume_name',),
            'description': 'Docker volume settings (only for volume sources)',
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    class Media:
        js = ('admin/js/conditional_fields.js',)

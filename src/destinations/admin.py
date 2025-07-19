from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from destinations.models import Destinations


@admin.register(Destinations)
class DestinationsAdmin(admin.ModelAdmin):
    list_display = ('name', 'telegram_channel_id', 'created_at', 'updated_at')
    search_fields = ('name', 'telegram_channel_id')
    list_filter = ('created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name',)
        }),
        ('Telegram Configuration', {
            'fields': ('telegram_bot_token', 'telegram_channel_id'),
            'description': _('Telegram bot token and channel ID for backup delivery')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

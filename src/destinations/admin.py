from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from destinations.models import Destinations
from django.utils import timezone


@admin.register(Destinations)
class DestinationsAdmin(admin.ModelAdmin):
    list_display = ('name', 'telegram_info', 'connection_status', 'created_at', 'updated_at')
    search_fields = ('name', 'telegram_channel_id')
    list_filter = ('created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50

    fieldsets = (
        (None, {
            'fields': ('name',),
            'description': _('Basic destination information')
        }),
        (_('Telegram Configuration'), {
            'fields': ('telegram_bot_token', 'telegram_channel_id'),
            'description': _('Telegram bot token and channel ID for backup delivery. Keep these credentials secure!')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def telegram_info(self, obj):
        """Display formatted Telegram channel info"""
        if obj.telegram_channel_id:
            # Mask the channel ID for security
            masked_id = obj.telegram_channel_id[:3] + '***' + \
                obj.telegram_channel_id[-3:] if len(obj.telegram_channel_id) > 6 else '***'
            return format_html('📱 {}', masked_id)
        return format_html('❌ Not configured')
    telegram_info.short_description = _('Telegram Channel')

    def connection_status(self, obj):
        """Display connection status"""
        if obj.telegram_bot_token and obj.telegram_channel_id:
            return format_html('<span class="status-active">Configured</span>')
        else:
            return format_html('<span class="status-inactive">Incomplete</span>')
    connection_status.short_description = _('Status')

    actions = ['test_telegram_connection', 'send_test_message']

    def test_telegram_connection(self, request, queryset):
        """Test Telegram connection for selected destinations"""
        from destinations.services.telegram_sender import TelegramSender

        success_count = 0
        error_count = 0

        for destination in queryset:
            try:
                sender = TelegramSender(destination)
                success, message = sender.test_connection()
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    self.message_user(request, f"❌ {destination.name}: {message}", level=messages.ERROR)
            except Exception as e:
                error_count += 1
                self.message_user(request, f"❌ {destination.name}: {str(e)}", level=messages.ERROR)

        if success_count > 0:
            self.message_user(request, f"✅ Successfully tested {success_count} destinations.", level=messages.SUCCESS)

        if error_count > 0:
            self.message_user(request, f"❌ Failed to test {error_count} destinations.", level=messages.ERROR)

    test_telegram_connection.short_description = _("Test Telegram connection")

    def send_test_message(self, request, queryset):
        """Send test message to selected destinations"""
        from destinations.services.telegram_sender import TelegramSender

        success_count = 0
        error_count = 0

        for destination in queryset:
            try:
                sender = TelegramSender(destination)
                message = f"🧪 Test message from Tele-Backup admin interface\n\nDestination: {destination.name}\nTime: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
                success = sender.send_message(message)
                if success:
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(request, f"❌ {destination.name}: {str(e)}", level=messages.ERROR)

        if success_count > 0:
            self.message_user(request, f"✅ Sent test message to {success_count} destinations.", level=messages.SUCCESS)

        if error_count > 0:
            self.message_user(request, f"❌ Failed to send to {error_count} destinations.", level=messages.ERROR)

    send_test_message.short_description = _("Send test message")

    class Media:
        css = {
            'all': ('admin/css/tele_backup_admin.css',)
        }
        js = ('admin/js/tele_backup_admin.js',)

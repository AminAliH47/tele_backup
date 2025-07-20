import os
import tempfile
import time
from django.core.management.base import BaseCommand, CommandError

from destinations.models import Destinations
from destinations.services.telegram_sender import TelegramSender, TelegramError, send_backup_notification_sync
from sources.models import Sources
from sources.services.backup_runner import create_backup, BackupError


class Command(BaseCommand):
    help = 'Test the end-to-end backup and Telegram upload flow'

    def add_arguments(self, parser):
        parser.add_argument(
            '--destination-id',
            type=int,
            help='Destination ID to test with (required)',
            required=True
        )
        parser.add_argument(
            '--source-id',
            type=int,
            help='Source ID to test backup with (optional - creates test file if not provided)'
        )
        parser.add_argument(
            '--test-connection',
            action='store_true',
            help='Only test Telegram connection without backup'
        )
        parser.add_argument(
            '--test-message',
            type=str,
            help='Send a test message instead of performing backup'
        )
        parser.add_argument(
            '--create-test-file',
            action='store_true',
            help='Create and send a test file instead of real backup'
        )

    def handle(self, *args, **options):
        destination_id = options['destination_id']
        source_id = options.get('source_id')
        test_connection = options.get('test_connection', False)
        test_message = options.get('test_message')
        create_test_file = options.get('create_test_file', False)

        # Get destination
        try:
            destination = Destinations.objects.get(id=destination_id)
        except Destinations.DoesNotExist:
            raise CommandError(f'Destination with ID {destination_id} does not exist')

        self.stdout.write(
            self.style.SUCCESS(f'Using destination: {destination.name}')
        )

        # Create Telegram sender
        try:
            sender = TelegramSender(destination)
        except Exception as e:
            raise CommandError(f'Failed to create Telegram sender: {str(e)}')

        # Test connection only
        if test_connection:
            return self._test_connection(sender)

        # Send test message only
        if test_message:
            return self._send_test_message(sender, test_message)

        # Create and send test file
        if create_test_file:
            return self._send_test_file(sender)

        # Perform real backup test
        if source_id:
            return self._test_real_backup(sender, source_id, destination)
        else:
            self.stdout.write(
                self.style.WARNING('No source specified. Use --create-test-file for a simple test.')
            )

    def _test_connection(self, sender):
        self.stdout.write('Testing Telegram connection...')

        try:
            success, message = sender.test_connection()

            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Connection successful: {message}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ Connection failed: {message}')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Connection test failed: {str(e)}')
            )

    def _send_test_message(self, sender, message):
        self.stdout.write(f'Sending test message: "{message}"')

        try:
            success = sender.send_message(message)

            if success:
                self.stdout.write(
                    self.style.SUCCESS('✅ Test message sent successfully')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Failed to send test message')
                )

        except TelegramError as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Telegram error: {str(e)}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Unexpected error: {str(e)}')
            )

    def _send_test_file(self, sender):
        self.stdout.write('Creating and sending test file...')

        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            test_content = f"""
Tele-Backup Test File
====================

Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}
Destination: {sender.destination.name}
File size test: {'A' * 1000}  # 1KB of data

This is a test file to verify that the Telegram integration is working correctly.
If you receive this file, the backup delivery system is functioning properly!
"""
            f.write(test_content)
            temp_file_path = f.name

        try:
            file_size = os.path.getsize(temp_file_path)

            success = sender.send_file(
                file_path=temp_file_path,
                caption="🧪 <b>Test File</b>\n\nThis is a test of the Tele-Backup system",
                filename="tele_backup_test.txt"
            )

            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Test file sent successfully ({file_size} bytes)')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Failed to send test file')
                )

        except TelegramError as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Telegram error: {str(e)}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Unexpected error: {str(e)}')
            )
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def _test_real_backup(self, sender, source_id, destination):
        self.stdout.write(f'Testing real backup with source ID: {source_id}')

        # Get source
        try:
            source = Sources.objects.get(id=source_id)
        except Sources.DoesNotExist:
            raise CommandError(f'Source with ID {source_id} does not exist')

        self.stdout.write(f'Source: {source.name} ({source.get_type_display()})')

        start_time = time.time()

        try:
            # Perform backup
            self.stdout.write('Creating backup...')

            backup_file_path, file_size = create_backup(source, 'tar.gz')

            duration = time.time() - start_time

            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Backup created: {backup_file_path} ({file_size} bytes) in {duration:.1f}s'
                )
            )

            # Send backup notification
            self.stdout.write('Sending backup to Telegram...')

            success = send_backup_notification_sync(
                destination=destination,
                file_path=backup_file_path,
                source_name=source.name,
                backup_type=f"{source.get_type_display()}" +
                (f" ({source.get_db_type_display()})" if source.db_type else ""),
                success=True,
                duration=duration
            )

            if success:
                self.stdout.write(
                    self.style.SUCCESS('✅ Backup sent to Telegram successfully')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Failed to send backup to Telegram')
                )

        except BackupError as e:
            duration = time.time() - start_time

            self.stdout.write(
                self.style.ERROR(f'❌ Backup failed: {str(e)}')
            )

            # Send failure notification
            self.stdout.write('Sending failure notification to Telegram...')

            try:
                success = send_backup_notification_sync(
                    destination=destination,
                    source_name=source.name,
                    backup_type=f"{source.get_type_display()}" +
                    (f" ({source.get_db_type_display()})" if source.db_type else ""),
                    success=False,
                    error_message=str(e)
                )

                if success:
                    self.stdout.write(
                        self.style.SUCCESS('✅ Failure notification sent to Telegram')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR('❌ Failed to send failure notification')
                    )

            except Exception as notify_error:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to send failure notification: {str(notify_error)}')
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Unexpected error during backup: {str(e)}')
            )

        finally:
            # Clean up backup file if it was created
            if 'backup_file_path' in locals() and os.path.exists(backup_file_path):
                try:
                    os.unlink(backup_file_path)
                    self.stdout.write('🧹 Cleaned up temporary backup file')
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️ Failed to clean up backup file: {str(e)}')
                    )

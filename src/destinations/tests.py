import os
import tempfile
from django.test import TestCase

from destinations.models import Destinations
from destinations.services.telegram_sender import (
    TelegramSender, TelegramError, create_backup_success_message,
    create_backup_failure_message
)


class TelegramSenderTestCase(TestCase):
    def setUp(self):
        self.destination = Destinations.objects.create(
            name='Test Channel',
            telegram_bot_token='1234567890:TEST_BOT_TOKEN',
            telegram_channel_id='@test_channel'
        )
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    def _create_test_file(self, content="Test file content", size_bytes=None):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=self.temp_dir) as f:
            if size_bytes:
                content = 'A' * size_bytes
            f.write(content)
            return f.name


class TelegramSenderInitTestCase(TelegramSenderTestCase):
    def test_sender_initialization(self):
        sender = TelegramSender(self.destination)
        self.assertEqual(sender.destination, self.destination)
        self.assertIsNotNone(sender.bot)


class TelegramFileUploadTestCase(TelegramSenderTestCase):
    def test_send_file_not_found(self):
        sender = TelegramSender(self.destination)

        with self.assertRaises(TelegramError) as context:
            sender.send_file("/nonexistent/file.txt")

        self.assertIn("File not found", str(context.exception))

    def test_send_file_too_large(self):
        # Create a file larger than 50MB
        large_file = self._create_test_file(size_bytes=51 * 1024 * 1024)
        sender = TelegramSender(self.destination)

        with self.assertRaises(TelegramError) as context:
            sender.send_file(large_file)

        self.assertIn("exceeds Telegram's 50MB limit", str(context.exception))


class TelegramMessageTestCase(TelegramSenderTestCase):
    def test_send_message_empty(self):
        sender = TelegramSender(self.destination)

        with self.assertRaises(TelegramError) as context:
            sender.send_message("")

        self.assertIn("cannot be empty", str(context.exception))

    def test_send_message_whitespace_only(self):
        sender = TelegramSender(self.destination)

        with self.assertRaises(TelegramError) as context:
            sender.send_message("   \n\t   ")

        self.assertIn("cannot be empty", str(context.exception))


class TelegramMessageFormattingTestCase(TestCase):
    def test_backup_success_message_format(self):
        message = create_backup_success_message(
            source_name="Test DB",
            file_name="backup_20240119_120000.tar.gz",
            file_size=1024,
            backup_type="Database (PostgreSQL)",
            duration=15.5
        )

        self.assertIn("✅", message)
        self.assertIn("Test DB", message)
        self.assertIn("backup_20240119_120000.tar.gz", message)
        self.assertIn("1.0 KB", message)
        self.assertIn("Database (PostgreSQL)", message)
        self.assertIn("15.5s", message)

    def test_backup_success_message_without_duration(self):
        message = create_backup_success_message(
            source_name="Test Volume",
            file_name="volume_backup.tar.gz",
            file_size=2048,
            backup_type="Volume"
        )

        self.assertIn("✅", message)
        self.assertIn("Test Volume", message)
        self.assertIn("2.0 KB", message)
        self.assertNotIn("Duration", message)

    def test_backup_failure_message_format(self):
        message = create_backup_failure_message(
            source_name="Failed DB",
            error_message="Connection refused",
            backup_type="Database (MySQL)"
        )

        self.assertIn("❌", message)
        self.assertIn("Failed DB", message)
        self.assertIn("Connection refused", message)
        self.assertIn("Database (MySQL)", message)

    def test_file_size_formatting(self):
        # Test different file sizes
        test_cases = [
            (512, "512.0 B"),
            (1024, "1.0 KB"),
            (1536, "1.5 KB"),
            (1048576, "1.0 MB"),
            (1073741824, "1.0 GB"),
        ]

        for size_bytes, expected in test_cases:
            message = create_backup_success_message(
                "Test", "file.txt", size_bytes, "Test"
            )
            self.assertIn(expected, message)


class DestinationsModelTestCase(TestCase):
    def test_create_destination(self):
        destination = Destinations.objects.create(
            name='Test Destination',
            telegram_bot_token='1234567890:TEST_TOKEN',
            telegram_channel_id='@test_channel'
        )

        self.assertEqual(destination.name, 'Test Destination')
        self.assertEqual(str(destination), 'Test Destination')

    def test_destination_ordering(self):
        dest1 = Destinations.objects.create(  # noqa
            name='First',
            telegram_bot_token='token1',
            telegram_channel_id='channel1'
        )
        import time
        time.sleep(0.01)  # Ensure different timestamps
        dest2 = Destinations.objects.create(  # noqa
            name='Second',
            telegram_bot_token='token2',
            telegram_channel_id='channel2'
        )

        destinations = list(Destinations.objects.all())
        self.assertEqual(destinations[0].name, 'Second')  # Newer first
        self.assertEqual(destinations[1].name, 'First')


# Integration test for the management command
class ManagementCommandTestCase(TestCase):
    def test_management_command_exists(self):
        from django.core.management import get_commands
        commands = get_commands()
        self.assertIn('test_backup_flow', commands)

    def test_command_help(self):
        from destinations.management.commands.test_backup_flow import Command

        command = Command()
        help_text = command.help

        self.assertIn('Test the end-to-end backup and Telegram upload flow', help_text)

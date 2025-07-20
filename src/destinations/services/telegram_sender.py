import os
import asyncio
import logging
from typing import Tuple, Optional
from datetime import datetime

from telegram import Bot
from telegram.error import TelegramError, NetworkError, TimedOut, BadRequest, Forbidden
# from django.utils.translation import gettext_lazy as _

from destinations import models

logger = logging.getLogger(__name__)


class TelegramSender:
    def __init__(self, destination: models.Destinations):
        self.destination = destination
        self.bot = Bot(token=destination.telegram_bot_token)

    async def send_file_async(
        self,
        file_path: str,
        caption: Optional[str] = None,
        filename: Optional[str] = None
    ) -> bool:
        if not os.path.exists(file_path):
            raise TelegramError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)
        max_size = 50 * 1024 * 1024  # 50MB Telegram limit for files

        if file_size > max_size:
            raise TelegramError(
                f"File size ({file_size} bytes) exceeds Telegram's 50MB limit"
            )

        if filename is None:
            filename = os.path.basename(file_path)

        try:
            logger.info(f"Sending file {filename} to {self.destination.name}")

            with open(file_path, 'rb') as file:
                await self.bot.send_document(
                    chat_id=self.destination.telegram_channel_id,
                    document=file,
                    filename=filename,
                    caption=caption,
                    read_timeout=300,  # 5 minutes
                    write_timeout=300,
                    connect_timeout=60
                )

            logger.info(f"Successfully sent file {filename} to {self.destination.name}")
            return True

        except Forbidden as e:
            error_msg = f"Bot doesn't have permission to send to {self.destination.name}: {str(e)}"
            logger.error(error_msg)
            raise TelegramError(error_msg)

        except BadRequest as e:
            error_msg = f"Invalid request for {self.destination.name}: {str(e)}"
            logger.error(error_msg)
            raise TelegramError(error_msg)

        except (NetworkError, TimedOut) as e:
            error_msg = f"Network error sending to {self.destination.name}: {str(e)}"
            logger.error(error_msg)
            raise TelegramError(error_msg)

        except TelegramError as e:
            error_msg = f"Telegram API error for {self.destination.name}: {str(e)}"
            logger.error(error_msg)
            raise TelegramError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error sending file to {self.destination.name}: {str(e)}"
            logger.error(error_msg)
            raise TelegramError(error_msg)

    async def send_message_async(self, message: str) -> bool:
        if not message.strip():
            raise TelegramError("Message cannot be empty")

        try:
            logger.info(f"Sending message to {self.destination.name}")

            await self.bot.send_message(
                chat_id=self.destination.telegram_channel_id,
                text=message,
                parse_mode='HTML',
                read_timeout=60,
                write_timeout=60,
                connect_timeout=30
            )

            logger.info(f"Successfully sent message to {self.destination.name}")
            return True

        except Forbidden as e:
            error_msg = f"Bot doesn't have permission to send to {self.destination.name}: {str(e)}"
            logger.error(error_msg)
            raise TelegramError(error_msg)

        except BadRequest as e:
            error_msg = f"Invalid request for {self.destination.name}: {str(e)}"
            logger.error(error_msg)
            raise TelegramError(error_msg)

        except (NetworkError, TimedOut) as e:
            error_msg = f"Network error sending to {self.destination.name}: {str(e)}"
            logger.error(error_msg)
            raise TelegramError(error_msg)

        except TelegramError as e:
            error_msg = f"Telegram API error for {self.destination.name}: {str(e)}"
            logger.error(error_msg)
            raise TelegramError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error sending message to {self.destination.name}: {str(e)}"
            logger.error(error_msg)
            raise TelegramError(error_msg)

    def send_file(
        self,
        file_path: str,
        caption: Optional[str] = None,
        filename: Optional[str] = None
    ) -> bool:
        return asyncio.run(self.send_file_async(file_path, caption, filename))

    def send_message(self, message: str) -> bool:
        return asyncio.run(self.send_message_async(message))

    async def test_connection_async(self) -> Tuple[bool, str]:
        try:
            logger.info(f"Testing connection to {self.destination.name}")

            me = await self.bot.get_me()

            # Try to get chat info
            try:
                chat = await self.bot.get_chat(self.destination.telegram_channel_id)
                chat_info = f"Chat: {chat.title or chat.first_name or 'Unknown'} (ID: {chat.id})"
            except Exception:
                chat_info = f"Chat ID: {self.destination.telegram_channel_id}"

            success_msg = f"Bot @{me.username} connected successfully to {chat_info}"
            logger.info(success_msg)
            return True, success_msg

        except Forbidden:
            error_msg = "Bot doesn't have permission to access this chat"
            logger.error(error_msg)
            return False, error_msg

        except BadRequest as e:
            error_msg = f"Invalid chat ID or bot token: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

        except (NetworkError, TimedOut):
            error_msg = "Network error - check internet connection"
            logger.error(error_msg)
            return False, error_msg

        except TelegramError as e:
            error_msg = f"Telegram API error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def test_connection(self) -> Tuple[bool, str]:
        return asyncio.run(self.test_connection_async())


def create_backup_success_message(
    source_name: str,
    file_name: str,
    file_size: int,
    backup_type: str,
    duration: Optional[float] = None
) -> str:
    def format_file_size(size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    formatted_size = format_file_size(file_size)

    message = "✅ <b>Backup Completed Successfully</b>\n\n"
    message += f"📋 <b>Source:</b> {source_name}\n"
    message += f"📁 <b>File:</b> {file_name}\n"
    message += f"📊 <b>Size:</b> {formatted_size}\n"
    message += f"🔧 <b>Type:</b> {backup_type}\n"

    if duration:
        message += f"⏱️ <b>Duration:</b> {duration:.1f}s\n"

    message += f"🕐 <b>Completed:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    return message


def create_backup_failure_message(
    source_name: str,
    error_message: str,
    backup_type: str
) -> str:
    message = "❌ <b>Backup Failed</b>\n\n"
    message += f"📋 <b>Source:</b> {source_name}\n"
    message += f"🔧 <b>Type:</b> {backup_type}\n"
    message += f"⚠️ <b>Error:</b> {error_message}\n"
    message += f"🕐 <b>Failed at:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    return message


async def send_backup_notification(
    destination: models.Destinations,
    file_path: Optional[str] = None,
    source_name: str = "",
    backup_type: str = "",
    success: bool = True,
    error_message: str = "",
    duration: Optional[float] = None
) -> bool:
    sender = TelegramSender(destination)

    try:
        if success and file_path:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)

            # Send the backup file
            caption = create_backup_success_message(
                source_name, file_name, file_size, backup_type, duration
            )

            await sender.send_file_async(file_path, caption=caption)

        else:
            # Send failure message
            message = create_backup_failure_message(
                source_name, error_message, backup_type
            )

            await sender.send_message_async(message)

        return True

    except TelegramError as e:
        logger.error(f"Failed to send backup notification: {str(e)}")
        return False


def send_backup_notification_sync(
    destination: models.Destinations,
    file_path: Optional[str] = None,
    source_name: str = "",
    backup_type: str = "",
    success: bool = True,
    error_message: str = "",
    duration: Optional[float] = None
) -> bool:
    return asyncio.run(
        send_backup_notification(
            destination, file_path, source_name, backup_type,
            success, error_message, duration
        )
    )

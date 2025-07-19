from django.db import models
from django.utils.translation import gettext_lazy as _

from config.fields import EncryptedCharField
from common.models import BaseModel


class Destinations(BaseModel):
    name = models.CharField(
        max_length=100,
        help_text=_("Friendly name for this destination (e.g., 'My Project Channel')")
    )
    telegram_bot_token = EncryptedCharField(
        max_length=500,
        help_text=_("Telegram bot API token")
    )
    telegram_channel_id = EncryptedCharField(
        max_length=200,
        help_text=_("Telegram channel ID or username")
    )

    class Meta:
        db_table = 'destinations'
        ordering = (
            '-created_at',
        )

    def __str__(self):
        return self.name

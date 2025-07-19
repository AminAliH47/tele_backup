from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from config.fields import EncryptedCharField
from common.models import BaseModel


class Sources(BaseModel):
    SOURCE_TYPE_CHOICES = (
        ('database', 'Database'),
        ('volume', 'Volume'),
    )

    DATABASE_TYPE_CHOICES = (
        ('postgresql', 'PostgreSQL'),
        ('mysql', 'MySQL/MariaDB'),
        ('sqlite', 'SQLite'),
    )

    name = models.CharField(
        max_length=100,
        help_text=_("Friendly name for this source (e.g., 'Production DB')")
    )
    type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        help_text=_("Type of backup source")
    )

    # Database-specific fields
    db_type = models.CharField(
        max_length=20,
        choices=DATABASE_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text=_("Database type (required if source type is Database)")
    )
    db_host = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Database host")
    )
    db_port = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=_("Database port")
    )
    db_name = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Database name")
    )
    db_user = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Database username")
    )
    db_password = EncryptedCharField(
        max_length=500,
        blank=True,
        help_text=_("Database password")
    )

    # Volume-specific fields
    volume_name = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Docker volume name (required if source type is Volume)")
    )

    class Meta:
        db_table = 'sources'
        ordering = (
            '-created_at',
        )

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

    def clean(self):
        if self.type == 'database':
            if not self.db_type:
                raise ValidationError({'db_type': _('Database type is required for database sources.')})
            if not self.db_name:
                raise ValidationError({'db_name': _('Database name is required for database sources.')})
        elif self.type == 'volume':
            if not self.volume_name:
                raise ValidationError({'volume_name': _('Volume name is required for volume sources.')})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

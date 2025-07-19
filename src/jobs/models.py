from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re

from common.models import BaseModel


class BackupJobs(BaseModel):
    OUTPUT_FORMAT_CHOICES = (
        ('sql', '.sql'),
        ('tar.gz', '.tar.gz'),
    )

    source = models.ForeignKey(
        'sources.Sources',
        on_delete=models.CASCADE,
        help_text=_("Sources to backup")
    )
    destination = models.ForeignKey(
        'destinations.Destinations',
        on_delete=models.CASCADE,
        help_text=_("Destinations for backup files")
    )
    schedule = models.CharField(
        max_length=100,
        help_text=_("Cron expression for scheduling (e.g., '0 2 * * *' for daily at 2 AM)")
    )
    output_format = models.CharField(
        max_length=10,
        choices=OUTPUT_FORMAT_CHOICES,
        default='tar.gz',
        help_text=_("Output format for backup files")
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_("Enable or disable this backup job")
    )

    class Meta:
        db_table = 'backup_jobs'
        ordering = (
            '-created_at',
        )

    def __str__(self):
        return f"{self.source.name} → {self.destination.name}"

    def clean(self):
        # Basic cron expression validation (5 fields)
        cron_pattern = r'^(\*|[0-5]?\d|\*\/\d+)(\s+(\*|[01]?\d|2[0-3]|\*\/\d+)){1}(\s+(\*|[012]?\d|3[01]|\*\/\d+)){1}(\s+(\*|[01]?\d|\*\/\d+)){1}(\s+(\*|[0-6]|\*\/\d+)){1}$'
        if not re.match(cron_pattern, self.schedule):
            raise ValidationError({'schedule': _('Invalid cron expression format.')})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ExecutionLogs(BaseModel):
    STATUS_CHOICES = (
        ('success', 'SUCCESS'),
        ('failed', 'FAILED'),
    )

    job = models.ForeignKey(
        BackupJobs,
        on_delete=models.CASCADE,
        related_name='execution_logs',
        help_text=_("The backup job this log entry belongs to")
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        help_text=_("Execution status")
    )
    details = models.TextField(
        blank=True,
        help_text=_("Execution details, output messages, or error information")
    )
    file_size = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text=_("Size of the generated backup file in bytes")
    )

    class Meta:
        db_table = 'execution_logs'
        ordering = (
            '-created_at',
        )

    def __str__(self):
        return f"{self.job} - {self.get_status_display()} ({self.created_at})"

    @property
    def file_size_human(self):
        if self.file_size is None:
            return "N/A"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} PB"

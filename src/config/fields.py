import os
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet


def get_encryption_key():
    key = getattr(settings, 'ENCRYPTION_KEY', None)
    if not key:
        key = os.environ.get('ENCRYPTION_KEY')
        if not key:
            key = Fernet.generate_key().decode()
    return key.encode() if isinstance(key, str) else key


class EncryptedCharField(models.CharField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        try:
            fernet = Fernet(get_encryption_key())
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            return value

    def to_python(self, value):
        if value is None:
            return value
        if isinstance(value, str):
            return value
        return str(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        try:
            fernet = Fernet(get_encryption_key())
            return fernet.encrypt(value.encode()).decode()
        except Exception:
            return value


class EncryptedTextField(models.TextField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        try:
            fernet = Fernet(get_encryption_key())
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            return value

    def to_python(self, value):
        if value is None:
            return value
        if isinstance(value, str):
            return value
        return str(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        try:
            fernet = Fernet(get_encryption_key())
            return fernet.encrypt(value.encode()).decode()
        except Exception:
            return value

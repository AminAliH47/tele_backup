from typing import List
from pydantic_settings import BaseSettings


class EnvsConfig(BaseSettings):
    TB_DEBUG: bool
    TB_TZ: str

    TB_SECRET_KEY: str

    TB_ENCRYPTION_KEY: str

    TB_ALLOWED_HOSTS: List[str] = list()
    TB_CSRF_TRUSTED_ORIGINS: List[str] = list()

    TB_REDIS_HOST: str
    TB_REDIS_PORT: int = 6379

    @property
    def MESSAGE_BROKER_URL(self) -> str:
        return (
            f'redis://{self.TB_REDIS_HOST}:{self.TB_REDIS_PORT}/'
        )

    class Config:
        env_file = '.env'
        case_sensitive = True
        extra = 'ignore'


envs = EnvsConfig()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='lucky_')

    db_url: str = 'sqlite+aiosqlite:///db.sqlite3'

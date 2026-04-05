from functools import lru_cache, wraps
from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)

from .config import Settings
from .models import EntityExistsError


def catch_session_exceptions(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            async for item in func(*args, **kwargs):
                yield item
        except EntityExistsError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
    return wrapper


@lru_cache
def get_settings():
    return Settings()


@catch_session_exceptions
async def get_session(
        settings: Annotated[str, Depends(get_settings)],
) -> AsyncGenerator:
    db_url = settings.db_url
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]

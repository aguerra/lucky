from functools import wraps
from typing import Annotated, AsyncGenerator

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EntityExistsError, async_session


def catch_session_exceptions(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            async for item in func(*args, **kwargs):
                yield item
        except EntityExistsError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
    return wrapper


@catch_session_exceptions
async def get_session() -> AsyncGenerator:
    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]

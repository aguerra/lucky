import re
from datetime import datetime
from typing import Optional, Self
from uuid import UUID, uuid7

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Table,
    Uuid,
    func,
    select
)
from sqlalchemy.engine import Engine
from sqlalchemy.event import listens_for
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    WriteOnlyMapped,
    mapped_column,
    relationship
)
from sqlalchemy.orm.attributes import flag_modified


def datetime_from_string(s: str) -> datetime:
    return datetime.fromisoformat(s)


@listens_for(Engine, 'connect')
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()


class EntityExistsError(Exception):
    pass


class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    @classmethod
    async def select(cls, session: AsyncSession) -> list[Self]:
        query = select(cls)
        result = await session.stream_scalars(query)
        return [items async for items in result]

    @classmethod
    async def new_or_existing(cls, session: AsyncSession, **attrs) -> Self:
        query = select(cls)
        for attr, value in attrs.items():
            query = query.where(getattr(cls, attr) == value)
        result = await session.stream_scalars(query)
        instance = await result.one_or_none()
        return instance or cls(**attrs)

    async def save(self, session: AsyncSession) -> Self:
        try:
            session.add(self)
            await session.commit()
        except IntegrityError as e:
            pattern = 'unique constraint failed'
            if re.search(pattern, str(e.orig), re.IGNORECASE):
                await session.rollback()
                name = type(self).__name__.lower()
                raise EntityExistsError(f'{name} exists')
            raise
        await session.refresh(self)
        return self

    async def delete(self, session: AsyncSession) -> None:
        await session.delete(self)
        await session.commit()

    def flag_modified(self, attr: str) -> None:
        flag_modified(self, attr)


class WithFortunesMixin:
    async def with_fortunes(self, session: AsyncSession) -> Self:
        query = self.fortunes_relationship.select()  # type: ignore
        result = await session.stream_scalars(query)
        self.fortunes = [fortune async for fortune in result]
        return self


FortuneTag = Table(
    'fortunes_tags',
    Base.metadata,
    Column(
        'fortune_id',
        Uuid,
        ForeignKey('fortunes.id', ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        'tag_id',
        Uuid,
        ForeignKey('tags.id', ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)


class Author(WithFortunesMixin, Base):
    __tablename__ = 'authors'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(unique=True)
    fortunes_relationship: WriteOnlyMapped['Fortune'] = relationship(
        back_populates='author',
    )

    def __repr__(self):
        return f'Author(id={self.id}, name="{self.name}")'


class Fortune(Base):
    __tablename__ = 'fortunes'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    content: Mapped[str] = mapped_column(unique=True)
    author_id: Mapped[int] = mapped_column(
        ForeignKey('authors.id', ondelete="RESTRICT"),
        index=True,
    )
    author: Mapped['Author'] = relationship(
        lazy='joined',
        innerjoin=True,
        back_populates='fortunes_relationship',
    )
    tags: Mapped[list['Tag']] = relationship(
        secondary=FortuneTag,
        lazy='selectin',
        back_populates='fortunes_relationship',
        cascade="all, delete",
    )

    def __repr__(self):
        return f'Fortune(id={self.id}, content="{self.content}")'


class Tag(WithFortunesMixin, Base):
    __tablename__ = 'tags'

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    tag: Mapped[str] = mapped_column(unique=True)
    fortunes_relationship: WriteOnlyMapped['Fortune'] = relationship(
        secondary=FortuneTag,
        back_populates='tags',
        passive_deletes=True,
    )

    def __repr__(self):
        return f'Tag(id={self.id}, tag="{self.tag}")'

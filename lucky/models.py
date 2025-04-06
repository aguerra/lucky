import re
import sys
from datetime import datetime
from typing import Optional, Self

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    func,
    select
)
from sqlalchemy.engine import Engine
from sqlalchemy.event import listens_for
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    WriteOnlyMapped,
    mapped_column,
    relationship
)
from sqlalchemy.orm.attributes import flag_modified
from tsidpy import TSID


def entity_id() -> int:
    return TSID.create().number


def entity_id_from_string(s: str) -> int:
    number = TSID.from_string(s).number
    if number < 0 or number > sys.maxsize:
        raise ValueError('invalid string')
    return number


def entity_id_to_string(id: int) -> str:
    return TSID(id).to_string()


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
        Integer,
        ForeignKey('fortunes.id', ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        'tag_id',
        Integer,
        ForeignKey('tags.id', ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)


class Author(WithFortunesMixin, Base):
    __tablename__ = 'authors'

    id: Mapped[int] = mapped_column(primary_key=True, default=entity_id)
    name: Mapped[str] = mapped_column(unique=True)
    fortunes_relationship: WriteOnlyMapped['Fortune'] = relationship(
        back_populates='author',
    )

    def __repr__(self):
        return f'Author(id={self.id}, name="{self.name}")'


class Fortune(Base):
    __tablename__ = 'fortunes'

    id: Mapped[int] = mapped_column(primary_key=True, default=entity_id)
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

    id: Mapped[int] = mapped_column(primary_key=True, default=entity_id)
    tag: Mapped[str] = mapped_column(unique=True)
    fortunes_relationship: WriteOnlyMapped['Fortune'] = relationship(
        secondary=FortuneTag,
        back_populates='tags',
        passive_deletes=True,
    )

    def __repr__(self):
        return f'Tag(id={self.id}, tag="{self.tag}")'


engine = create_async_engine('sqlite+aiosqlite:///db.sqlite3')
async_session = async_sessionmaker(engine, expire_on_commit=False)

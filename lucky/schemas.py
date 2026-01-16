from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    StringConstraints,
    model_validator
)

AuthorName = Annotated[str, StringConstraints(min_length=1, max_length=128)]
TagValue = Annotated[str, StringConstraints(min_length=1, max_length=32)]
FortuneContent = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512),
]


class FortuneIn(BaseModel):
    author: AuthorName
    tags: list[TagValue] = []
    content: FortuneContent


class FortunePatch(BaseModel):
    author: AuthorName | None = None
    tags: list[TagValue] | None = None
    content: FortuneContent | None = None

    @model_validator(mode='after')
    def verify_any(self) -> Self:
        attrs = self.author, self.tags, self.content
        if all([attr is None for attr in attrs]):
            raise ValueError('all attributes are missing')
        return self


class AuthorPatch(BaseModel):
    name: AuthorName


class TagPatch(BaseModel):
    tag: TagValue


class EntityModelOut(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class AuthorOutWithoutFortunes(EntityModelOut):
    name: AuthorName


class TagOutWithoutFortunes(EntityModelOut):
    tag: TagValue


class FortuneOut(EntityModelOut):
    content: FortuneContent
    author: AuthorOutWithoutFortunes
    tags: list[TagOutWithoutFortunes]


class FortuneOutWithoutAuthor(EntityModelOut):
    content: FortuneContent
    tags: list[TagOutWithoutFortunes]


class AuthorOut(EntityModelOut):
    name: AuthorName
    fortunes: list[FortuneOutWithoutAuthor]


class FortuneOutWithoutTags(EntityModelOut):
    author: AuthorOutWithoutFortunes
    content: FortuneContent


class TagOut(EntityModelOut):
    tag: TagValue
    fortunes: list[FortuneOutWithoutTags]


class FortuneItems(BaseModel):
    items: list[FortuneOut]


class AuthorItems(BaseModel):
    items: list[AuthorOut]


class TagItems(BaseModel):
    items: list[TagOut]


def min_length(type_alias) -> int:
    return type_alias.__metadata__[0].min_length


def max_length(type_alias) -> int:
    return type_alias.__metadata__[0].max_length

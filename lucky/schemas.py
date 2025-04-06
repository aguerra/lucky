from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    StringConstraints,
    field_serializer,
    model_validator
)

from .models import entity_id_from_string, entity_id_to_string

AuthorName = Annotated[str, StringConstraints(min_length=1, max_length=128)]
TagValue = Annotated[str, StringConstraints(min_length=1, max_length=32)]
FortuneContent = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512),
]
EntityId = Annotated[
    str,
    StringConstraints(min_length=13, max_length=13),
    AfterValidator(lambda x: entity_id_from_string(x)),
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
    id: int
    created_at: datetime
    updated_at: datetime | None = None

    @field_serializer('id')
    def serialize_id(self, id: int, _info) -> str:
        return entity_id_to_string(id)


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

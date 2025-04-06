from datetime import datetime

import pytest

from lucky.schemas import (
    AuthorName,
    EntityId,
    EntityModelOut,
    FortuneContent,
    FortunePatch,
    TagValue,
    max_length,
    min_length
)


def test_fortune_patch_raise_value_error_all_attributes_missing():
    with pytest.raises(ValueError, match=r'all attributes.+missing'):
        FortunePatch()


def test_entity_model_out_serialize_id():
    created_at = datetime.now()
    instance = EntityModelOut(id=1, created_at=created_at)
    serialized = instance.serialize_id(1, None)

    assert serialized


@pytest.mark.parametrize(
    "type_alias",
    [AuthorName, TagValue, FortuneContent, EntityId],
)
def test_min_length(type_alias):
    value = min_length(type_alias)

    assert value >= 0


@pytest.mark.parametrize(
    "type_alias",
    [AuthorName, TagValue, FortuneContent, EntityId],
)
def test_max_length(type_alias):
    value = max_length(type_alias)

    assert value > 0

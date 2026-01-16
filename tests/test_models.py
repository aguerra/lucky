from datetime import datetime

import pytest

from lucky.models import (
    Author,
    EntityExistsError,
    Fortune,
    Tag,
    datetime_from_string
)


@pytest.fixture
async def create_fortune(session):
    async def _create_fortune(**kwargs):
        fortune = Fortune(**kwargs)
        session.add(fortune)
        await session.commit()
        return fortune
    return _create_fortune


@pytest.fixture
def author():
    return Author(name='Anonymous')


@pytest.fixture
def tags():
    return [Tag(tag='tag_1'), Tag(tag='tag_2')]


@pytest.mark.anyio
async def test_save(author, session):
    expected = await author.save(session)
    actual = await session.get(Author, expected.id)

    assert expected == actual


@pytest.mark.anyio
async def test_save_raise_entity_exists_error(
        author,
        create_fortune,
        session,
        tags,
):
    await create_fortune(content='Test', author=author, tags=tags)
    new_fortune = Fortune(content='Test', author=author, tags=tags)

    with pytest.raises(EntityExistsError):
        await new_fortune.save(session)


@pytest.mark.anyio
async def test_select(author, create_fortune, session, tags):
    fortune_1 = await create_fortune(
        content='Test 1',
        author=author,
        tags=tags,
    )
    fortune_2 = await create_fortune(
        content='Test 2',
        author=author,
        tags=tags,
    )
    expected = [fortune_1, fortune_2]
    actual = await Fortune.select(session)

    assert expected == actual


@pytest.mark.anyio
async def test_new_or_existing_return_new(
        author,
        create_fortune,
        session,
        tags,
):
    await create_fortune(content='Test', author=author, tags=tags)
    fortune = await Fortune.new_or_existing(session, content='Wtf')

    assert fortune.id is None


@pytest.mark.anyio
async def test_new_or_existing_return_existing(
        author,
        create_fortune,
        session,
        tags,
):
    expected = await create_fortune(content='Test', author=author, tags=tags)
    actual = await Fortune.new_or_existing(session, content='Test')

    assert expected == actual


@pytest.mark.anyio
async def test_with_fortunes(author, create_fortune, session, tags):
    fortune_1 = await create_fortune(
        content='Test 1',
        author=author,
        tags=tags,
    )
    fortune_2 = await create_fortune(
        content='Test 2',
        author=author,
        tags=tags,
    )
    author = await author.with_fortunes(session)
    actual = author.fortunes
    expected = [fortune_1, fortune_2]

    assert expected == actual


def test_datetime_from_string():
    expected = datetime(2025, 2, 26, 23, 31, 55)
    actual = datetime_from_string('2025-02-26T23:31:55')

    assert expected == actual


@pytest.mark.anyio
async def test_delete(author, create_fortune, session, tags):
    fortune = await create_fortune(content='Test', author=author, tags=tags)
    expected = await fortune.delete(session)
    actual = await session.get(Fortune, fortune.id)

    assert expected == actual

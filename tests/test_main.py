from asyncio import sleep
from random import choices, randrange
from string import printable

import pytest
from httpx import ASGITransport, AsyncClient

from lucky.dependencies import catch_session_exceptions, get_session
from lucky.main import app
from lucky.models import datetime_from_string, entity_id_from_string
from lucky.schemas import (
    AuthorName,
    EntityId,
    FortuneContent,
    TagValue,
    max_length,
    min_length
)


@pytest.fixture
async def client(session):
    @catch_session_exceptions
    async def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as async_client:
        yield async_client
    app.dependency_overrides.clear()


def random_str(min_len, max_len, different_from=None):
    length = randrange(min_len, max_len+1)
    while s := ''.join(choices(printable, k=length)):
        if s != different_from:
            return s


def random_value(type_alias, **kwargs):
    min_len = min_length(type_alias)
    max_len = max_length(type_alias)
    return random_str(min_len, max_len, **kwargs)


def random_fortune_payload():
    max_tags = randrange(0, 10)
    return {
        'author': random_value(AuthorName),
        'content': random_value(FortuneContent),
        'tags': [random_value(TagValue) for _ in range(0, max_tags)]
    }


@pytest.fixture
async def create_fortune(client):
    async def _create_fortune(**kwargs):
        payload = random_fortune_payload() | kwargs
        response = await client.post('/api/fortunes', json=payload)
        assert response.status_code == 200
        return response.json()
    return _create_fortune


@pytest.fixture
def entity_id():
    return '0K27TH4PYWP1P'


@pytest.fixture
def invalid_entity_id():
    return 'aaaaaaaaaaaaa'


def match(expected, actual, embedded=False):
    if isinstance(expected, dict):
        if not embedded:
            assert len(expected) == len(actual)
        for k, v in expected.items():
            match(v, actual[k], embedded=embedded)
    elif isinstance(expected, list):
        if not embedded:
            assert len(expected) == len(actual)
        for i, item in enumerate(expected):
            match(item, actual[i], embedded=embedded)
    elif callable(expected):
        assert expected(actual)
    else:
        assert expected == actual


def value_too_long(type_alias):
    length = max_length(type_alias)
    return ''.join(['a'] * (length + 1))


def value_too_short(type_alias):
    length = min_length(type_alias)
    return ''.join(['a'] * (length - 1))


@pytest.mark.anyio
async def test_create_fortune(client):
    payload = random_fortune_payload()
    response = await client.post('/api/fortunes', json=payload)
    actual = response.json()
    expected = {
        'id': entity_id_from_string,
        'author': {
            'id': entity_id_from_string,
            'name': payload['author'],
            'created_at': datetime_from_string
        },
        'content': payload['content'],
        'created_at': datetime_from_string,
        'tags': [
            {
                'id': entity_id_from_string,
                'tag': tag,
                'created_at': datetime_from_string
            }
            for tag in payload['tags']
        ]
    }

    assert response.status_code == 200
    match(expected, actual)


@pytest.mark.parametrize(
    "type_alias,key",
    [(FortuneContent, 'content'), (AuthorName, 'author'), (TagValue, 'tags')],
)
@pytest.mark.anyio
async def test_create_fortune_fail_invalid_payload_string_too_long(
        client,
        type_alias,
        key,
):
    string = value_too_long(type_alias)
    value = [string] if key == 'tags' else string
    payload = random_fortune_payload() | {key: value}
    response = await client.post('/api/fortunes', json=payload)
    actual = response.json()
    expected = {'detail': [{'type': 'string_too_long'}]}

    assert response.status_code == 422
    match(expected, actual, embedded=True)


@pytest.mark.parametrize(
    "type_alias,key",
    [(FortuneContent, 'content'), (AuthorName, 'author'), (TagValue, 'tags')],
)
@pytest.mark.anyio
async def test_create_fortune_fail_invalid_payload_string_too_short(
        client,
        type_alias,
        key,
):
    string = value_too_short(type_alias)
    value = [string] if key == 'tags' else string
    payload = random_fortune_payload() | {key: value}
    response = await client.post('/api/fortunes', json=payload)
    actual = response.json()
    expected = {'detail': [{'type': 'string_too_short'}]}

    assert response.status_code == 422
    match(expected, actual, embedded=True)


@pytest.mark.parametrize("key", ['content', 'author'])
@pytest.mark.anyio
async def test_create_fortune_fail_invalid_payload_missing_key(client, key):
    payload = random_fortune_payload()
    payload.pop(key)
    response = await client.post('/api/fortunes', json=payload)
    actual = response.json()
    expected = {'detail': [{'type': 'missing', 'loc': ['body', key]}]}

    assert response.status_code == 422
    match(expected, actual, embedded=True)


@pytest.mark.anyio
async def test_create_fortune_fail_conflict(client):
    payload = random_fortune_payload()
    response = await client.post('/api/fortunes', json=payload)
    response = await client.post('/api/fortunes', json=payload)
    actual = response.json()
    expected = {'detail': 'fortune exists'}

    assert response.status_code == 409
    match(expected, actual)


@pytest.mark.anyio
async def test_patch_fortune(client, create_fortune):
    fortune = await create_fortune()
    await sleep(1)
    fortune_id = fortune['id']
    payload = random_fortune_payload()
    response = await client.patch(f'/api/fortunes/{fortune_id}', json=payload)
    actual = response.json()
    expected = {
        'id': f'{fortune_id}',
        'author': {
            'id': entity_id_from_string,
            'name': payload['author'],
            'created_at': datetime_from_string
        },
        'content': payload['content'],
        'created_at': datetime_from_string,
        'updated_at': datetime_from_string,
        'tags': [
            {
                'id': entity_id_from_string,
                'tag': tag,
                'created_at': datetime_from_string
            }
            for tag in payload['tags']
        ]
    }

    assert response.status_code == 200
    match(expected, actual)
    assert actual['updated_at'] > actual['created_at']


@pytest.mark.anyio
async def test_patch_fortune_removing_tags(client, create_fortune):
    tag = random_value(TagValue)
    fortune = await create_fortune(tags=[tag])
    fortune_id = fortune['id']
    payload = {'tags': []}
    response = await client.patch(f'/api/fortunes/{fortune_id}', json=payload)
    actual = response.json()
    expected = {
        'id': f'{fortune_id}',
        'created_at': datetime_from_string,
        'updated_at': datetime_from_string,
        'tags': []
    }

    assert response.status_code == 200
    match(expected, actual, embedded=True)


@pytest.mark.parametrize(
    "path,payload",
    [
        ('/api/fortunes', random_fortune_payload()),
        ('/api/authors', {'name': random_value(AuthorName)}),
        ('/api/tags', {'tag': random_value(TagValue)}),
    ],
)
@pytest.mark.anyio
async def test_patch_entity_fail_invalid_id_string_too_long(
        client,
        path,
        payload,
):
    entity_id = value_too_long(EntityId)
    response = await client.patch(f'{path}/{entity_id}', json=payload)
    actual = response.json()
    expected = {'detail': [{'type': 'string_too_long'}]}

    assert response.status_code == 422
    match(expected, actual, embedded=True)


@pytest.mark.parametrize(
    "path,payload",
    [
        ('/api/fortunes', random_fortune_payload()),
        ('/api/authors', {'name': random_value(AuthorName)}),
        ('/api/tags', {'tag': random_value(TagValue)}),
    ],
)
@pytest.mark.anyio
async def test_patch_entity_fail_invalid_id_string_too_short(
        client,
        path,
        payload,
):
    entity_id = value_too_short(EntityId)
    response = await client.patch(f'{path}/{entity_id}', json=payload)
    actual = response.json()
    expected = {'detail': [{'type': 'string_too_short'}]}

    assert response.status_code == 422
    match(expected, actual, embedded=True)


@pytest.mark.parametrize(
    "path,payload",
    [
        ('/api/fortunes', random_fortune_payload()),
        ('/api/authors', {'name': random_value(AuthorName)}),
        ('/api/tags', {'tag': random_value(TagValue)}),
    ],
)
@pytest.mark.anyio
async def test_patch_entity_fail_invalid_id_value_error(
        client,
        invalid_entity_id,
        path,
        payload,
):
    response = await client.patch(f'{path}/{invalid_entity_id}', json=payload)
    actual = response.json()
    expected = {'detail': [{'type': 'value_error'}]}

    assert response.status_code == 422
    match(expected, actual, embedded=True)


@pytest.mark.parametrize(
    "path,payload,entity_name",
    [
        ('/api/fortunes', random_fortune_payload(), 'fortune'),
        ('/api/authors', {'name': random_value(AuthorName)}, 'author'),
        ('/api/tags', {'tag': random_value(TagValue)}, 'tag'),
    ],
)
@pytest.mark.anyio
async def test_patch_entity_fail_not_found(
        client,
        entity_id,
        path,
        payload,
        entity_name,
):
    response = await client.patch(f'{path}/{entity_id}', json=payload)
    actual = response.json()
    expected = {'detail': f'{entity_name} not found'}

    assert response.status_code == 404
    match(expected, actual)


@pytest.mark.anyio
async def test_patch_fortune_fail_conflict(client, create_fortune):
    fortune_1 = await create_fortune()
    content_1 = fortune_1['content']
    content_2 = random_value(FortuneContent, different_from=content_1)
    fortune_2 = await create_fortune(content=content_2)
    fortune_id = fortune_2['id']
    payload = random_fortune_payload() | {'content': content_1}
    response = await client.patch(f'/api/fortunes/{fortune_id}', json=payload)
    actual = response.json()
    expected = {'detail': 'fortune exists'}

    assert response.status_code == 409
    match(expected, actual)


@pytest.mark.anyio
async def test_patch_fortune_fail_empty_payload(client, create_fortune):
    fortune = await create_fortune()
    fortune_id = fortune['id']
    response = await client.patch(f'/api/fortunes/{fortune_id}', json={})
    actual = response.json()
    expected = {'detail': [{'msg': 'Value error, all attributes are missing'}]}

    assert response.status_code == 422
    match(expected, actual, embedded=True)


@pytest.mark.anyio
async def test_get_fortune(client, create_fortune):
    fortune = await create_fortune()
    fortune_id = fortune['id']
    response = await client.get(f'/api/fortunes/{fortune_id}')
    actual = response.json()
    expected = {
        'id': f'{fortune_id}',
        'author': fortune['author'],
        'content': fortune['content'],
        'created_at': datetime_from_string,
        'tags': fortune['tags']
    }

    assert response.status_code == 200
    match(expected, actual)


@pytest.mark.parametrize(
    "path",
    ['/api/fortunes', '/api/authors', '/api/tags'],
)
@pytest.mark.anyio
async def test_get_entity_fail_invalid_id_string_too_long(client, path):
    entity_id = value_too_long(EntityId)
    response = await client.get(f'{path}/{entity_id}')
    actual = response.json()
    expected = {'detail': [{'type': 'string_too_long'}]}

    assert response.status_code == 422
    match(expected, actual, embedded=True)


@pytest.mark.parametrize(
    "path",
    ['/api/fortunes', '/api/authors', '/api/tags'],
)
@pytest.mark.anyio
async def test_get_entity_fail_invalid_id_string_too_short(client, path):
    entity_id = value_too_short(EntityId)
    response = await client.get(f'{path}/{entity_id}')
    actual = response.json()
    expected = {'detail': [{'type': 'string_too_short'}]}

    assert response.status_code == 422
    match(expected, actual, embedded=True)


@pytest.mark.parametrize(
    "path",
    ['/api/fortunes', '/api/authors', '/api/tags'],
)
@pytest.mark.anyio
async def test_get_entity_fail_invalid_id_value_error(
        client,
        invalid_entity_id,
        path,
):
    response = await client.get(f'{path}/{invalid_entity_id}')
    actual = response.json()
    expected = {'detail': [{'type': 'value_error'}]}

    assert response.status_code == 422
    match(expected, actual, embedded=True)


@pytest.mark.parametrize(
    "path,entity_name",
    [
        ('/api/fortunes', 'fortune'),
        ('/api/authors', 'author'),
        ('/api/tags', 'tag'),
    ],
)
@pytest.mark.anyio
async def test_get_entity_fail_not_found(client, entity_id, path, entity_name):
    response = await client.get(f'{path}/{entity_id}')
    actual = response.json()
    expected = {'detail': f'{entity_name} not found'}

    assert response.status_code == 404
    match(expected, actual)


@pytest.mark.anyio
async def test_get_fortunes(client, create_fortune):
    fortune_1 = await create_fortune()
    content_1 = fortune_1['content']
    content_2 = random_value(FortuneContent, different_from=content_1)
    fortune_2 = await create_fortune(content=content_2)
    fortune_1_id = fortune_1['id']
    fortune_2_id = fortune_2['id']
    response = await client.get('/api/fortunes')
    actual = response.json()
    expected = {
        'items': [
            {
                'id': f'{fortune_1_id}',
                'author': fortune_1['author'],
                'content': fortune_1['content'],
                'created_at': datetime_from_string,
                'tags': fortune_1['tags']
            },
            {
                'id': f'{fortune_2_id}',
                'author': fortune_2['author'],
                'content': fortune_2['content'],
                'created_at': datetime_from_string,
                'tags': fortune_2['tags']
            }
        ]
    }

    assert response.status_code == 200
    match(expected, actual)


@pytest.mark.parametrize(
    "path",
    ['/api/fortunes', '/api/authors', '/api/tags'],
)
@pytest.mark.anyio
async def test_get_entities_empty_response(client, path):
    response = await client.get(path)
    actual = response.json()
    expected = {'items': []}

    assert response.status_code == 200
    match(expected, actual)


@pytest.mark.anyio
async def test_get_author(client, create_fortune):
    fortune = await create_fortune()
    author_id = fortune['author']['id']
    name = fortune['author']['name']
    response = await client.get(f'/api/authors/{author_id}')
    actual = response.json()
    fortune.pop('author')
    expected = {
        'id': f'{author_id}',
        'name': name,
        'created_at': datetime_from_string,
        'fortunes': [fortune]
    }

    assert response.status_code == 200
    match(expected, actual)


@pytest.mark.anyio
async def test_get_authors(client, create_fortune):
    fortune_1 = await create_fortune()
    name_1 = fortune_1['author']['name']
    name_2 = random_value(AuthorName, different_from=name_1)
    fortune_2 = await create_fortune(author=name_2)
    author_1_id = fortune_1['author']['id']
    author_2_id = fortune_2['author']['id']
    response = await client.get('/api/authors')
    actual = response.json()
    fortune_1.pop('author')
    fortune_2.pop('author')
    expected = {
        'items': [
            {
                'id': f'{author_1_id}',
                'name': name_1,
                'created_at': datetime_from_string,
                'fortunes': [fortune_1]
            },
            {
                'id': f'{author_2_id}',
                'name': name_2,
                'created_at': datetime_from_string,
                'fortunes': [fortune_2]
            }
        ]
    }

    assert response.status_code == 200
    match(expected, actual)


@pytest.mark.anyio
async def test_patch_author(client, create_fortune):
    fortune = await create_fortune()
    await sleep(1)
    author_id = fortune['author']['id']
    payload = {'name': random_value(AuthorName)}
    response = await client.patch(f'/api/authors/{author_id}', json=payload)
    actual = response.json()
    fortune.pop('author')
    expected = {
        'id': f'{author_id}',
        'name': payload['name'],
        'created_at': datetime_from_string,
        'updated_at': datetime_from_string,
        'fortunes': [fortune]
    }

    assert response.status_code == 200
    match(expected, actual)
    assert actual['updated_at'] > actual['created_at']


@pytest.mark.anyio
async def test_patch_author_fail_conflict(client, create_fortune):
    fortune_1 = await create_fortune()
    name_1 = fortune_1['author']['name']
    name_2 = random_value(AuthorName, different_from=name_1)
    fortune_2 = await create_fortune(author=name_2)
    author_id = fortune_2['author']['id']
    payload = {'name': name_1}
    response = await client.patch(f'/api/authors/{author_id}', json=payload)
    actual = response.json()
    expected = {'detail': 'author exists'}

    assert response.status_code == 409
    match(expected, actual)


@pytest.mark.anyio
async def test_get_tag(client, create_fortune):
    tag = random_value(TagValue)
    fortune = await create_fortune(tags=[tag])
    tag_id = fortune['tags'][0]['id']
    response = await client.get(f'/api/tags/{tag_id}')
    actual = response.json()
    fortune.pop('tags')
    expected = {
        'id': f'{tag_id}',
        'tag': tag,
        'created_at': datetime_from_string,
        'fortunes': [fortune]
    }

    assert response.status_code == 200
    match(expected, actual)


@pytest.mark.anyio
async def test_get_tags(client, create_fortune):
    tag_1 = random_value(TagValue)
    tag_2 = random_value(TagValue, different_from=tag_1)
    fortune = await create_fortune(tags=[tag_1, tag_2])
    tag_1_id = fortune['tags'][0]['id']
    tag_2_id = fortune['tags'][1]['id']
    response = await client.get('/api/tags')
    actual = response.json()
    fortune.pop('tags')
    expected = {
        'items': [
            {
                'id': f'{tag_1_id}',
                'tag': tag_1,
                'created_at': datetime_from_string,
                'fortunes': [fortune]
            },
            {
                'id': f'{tag_2_id}',
                'tag': tag_2,
                'created_at': datetime_from_string,
                'fortunes': [fortune]
            }
        ]
    }

    assert response.status_code == 200
    match(expected, actual)


@pytest.mark.anyio
async def test_patch_tag(client, create_fortune):
    tag = random_value(TagValue)
    fortune = await create_fortune(tags=[tag])
    await sleep(1)
    tag_id = fortune['tags'][0]['id']
    payload = {'tag': random_value(TagValue)}
    response = await client.patch(f'/api/tags/{tag_id}', json=payload)
    actual = response.json()
    fortune.pop('tags')
    expected = {
        'id': f'{tag_id}',
        'tag': payload['tag'],
        'created_at': datetime_from_string,
        'updated_at': datetime_from_string,
        'fortunes': [fortune]
    }

    assert response.status_code == 200
    match(expected, actual)
    assert actual['updated_at'] > actual['created_at']


@pytest.mark.anyio
async def test_patch_tag_fail_conflict(client, create_fortune):
    tag_1 = random_value(TagValue)
    tag_2 = random_value(TagValue, different_from=tag_1)
    fortune = await create_fortune(tags=[tag_1, tag_2])
    tag_id = fortune['tags'][1]['id']
    payload = {'tag': tag_1}
    response = await client.patch(f'/api/tags/{tag_id}', json=payload)
    actual = response.json()
    expected = {'detail': 'tag exists'}

    assert response.status_code == 409
    match(expected, actual)

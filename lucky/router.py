from fastapi import APIRouter, HTTPException
from tenacity import retry, stop_after_attempt, wait_exponential

from .dependencies import SessionDep
from .models import Author, Fortune, Tag
from .schemas import (
    AuthorItems,
    AuthorOut,
    AuthorPatch,
    EntityId,
    FortuneIn,
    FortuneItems,
    FortuneOut,
    FortunePatch,
    TagItems,
    TagOut,
    TagPatch
)

router = APIRouter()


@router.get(
    '/api/tags',
    response_model=TagItems,
    response_model_exclude_none=True,
)
async def get_tags(session: SessionDep) -> dict[str, list[Tag]]:
    tags = await Tag.select(session)
    items = [await tag.with_fortunes(session) for tag in tags]
    return {'items': items}


@router.get(
    '/api/tags/{tag_id}',
    response_model=TagOut,
    response_model_exclude_none=True,
)
async def get_tag(tag_id: EntityId, session: SessionDep) -> Tag:
    tag = await session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="tag not found")
    return await tag.with_fortunes(session)


@router.patch(
    '/api/tags/{tag_id}',
    response_model=TagOut,
    response_model_exclude_none=True,
)
async def patch_tag(
        tag_id: EntityId,
        patch: TagPatch,
        session: SessionDep,
) -> Tag:
    tag = await session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="tag not found")
    tag.tag = patch.tag
    tag = await tag.save(session)
    return await tag.with_fortunes(session)


@router.get(
    '/api/authors',
    response_model=AuthorItems,
    response_model_exclude_none=True,
)
async def get_authors(session: SessionDep) -> dict[str, list[Author]]:
    authors = await Author.select(session)
    items = [await author.with_fortunes(session) for author in authors]
    return {'items': items}


@router.get(
    '/api/authors/{author_id}',
    response_model=AuthorOut,
    response_model_exclude_none=True,
)
async def get_author(author_id: EntityId, session: SessionDep) -> Author:
    author = await session.get(Author, author_id)
    if not author:
        raise HTTPException(status_code=404, detail="author not found")
    return await author.with_fortunes(session)


@router.patch(
    '/api/authors/{author_id}',
    response_model=AuthorOut,
    response_model_exclude_none=True,
)
async def patch_author(
        author_id: EntityId,
        patch: AuthorPatch,
        session: SessionDep,
) -> Author:
    author = await session.get(Author, author_id)
    if not author:
        raise HTTPException(status_code=404, detail="author not found")
    author.name = patch.name
    author = await author.save(session)
    return await author.with_fortunes(session)


@router.get(
    '/api/fortunes',
    response_model=FortuneItems,
    response_model_exclude_none=True,
)
async def get_fortunes(session: SessionDep) -> dict[str, list[Fortune]]:
    items = await Fortune.select(session)
    return {'items': items}


@router.get(
    '/api/fortunes/{fortune_id}',
    response_model=FortuneOut,
    response_model_exclude_none=True,
)
async def get_fortune(fortune_id: EntityId, session: SessionDep) -> Fortune:
    fortune = await session.get(Fortune, fortune_id)
    if not fortune:
        raise HTTPException(status_code=404, detail="fortune not found")
    return fortune


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=0.1, min=0.1),
    stop=stop_after_attempt(4),
)
async def _patch_fortune(
        fortune_id: EntityId,
        patch: FortunePatch,
        session: SessionDep,
) -> Fortune:
    fortune = await session.get(Fortune, fortune_id)
    if not fortune:
        raise HTTPException(status_code=404, detail="fortune not found")
    fortune.flag_modified('content')
    if patch.author:
        author = await Author.new_or_existing(session, name=patch.author)
        fortune.author = author
    if patch.content:
        fortune.content = patch.content
    with session.no_autoflush:
        if patch.tags is not None:
            tags = [
                await Tag.new_or_existing(session, tag=tag)
                for tag in patch.tags
            ]
            fortune.tags = tags
    return await fortune.save(session)


@router.patch(
    '/api/fortunes/{fortune_id}',
    response_model=FortuneOut,
    response_model_exclude_none=True,
)
async def patch_fortune(
        fortune_id: EntityId,
        patch: FortunePatch,
        session: SessionDep,
) -> Fortune:
    return await _patch_fortune(fortune_id, patch, session)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=0.1, min=0.1),
    stop=stop_after_attempt(4),
)
async def _create_fortune(
        fortune_in: FortuneIn,
        session: SessionDep,
) -> Fortune:
    author = await Author.new_or_existing(session, name=fortune_in.author)
    tags = [
        await Tag.new_or_existing(session, tag=tag)
        for tag in fortune_in.tags
    ]
    fortune = Fortune(content=fortune_in.content, author=author, tags=tags)
    return await fortune.save(session)


@router.post(
    '/api/fortunes',
    response_model=FortuneOut,
    response_model_exclude_none=True,
)
async def create_fortune(
        fortune_in: FortuneIn,
        session: SessionDep,
) -> Fortune:
    return await _create_fortune(fortune_in, session)

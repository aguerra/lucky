import asyncio
import csv
import sys

from lucky.models import (
    Author,
    Base,
    Fortune,
    Tag,
    async_session,
    engine
)


async def main():
    path = sys.argv[1]

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with async_session() as session, session.begin():
        with open(path) as f:
            reader = csv.DictReader(f)
            all_authors = {}
            all_fortunes = {}
            all_tags = {}
            for row in reader:
                author_name = row.pop('author')
                if author_name not in all_authors:
                    author = Author(name=author_name)
                    all_authors[author_name] = author

                fortune_content = row.pop('fortune')
                if fortune_content in all_fortunes:
                    continue
                fortune = Fortune(content=fortune_content)
                fortune.author = all_authors[author_name]
                session.add(fortune)
                all_fortunes[fortune_content] = fortune

                tag_list = row.pop('tags').split('/')
                for tag_name in tag_list:
                    if tag_name not in all_tags:
                        tag = Tag(tag=tag_name)
                        all_tags[tag_name] = tag
                    fortune.tags.append(all_tags[tag_name])


if __name__ == '__main__':
    asyncio.run(main())

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from sqlmodel import select

from app.database import async_session
from app.models.feed import Feed


@dataclass
class FeedResult:
    success: bool
    feed: Optional[Feed] = None
    error: Optional[str] = None


async def subscribe_feed(title: str, url: str, channel_id: int) -> FeedResult:
    async with async_session() as session:
        query = select(Feed).where(Feed.url == url, Feed.channel_id == channel_id)
        result = await session.exec(query)
        feed = result.one_or_none()
        if feed:
            return FeedResult(success=False, error=f"{url} already exists")

        # here should have a unique constraint on url and channel_id check, simplify for now
        new_feed = Feed(title=title, url=url, channel_id=channel_id)
        session.add(new_feed)
        await session.commit()
        await session.refresh(new_feed)

        return FeedResult(success=True, feed=new_feed)


async def get_feeds_by_channel(channel_id: int) -> Sequence[Feed]:
    async with async_session() as session:
        query = select(Feed).where(Feed.channel_id == channel_id)
        result = await session.exec(query)
        subscriptions = result.all()
        return subscriptions


async def get_all_channel_ids() -> Sequence[int]:
    async with async_session() as session:
        query = select(Feed.channel_id).distinct()
        result = await session.exec(query)
        return result.all()


async def update_last_checked(feed_id: int) -> FeedResult:
    async with async_session() as session:
        query = select(Feed).where(Feed.id == feed_id)
        result = await session.exec(query)
        feed = result.one_or_none()
        if feed:
            feed.last_checked = datetime.utcnow()
            await session.commit()
            return FeedResult(success=True, feed=feed)
        else:
            return FeedResult(success=False, error=f"Feed with id {feed_id} not found")


async def unsubscribe_feed(url: str, channel_id: int) -> FeedResult:
    async with async_session() as session:
        result = await session.exec(select(Feed).where(Feed.url == url, Feed.channel_id == channel_id))
        feed = result.one_or_none()
        if feed:
            await session.delete(feed)
            await session.commit()
            return FeedResult(success=True, feed=feed)
        else:
            return FeedResult(success=False, error=f"{url} not found for feed unsubscribing")

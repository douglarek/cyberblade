from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class Feed(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field()
    url: str = Field(index=True)
    channel_id: int = Field(index=True)
    last_checked: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (UniqueConstraint("url", "channel_id", name="unique_item_url_channel_id"),)

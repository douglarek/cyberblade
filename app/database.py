from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config.settings import settings

engine = create_async_engine(settings.database_url)
async_session = lambda: AsyncSession(engine)

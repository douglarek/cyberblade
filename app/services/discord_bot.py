import asyncio
import io
import logging
import re
import traceback
from datetime import datetime
from time import mktime

import feedparser  # type: ignore
import nextcord
from nextcord.ext import application_checks, commands

from app.config.settings import settings
from app.services.feed import (
    get_all_channel_ids,
    get_feeds_by_channel,
    subscribe_feed,
    unsubscribe_feed,
    update_last_checked,
)
from app.services.poem_api import HTTPService

logger = logging.getLogger(__name__)
http_service = HTTPService()


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # create the background task and run it in the background
        self.bg_task = self.loop.create_task(self.rss_task())

    async def rss_task(self):
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                channel_ids = await get_all_channel_ids()
                for channel_id in channel_ids:
                    channel = await self.fetch_channel(channel_id)
                    if channel:
                        feeds = await get_feeds_by_channel(channel_id)
                        for _feed in feeds.feeds:
                            feed = await parse_feed(_feed.url)
                            if not feed or not feed.version:
                                # here should delete feed or notify user
                                logger.error(f"Invalid feed url: {_feed.url}")
                                continue
                            if feed.entries:
                                entry = feed.entries[0]
                                dt = entry.get("published_parsed") or entry.get("updated_parsed")  # rss, aotm
                                published = datetime.fromtimestamp(mktime(dt)) if dt else datetime.utcnow()
                                logger.info(f"checking feed: {_feed.url}, last_updated: {_feed.last_checked}")
                                if (not _feed.last_checked) or published > _feed.last_checked:
                                    logger.info(f"New entry found in: {_feed.url}, last_checked: {_feed.last_checked}")
                                    await channel.send(content=f":newspaper2: [{entry.title}]({entry.link})")
                                    res = await update_last_checked(_feed.id)
                                    logger.info(f"update last_checked: {res}")
            except Exception as e:  # handle all exceptions here to avoid task hang
                info = await self.application_info()
                channel = await self.create_dm(info.owner)
                await channel.send(f"```feed task error: {traceback.format_exc()}```")
                logger.error(f"feed task error: {e}", exc_info=True)
            logger.info("feed task finished, sleep 5 min")
            await asyncio.sleep(60 * 5)  # 5m


intents = nextcord.Intents.default()
intents.message_content = True
bot = Bot(intents=intents)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")


def process_twitter_urls(text):
    pattern = r"https?://(?:twitter\.com|x\.com)/(\w+)/status/(\d+)"
    urls = []
    users = []

    for match in re.finditer(pattern, text):
        user, tweet_id = match.groups()
        replaced_url = f"https://fxtwitter.com/{user}/status/{tweet_id}"
        urls.append(replaced_url)
        users.append(user)

    return urls, users


@bot.event
async def on_message(message: nextcord.Message):
    if message.author == bot.user or message.mention_everyone:
        return

    assert bot.user
    if settings.enable_fxtwitter:
        urls, users = process_twitter_urls(message.content)
        if not urls:
            return
        async with message.channel.typing():
            await message.add_reaction("💬")
            await message.channel.send(content=f":bird: [Tweet • {users[0]}]({urls[0]})")


@bot.slash_command(description="cyberblade main command")
async def cyberblade(interaction: nextcord.Interaction):
    """
    This is the main slash command that will be the prefix of all commands below.
    This will never get called since it has subcommands.
    """


@cyberblade.subcommand(description="feed subcommand")
async def feed(interaction: nextcord.Interaction):
    """
    This is the second slash command that will be the prefix of all commands below.
    This will never get called since it has subcommands.
    """


async def parse_feed(url: str):
    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, url)
    return feed


@feed.subcommand(description="test a rss feed", name="test")
async def test_feed(
    interaction: nextcord.Interaction,
    url: str = nextcord.SlashOption(description="a rss feed url", required=True),
):
    """
    This is a subcommand of the '/cyberblade feed' command.
    It will appear in the menu as '/cyberblade feed test'.
    """
    await interaction.response.defer(ephemeral=True)
    feed = await parse_feed(url)
    if not feed.version:
        return await interaction.followup.send(
            embed=nextcord.Embed(description="Invalid feed url", color=nextcord.Color.red()), delete_after=10
        )
    if feed.entries:
        entry = feed.entries[0]
        return await interaction.followup.send(content=f":newspaper2: [{entry.title}]({entry.link})", delete_after=30)
    await interaction.followup.send(content="No entries found", delete_after=10)


@feed.subcommand(description="subscribe a rss feed", name="sub")
@application_checks.is_owner()
async def sub_feed(
    interaction: nextcord.Interaction,
    url: str = nextcord.SlashOption(description="a rss feed url", required=True),
):
    """
    This is a subcommand of the '/cyberblade feed' command.
    It will appear in the menu as '/cyberblade feed sub'.
    """
    await interaction.response.defer(ephemeral=True)
    feed = await parse_feed(url)
    if not feed.version:
        return await interaction.followup.send(
            embed=nextcord.Embed(description="Invalid feed url", color=nextcord.Color.red()), delete_after=10
        )
    assert interaction.channel
    sr = await subscribe_feed(feed.feed.title, url, interaction.channel.id)
    if sr.success:
        assert sr.feed
        return await interaction.followup.send(
            content=f"**Subscribe feed successful:** [{sr.feed.title}]({sr.feed.url}).",
            delete_after=10,
        )
    await interaction.followup.send(content=f"**Failed to subscribe:** {sr.error}", delete_after=10)


@feed.subcommand(description="unsubscribe a rss feed", name="unsub")
@application_checks.is_owner()
async def unsub_feed(
    interaction: nextcord.Interaction,
    url: str = nextcord.SlashOption(description="a rss feed url", required=True),
):
    """
    This is a subcommand of the '/cyberblade feed' command.
    It will appear in the menu as '/cyberblade feed ubsub'.
    """
    await interaction.response.defer(ephemeral=True)
    assert interaction.channel
    sr = await unsubscribe_feed(url, interaction.channel.id)
    if sr.success:
        assert sr.feed
        return await interaction.followup.send(
            content=f"**Unsubscription successful:** [{sr.feed.title}]({sr.feed.url}).",
            delete_after=10,
        )
    await interaction.followup.send(content=f"**Failed to unsubscribe:** {sr.error}", delete_after=10)


@feed.subcommand(description="list rss feeds", name="list")
async def list_feed(interaction: nextcord.Interaction):
    """
    This is a subcommand of the '/cyberblade feed' command.
    It will appear in the menu as '/cyberblade feed list'.
    """
    await interaction.response.defer(ephemeral=True)
    assert interaction.channel
    feeds = await get_feeds_by_channel(interaction.channel.id)
    if feeds.feeds:
        return await interaction.followup.send(
            content="\n".join([f"{i}. [{s.title}]({s.url})" for i, s in enumerate(feeds.feeds, 1)]),
            delete_after=30,
        )
    await interaction.followup.send(content="No feed found", delete_after=10)


@feed.subcommand(description="export rss feeds to opml file", name="export")
async def export_feed(interaction: nextcord.Interaction):
    """
    This is a subcommand of the '/cyberblade feed' command.
    It will appear in the menu as '/cyberblade feed export'.
    """
    await interaction.response.defer(ephemeral=True)
    assert interaction.channel
    feeds = await get_feeds_by_channel(interaction.channel.id, return_opml=True)
    if feeds.opml:
        return await interaction.followup.send(
            content="Here is your opml file",
            file=nextcord.File(
                io.BytesIO(feeds.opml.encode()), filename=f"feeds_{datetime.utcnow().strftime('%Y%m%d%H%M')}.opml"
            ),
        )
    await interaction.followup.send(content="No feed found", delete_after=10)


if settings.jinrishici_token:
    logger.info("random_poem command enabled")

    @cyberblade.subcommand(description="random a poem")
    async def random_poem(interaction: nextcord.Interaction):
        """
        This is a subcommand of the '/cyberblade' slash command.
        It will appear in the menu as '/cyberblade random_poem'.
        """
        logger.info("random_poem command called")
        await interaction.response.defer()
        res = await http_service.jinrishici_sentence()
        if res["status"] == "success":
            data = res["data"]["origin"]
            embed = nextcord.Embed(
                title=data["title"],
                description="\n".join(data["content"]),
                color=nextcord.Color.green(),
            )
            embed.set_author(name=data["author"], url="https://zh.wikipedia.org/wiki/" + data["author"])
            if data["translate"]:
                embed.add_field(name="译文", value="> " + ("".join(data["translate"])))
            return await interaction.followup.send(content="📖 "  +res["data"]["content"], embed=embed)

        await interaction.followup.send(
            content="error occurred and this message will be auto deleted in 10 seconds. :cry:",
            ephemeral=True,
            delete_after=10,
        )


def start():
    bot.run(settings.discord_bot_token)

import asyncio
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from config import Settings

MAX_MESSAGE_LENGTH = 1_500
logger = logging.getLogger(__name__)


class Cooldown:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self.last_sent: dict[int, float] = {}
        self.lock = asyncio.Lock()

    async def acquire(self, user_id: int) -> float | None:
        async with self.lock:
            now = time.monotonic()
            previous = self.last_sent.get(user_id)
            remaining = self.seconds - (now - previous) if previous is not None else 0
            if remaining > 0:
                return remaining
            self.last_sent[user_id] = now
            return None

    async def release(self, user_id: int) -> None:
        async with self.lock:
            self.last_sent.pop(user_id, None)


class AnonymousModal(discord.ui.Modal, title="익명 메시지 작성"):
    message = discord.ui.TextInput(label="메시지", style=discord.TextStyle.paragraph, min_length=1, max_length=MAX_MESSAGE_LENGTH)

    def __init__(self, settings: Settings, cooldown: Cooldown) -> None:
        super().__init__(timeout=300)
        self.settings = settings
        self.cooldown = cooldown

    async def on_submit(self, interaction: discord.Interaction) -> None:
        content = self.message.value.strip()
        if not content:
            logger.info("Rejected blank anonymous message.")
            await interaction.response.send_message("메시지를 입력해 주세요.", ephemeral=True)
            return
        if interaction.guild_id != self.settings.guild_id:
            logger.warning("Rejected anonymous message from an unapproved server.")
            await interaction.response.send_message("이 서버에서는 사용할 수 없어요.", ephemeral=True)
            return
        remaining = await self.cooldown.acquire(interaction.user.id)
        if remaining is not None:
            logger.info("Rejected anonymous message during cooldown.")
            await interaction.response.send_message(f"잠시 후 다시 시도해 주세요. ({remaining:.0f}초 남음)", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            anonymous_channel = interaction.client.get_channel(self.settings.anonymous_channel_id)
            if anonymous_channel is None:
                anonymous_channel = await interaction.client.fetch_channel(self.settings.anonymous_channel_id)
            log_channel = interaction.client.get_channel(self.settings.anonymous_log_channel_id)
            if log_channel is None:
                log_channel = await interaction.client.fetch_channel(self.settings.anonymous_log_channel_id)

            if (
                not isinstance(anonymous_channel, discord.TextChannel)
                or not isinstance(log_channel, discord.TextChannel)
                or anonymous_channel.guild.id != self.settings.guild_id
                or log_channel.guild.id != self.settings.guild_id
            ):
                raise LookupError

            log_embed = discord.Embed(
                title="🔒 익명 메시지 기록",
                description=content,
                color=discord.Color.dark_gold(),
            )
            log_embed.add_field(
                name="작성자",
                value=f"{interaction.user} (ID: {interaction.user.id})",
                inline=False,
            )
            await log_channel.send(embed=log_embed, allowed_mentions=discord.AllowedMentions.none())

            embed = discord.Embed(
                title="📨 익명 메시지",
                description=content,
                color=discord.Color.blurple(),
            )
            await anonymous_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.NotFound, discord.HTTPException, LookupError):
            await self.cooldown.release(interaction.user.id)
            logger.warning("Anonymous-message delivery failed because of Discord or channel configuration.")
            await interaction.followup.send("전송에 실패했어요. 익명 채널·로그 채널 설정과 권한을 확인해 주세요.", ephemeral=True)
        except Exception:
            await self.cooldown.release(interaction.user.id)
            logger.exception("Unexpected anonymous-message delivery error")
            await interaction.followup.send("알 수 없는 오류가 발생했어요. 잠시 후 다시 시도해 주세요.", ephemeral=True)
        else:
            logger.info("Anonymous message delivered.")
            await interaction.followup.send("익명 메시지를 보냈어요.", ephemeral=True)


class AnonymousCog(commands.Cog):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cooldown = Cooldown(settings.cooldown_seconds)

    @app_commands.command(name="익명", description="익명으로 메시지를 보냅니다.")
    async def anonymous(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id != self.settings.guild_id:
            await interaction.response.send_message("이 서버에서는 사용할 수 없어요.", ephemeral=True)
            return
        await interaction.response.send_modal(AnonymousModal(self.settings, self.cooldown))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AnonymousCog(Settings.from_environment()))

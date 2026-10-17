import random

import discord
from discord import app_commands
from discord.ext import commands

from config import Settings


class TeamCog(commands.Cog):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.random = random.SystemRandom()

    @app_commands.command(name="팀짜기", description="현재 통화방 인원을 무작위로 두 팀으로 나눕니다.")
    async def make_teams(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id != self.settings.guild_id:
            await interaction.response.send_message("이 서버에서는 사용할 수 없어요.", ephemeral=True)
            return

        member = interaction.user
        voice_channel = member.voice.channel if isinstance(member, discord.Member) and member.voice else None
        if voice_channel is None:
            await interaction.response.send_message("먼저 통화방에 들어가 주세요.", ephemeral=True)
            return

        participants = [voice_member for voice_member in voice_channel.members if not voice_member.bot]
        if len(participants) < 2:
            await interaction.response.send_message("팀을 나누려면 통화방에 두 명 이상 있어야 해요.", ephemeral=True)
            return

        self.random.shuffle(participants)
        first_team_size = (len(participants) + 1) // 2
        team_a = participants[:first_team_size]
        team_b = participants[first_team_size:]

        embed = discord.Embed(
            title="🎲 랜덤 팀 배정",
            description=f"통화방: {voice_channel.name} · 총 {len(participants)}명",
            color=discord.Color.green(),
        )
        embed.add_field(
            name=f"팀 A · {len(team_a)}명",
            value="\n".join(f"• {participant.display_name}" for participant in team_a),
            inline=True,
        )
        embed.add_field(
            name=f"팀 B · {len(team_b)}명",
            value="\n".join(f"• {participant.display_name}" for participant in team_b),
            inline=True,
        )
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TeamCog(Settings.from_environment()))

import sqlite3
from datetime import date

import discord
from discord import app_commands
from discord.ext import commands

DATABASE_PATH = "economy.db"
EMBED_COLOR = discord.Color.blurple()
DAILY_REWARD = 1_000


def embed(title: str, description: str, *, color: discord.Color = EMBED_COLOR) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


class Economy:
    """SQLite 잔액 작업을 한곳에 모아 둔 간단한 동기식 저장소입니다."""

    @staticmethod
    def _ensure_user(connection: sqlite3.Connection, user_id: int) -> None:
        connection.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))

    @classmethod
    def balance(cls, user_id: int) -> int:
        with sqlite3.connect(DATABASE_PATH) as connection:
            cls._ensure_user(connection, user_id)
            return connection.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]

    @classmethod
    def change_balance(cls, user_id: int, amount: int) -> int:
        with sqlite3.connect(DATABASE_PATH) as connection:
            cls._ensure_user(connection, user_id)
            connection.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            return connection.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()[0]

    @classmethod
    def transfer(cls, sender_id: int, receiver_id: int, amount: int) -> bool:
        with sqlite3.connect(DATABASE_PATH) as connection:
            cls._ensure_user(connection, sender_id)
            cls._ensure_user(connection, receiver_id)
            cursor = connection.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
                (amount, sender_id, amount),
            )
            if cursor.rowcount != 1:
                return False
            connection.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, receiver_id))
            return True


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="출석", description="하루 한 번 출석 보상을 받습니다.")
    async def attendance(self, interaction: discord.Interaction) -> None:
        today = date.today().isoformat()
        with sqlite3.connect(DATABASE_PATH) as connection:
            Economy._ensure_user(connection, interaction.user.id)
            last = connection.execute("SELECT last_attendance FROM users WHERE user_id = ?", (interaction.user.id,)).fetchone()[0]
            if last == today:
                await interaction.response.send_message(embed=embed("출석", "오늘은 이미 출석했습니다.", color=discord.Color.orange()), ephemeral=True)
                return
            connection.execute("UPDATE users SET balance = balance + ?, last_attendance = ? WHERE user_id = ?", (DAILY_REWARD, today, interaction.user.id))
        await interaction.response.send_message(embed=embed("출석 완료", f"{DAILY_REWARD:,} 코인을 받았습니다."), ephemeral=True)

    @app_commands.command(name="프로필", description="보유 코인을 확인합니다.")
    async def profile(self, interaction: discord.Interaction, 회원: discord.Member | None = None) -> None:
        member = 회원 or interaction.user
        balance = Economy.balance(member.id)
        card = embed(f"{member.display_name}님의 프로필", f"보유 코인: **{balance:,}**")
        card.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=card)

    @app_commands.command(name="송금", description="다른 회원에게 코인을 보냅니다.")
    @app_commands.describe(회원="받는 회원", 금액="보낼 코인")
    async def send(self, interaction: discord.Interaction, 회원: discord.Member, 금액: app_commands.Range[int, 1]) -> None:
        if 회원.bot or 회원.id == interaction.user.id:
            await interaction.response.send_message(embed=embed("송금 실패", "본인 또는 봇에게는 송금할 수 없습니다.", color=discord.Color.red()), ephemeral=True)
            return
        if not Economy.transfer(interaction.user.id, 회원.id, 금액):
            await interaction.response.send_message(embed=embed("송금 실패", "보유 코인이 부족합니다.", color=discord.Color.red()), ephemeral=True)
            return
        await interaction.response.send_message(embed=embed("송금 완료", f"{회원.mention}에게 **{금액:,}** 코인을 보냈습니다."))

    @app_commands.command(name="코인랭킹", description="보유 코인 순위를 봅니다.")
    async def ranking(self, interaction: discord.Interaction) -> None:
        with sqlite3.connect(DATABASE_PATH) as connection:
            rows = connection.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10").fetchall()
        lines = [f"{rank}. <@{user_id}> — **{balance:,}**" for rank, (user_id, balance) in enumerate(rows, 1)]
        await interaction.response.send_message(embed=embed("코인 랭킹", "\n".join(lines) if lines else "아직 등록된 회원이 없습니다."))

    @app_commands.command(name="코인지급", description="관리자가 회원에게 코인을 지급합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    async def grant(self, interaction: discord.Interaction, 회원: discord.Member, 금액: app_commands.Range[int, 1]) -> None:
        balance = Economy.change_balance(회원.id, 금액)
        await interaction.response.send_message(embed=embed("코인 지급", f"{회원.mention}에게 **{금액:,}** 코인을 지급했습니다.\n현재 잔액: **{balance:,}**"))

    @grant.error
    async def grant_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(embed=embed("권한 없음", "관리자만 사용할 수 있습니다.", color=discord.Color.red()), ephemeral=True)
            return
        raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EconomyCog(bot))

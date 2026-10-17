
import os
import sqlite3

import discord
from discord.ext import commands
from dotenv import load_dotenv

DATABASE_PATH = "economy.db"

# 로컬 실행 시 .env를 읽고, 배포 서비스의 환경 변수도 그대로 지원합니다.
load_dotenv()


def create_database() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 1000,
                last_attendance TEXT
            );
        """)


class Bot(commands.Bot):

    async def setup_hook(self) -> None:
        for extension in ("economy", "seotda", "baccarat", "anonymous", "team"):
            await self.load_extension(extension)

        guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
        if guild_id:
            try:
                guild = discord.Object(id=int(guild_id))
            except ValueError as error:
                raise RuntimeError(
                    "DISCORD_GUILD_ID는 숫자로 된 Discord 서버 ID여야 합니다."
                ) from error

            # 전역 명령어를 이 서버에 복사하면 즉시 반영됩니다.
            self.tree.copy_global_to(guild=guild)
            # 이전 배포에서 남은 전역 명령어를 제거해 중복 표시를 방지합니다.
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            await self.tree.sync(guild=guild)
            print("서버 전용 슬래시 명령어를 동기화했습니다.")
        else:
            commands_synced = await self.tree.sync()
            print(f"전역 슬래시 명령 {len(commands_synced)}개를 동기화했습니다.")



def main() -> None:
    token = os.getenv("DISCORD_TOKEN", "").strip() or os.getenv("DISCORD_BOT_TOKEN", "").strip()

    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN 또는 DISCORD_BOT_TOKEN 환경 변수를 설정하세요."
        )

    create_database()

    intents = discord.Intents.default()
    intents.voice_states = True
    bot = Bot(command_prefix="!", intents=intents)
    bot.run(token)


if __name__ == "__main__":
    main()

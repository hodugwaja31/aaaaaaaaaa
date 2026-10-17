import random

import discord
from discord import app_commands
from discord.ext import commands

from economy import Economy, embed


def draw_card() -> int:
    return random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 0, 0, 0])


def score(cards: list[int]) -> int:
    return sum(cards) % 10


def standard_draw(player: list[int], banker: list[int]) -> None:
    """표준 Punto Banco 3장 규칙."""
    player_total, banker_total = score(player), score(banker)
    if player_total in (8, 9) or banker_total in (8, 9):
        return
    player_third = None
    if player_total <= 5:
        player_third = draw_card()
        player.append(player_third)
    banker_total = score(banker)
    if player_third is None:
        if banker_total <= 5:
            banker.append(draw_card())
        return
    if banker_total <= 2 or (banker_total == 3 and player_third != 8) or (banker_total == 4 and 2 <= player_third <= 7) or (banker_total == 5 and 4 <= player_third <= 7) or (banker_total == 6 and player_third in (6, 7)):
        banker.append(draw_card())


class BaccaratCog(commands.Cog):
    @app_commands.command(name="바카라", description="표준 3카드 바카라를 합니다. 최소 500코인입니다.")
    @app_commands.describe(금액="배팅 금액", 선택="뱅커, 플레이어 또는 무승부")
    @app_commands.choices(선택=[app_commands.Choice(name="뱅커", value="banker"), app_commands.Choice(name="플레이어", value="player"), app_commands.Choice(name="무승부", value="tie")])
    async def baccarat(self, interaction: discord.Interaction, 금액: app_commands.Range[int, 500], 선택: app_commands.Choice[str]) -> None:
        if Economy.balance(interaction.user.id) < 금액:
            await interaction.response.send_message(embed=embed("바카라", "보유 코인이 부족합니다.", color=discord.Color.red()), ephemeral=True)
            return
        player, banker = [draw_card(), draw_card()], [draw_card(), draw_card()]
        standard_draw(player, banker)
        player_score, banker_score = score(player), score(banker)
        winner = "tie" if player_score == banker_score else ("player" if player_score > banker_score else "banker")
        labels = {"banker": "뱅커", "player": "플레이어", "tie": "무승부"}
        won = 선택.value == winner
        payout = 금액 * (10 if winner == "tie" else 2) if won else 0
        Economy.change_balance(interaction.user.id, payout - 금액)
        card = embed("바카라 결과", f"선택: **{labels[선택.value]}**\n결과: **{labels[winner]}**", color=discord.Color.green() if won else discord.Color.red())
        card.add_field(name=f"플레이어 ({player_score})", value=" · ".join(map(str, player)), inline=False)
        card.add_field(name=f"뱅커 ({banker_score})", value=" · ".join(map(str, banker)), inline=False)
        card.add_field(name="정산", value=f"{'승리: ' + format(payout, ',') + ' 코인' if won else '패배: ' + format(금액, ',') + ' 코인'}", inline=False)
        await interaction.response.send_message(embed=card)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BaccaratCog(bot))

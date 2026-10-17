import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from economy import Economy, embed
from seotda_rules import Hand, evaluate, shuffled_deck


MAX_PLAYERS = 8


class Game:
    def __init__(self, host: int, bet: int) -> None:
        self.host, self.bet = host, bet
        self.players: list[int] = [host]
        self.cards: dict[int, list] = {}
        self.paid: dict[int, int] = {}
        self.folded: set[int] = set()
        self.pot = 0
        self.started = False
        self.turn = 0
        self.pending: set[int] = set()
        self.current_bet = bet

    def active(self) -> list[int]:
        return [player for player in self.players if player not in self.folded]


def hand_text(cards: list) -> str:
    return f"{cards[0].month}월 · {cards[1].month}"


class SeotdaCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.games: dict[int, Game] = {}
        self.lock = asyncio.Lock()

    def _deal(self, game: Game) -> None:
        """Deal new cards to active players while preserving folded players' last cards."""
        deck = shuffled_deck()
        new_cards = {
            player: [deck.pop(), deck.pop()]
            for player in game.active()
        }
        game.cards.update(new_cards)

    async def _send_private_hands(self, game: Game) -> None:
        """Send each active player their own cards and hand ranking by DM."""
        for player in game.active():
            cards = game.cards.get(player)
            if cards is None:
                continue

            hand = evaluate(cards)
            message = (
                "🎴 **섯다 카드 안내**\n"
                f"카드: **{hand_text(cards)}**\n"
                f"족보: **{hand.name}**"
            )

            try:
                user = self.bot.get_user(player)
                if user is None:
                    user = await self.bot.fetch_user(player)
                await user.send(message)
            except (discord.Forbidden, discord.HTTPException):
                # DM을 받을 수 없어도 게임은 계속 진행한다.
                pass

    def _all_hands_text(self, game: Game) -> str:
        """Build a public list of all players' cards and hand rankings."""
        lines = []

        for player in game.players:
            cards = game.cards.get(player)
            if cards is None:
                lines.append(f"<@{player}> — 확인 가능한 카드가 없습니다.")
                continue

            hand = evaluate(cards)
            status = " (다이)" if player in game.folded else ""
            lines.append(
                f"<@{player}>{status}\n"
                f"카드: **{hand_text(cards)}** · 족보: **{hand.name}**"
            )

        return "\n".join(lines)

    def _replay_reason(self, game: Game) -> str | None:
        hands = [evaluate(game.cards[player]) for player in game.active()]

        for hand in hands:
            if hand.special == "meong" and any(
                other is not hand and other.rank <= 90 for other in hands
            ):
                return "멍텅구리구사와 장땡 이하 패이므로 재경기합니다."

        for hand in hands:
            if hand.special == "gusa" and any(
                other is not hand and other.rank <= 79 for other in hands
            ):
                return "구사와 알리 이하 패이므로 재경기합니다."

        return None

    def _winner(self, game: Game) -> int:
        active = game.active()
        hands = {player: evaluate(game.cards[player]) for player in active}
        highest_rank = max(hand.rank for hand in hands.values())
        leaders = [
            player for player in active
            if hands[player].rank == highest_rank
        ]

        if hands[leaders[0]].special == "gwang":
            special_players = [
                player for player in active
                if hands[player].special == "secret"
            ]
            if special_players:
                return max(
                    special_players,
                    key=lambda player: hands[player].rank,
                )

        if hands[leaders[0]].special == "ddaeng":
            special_players = [
                player for player in active
                if hands[player].special == "catcher"
            ]
            if special_players:
                return max(
                    special_players,
                    key=lambda player: hands[player].rank,
                )

        return leaders[0]

    @app_commands.command(name="섯다", description="섯다 방을 만들거나 참가합니다.")
    async def seotda(
        self,
        interaction: discord.Interaction,
        금액: app_commands.Range[int, 100, 1_000_000],
    ) -> None:
        channel_id, user_id = interaction.channel_id, interaction.user.id

        async with self.lock:
            game = self.games.get(channel_id)

            if game is None:
                self.games[channel_id] = Game(user_id, 금액)
                response = embed(
                    "섯다 방 생성",
                    f"판돈: **{금액:,}** 코인\n"
                    f"참가: `/섯다 {금액}` · 방장 시작: `/섯다시작`",
                )
                await interaction.response.send_message(embed=response)

            elif game.started:
                await interaction.response.send_message(
                    embed=embed(
                        "섯다",
                        "진행 중인 섯다 게임이 있습니다.",
                        color=discord.Color.orange(),
                    ),
                    ephemeral=True,
                )

            elif user_id in game.players:
                await interaction.response.send_message(
                    embed=embed(
                        "섯다",
                        "이미 참가했습니다.",
                        color=discord.Color.orange(),
                    ),
                    ephemeral=True,
                )

            elif len(game.players) >= MAX_PLAYERS:
                await interaction.response.send_message(
                    embed=embed(
                        "섯다",
                        "최대 8명까지 참가할 수 있습니다.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )

            else:
                game.players.append(user_id)
                await interaction.response.send_message(
                    embed=embed(
                        "섯다 참가",
                        f"{interaction.user.mention}님이 참가했습니다. "
                        f"({len(game.players)}/{MAX_PLAYERS})",
                    )
                )

    @app_commands.command(
        name="섯다시작",
        description="대기 중인 섯다를 시작합니다.",
    )
    async def start(self, interaction: discord.Interaction) -> None:
        async with self.lock:
            game = self.games.get(interaction.channel_id)

            if (
                game is None
                or game.host != interaction.user.id
                or len(game.players) < 2
            ):
                await interaction.response.send_message(
                    embed=embed(
                        "섯다 시작",
                        "방장만 2명 이상일 때 시작할 수 있습니다.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            if any(
                Economy.balance(player) < game.bet
                for player in game.players
            ):
                await interaction.response.send_message(
                    embed=embed(
                        "섯다 시작",
                        "참가자 중 보유 코인이 부족한 사람이 있습니다.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            for player in game.players:
                Economy.change_balance(player, -game.bet)

            game.pot = game.bet * len(game.players)
            game.paid = {
                player: game.bet
                for player in game.players
            }
            game.started = True
            game.pending = set(game.players)
            game.turn = 0

            self._deal(game)

            await interaction.response.send_message(
                embed=embed(
                    "섯다 시작",
                    f"총 판돈: **{game.pot:,}** 코인\n"
                    "각 플레이어에게 자신의 패와 족보를 DM으로 전송합니다.\n"
                    f"현재 차례: <@{game.players[0]}>",
                )
            )

            await self._send_private_hands(game)

    @app_commands.command(
        name="섯다취소",
        description="대기 중인 섯다 방을 취소합니다.",
    )
    async def cancel(self, interaction: discord.Interaction) -> None:
        async with self.lock:
            channel_id = interaction.channel_id
            game = self.games.get(channel_id)

            if game is None:
                await interaction.response.send_message(
                    embed=embed(
                        "섯다 취소",
                        "취소할 섯다 방이 없습니다.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            if game.host != interaction.user.id:
                await interaction.response.send_message(
                    embed=embed(
                        "섯다 취소",
                        "섯다 방장만 취소할 수 있습니다.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            if game.started:
                await interaction.response.send_message(
                    embed=embed(
                        "섯다 취소",
                        "이미 시작된 게임은 취소할 수 없습니다.",
                        color=discord.Color.orange(),
                    ),
                    ephemeral=True,
                )
                return

            self.games.pop(channel_id, None)
            await interaction.response.send_message(
                embed=embed(
                    "섯다 방 취소",
                    f"{interaction.user.mention}님이 섯다 방을 취소했습니다.",
                )
            )

    @app_commands.command(
        name="내패",
        description="내 섯다 패를 확인합니다.",
    )
    async def hand(self, interaction: discord.Interaction) -> None:
        game = self.games.get(interaction.channel_id)
        cards = game.cards.get(interaction.user.id) if game else None

        if cards is None:
            await interaction.response.send_message(
                embed=embed(
                    "내 패",
                    "진행 중인 게임의 참가자가 아닙니다.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        hand = evaluate(cards)
        await interaction.response.send_message(
            embed=embed(
                "내 섯다 패",
                f"패: **{hand_text(cards)}**\n족보: **{hand.name}**",
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="베팅",
        description="내 차례에 콜, 따당, 다이를 선택합니다.",
    )
    @app_commands.choices(
        행동=[
            app_commands.Choice(name="콜", value="call"),
            app_commands.Choice(name="따당", value="raise"),
            app_commands.Choice(name="다이", value="die"),
        ]
    )
    async def bet(
        self,
        interaction: discord.Interaction,
        행동: app_commands.Choice[str],
    ) -> None:
        async with self.lock:
            game = self.games.get(interaction.channel_id)
            user_id = interaction.user.id

            if (
                game is None
                or not game.started
                or game.players[game.turn] != user_id
                or user_id in game.folded
            ):
                await interaction.response.send_message(
                    embed=embed(
                        "베팅",
                        "지금은 당신의 차례가 아닙니다.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            if 행동.value == "die":
                game.folded.add(user_id)
                game.pending.discard(user_id)

            else:
                target = game.current_bet * (
                    2 if 행동.value == "raise" else 1
                )
                due = target - game.paid[user_id]

                if Economy.balance(user_id) < due:
                    await interaction.response.send_message(
                        embed=embed(
                            "베팅",
                            "코인이 부족합니다.",
                            color=discord.Color.red(),
                        ),
                        ephemeral=True,
                    )
                    return

                Economy.change_balance(user_id, -due)
                game.paid[user_id] += due
                game.pot += due
                game.pending.discard(user_id)

                if 행동.value == "raise":
                    game.current_bet = target
                    game.pending = set(game.active()) - {user_id}

            if len(game.active()) == 1:
                winner = game.active()[0]
                Economy.change_balance(winner, game.pot)
                self.games.pop(interaction.channel_id, None)

                await interaction.response.send_message(
                    embed=embed(
                        "섯다 종료",
                        f"🏆 승자: <@{winner}>\n"
                        f"획득: **{game.pot:,}** 코인\n\n"
                        f"**전체 플레이어의 패**\n"
                        f"{self._all_hands_text(game)}",
                    )
                )
                return

            if not game.pending:
                replay_reason = self._replay_reason(game)

                if replay_reason:
                    self._deal(game)
                    game.pending = set(game.active())
                    game.turn = next(
                        index
                        for index, player in enumerate(game.players)
                        if player in game.pending
                    )

                    await interaction.response.send_message(
                        embed=embed(
                            "섯다 재경기",
                            f"{replay_reason}\n"
                            f"판돈 **{game.pot:,}** 코인은 유지됩니다.\n"
                            f"현재 차례: <@{game.players[game.turn]}>",
                        )
                    )
                    await self._send_private_hands(game)
                    return

                winner = self._winner(game)
                winning_hand: Hand = evaluate(game.cards[winner])
                Economy.change_balance(winner, game.pot)
                self.games.pop(interaction.channel_id, None)

                await interaction.response.send_message(
                    embed=embed(
                        "섯다 종료",
                        f"🏆 승자: <@{winner}> — **{winning_hand.name}**\n"
                        f"획득: **{game.pot:,}** 코인\n\n"
                        f"**전체 플레이어의 패**\n"
                        f"{self._all_hands_text(game)}",
                    )
                )
                return

            while True:
                game.turn = (game.turn + 1) % len(game.players)
                if game.players[game.turn] in game.pending:
                    break

            await interaction.response.send_message(
                embed=embed(
                    "베팅",
                    f"{행동.name}! 다음 차례: <@{game.players[game.turn]}>\n"
                    f"현재 판돈: **{game.pot:,}** 코인",
                )
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SeotdaCog(bot))

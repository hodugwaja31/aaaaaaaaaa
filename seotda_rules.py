import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Card:
    month: int
    bright: bool = False
    yeolkkeut: bool = False


@dataclass(frozen=True)
class Hand:
    rank: int
    name: str
    special: str | None = None


def deck() -> list[Card]:
    """원본과 동일한 월별 두 장 덱. 4월·9월의 첫 장은 열끗으로 표시한다."""
    return [
        Card(month, month in (1, 3, 8) and copy == 0, month in (4, 9) and copy == 0)
        for month in range(1, 11)
        for copy in range(2)
    ]


def evaluate(cards: list[Card]) -> Hand:
    a, b = sorted(cards, key=lambda card: card.month)
    months = (a.month, b.month)
    if months == (3, 8) and a.bright and b.bright:
        return Hand(100, "38광땡", "gwang")
    if months == (1, 8) and a.bright and b.bright:
        return Hand(99, "18광땡", "gwang")
    if months == (1, 3) and a.bright and b.bright:
        return Hand(98, "13광땡", "gwang")
    if a.month == b.month:
        return Hand(80 + a.month, f"{a.month}땡", "ddaeng")

    named_hands = {
        (1, 2): ("알리", 79), (1, 4): ("독사", 78), (1, 9): ("구삥", 77),
        (1, 10): ("장삥", 76), (4, 10): ("장사", 75), (4, 6): ("세륙", 74),
    }
    if months in named_hands:
        name, rank = named_hands[months]
        return Hand(rank, name)
    if months == (4, 9) and a.yeolkkeut and b.yeolkkeut:
        return Hand(73, "멍텅구리구사", "meong")
    if months == (4, 9):
        return Hand(72, "구사", "gusa")
    if months == (4, 7):
        return Hand(71, "암행어사", "secret")
    if months == (3, 7):
        return Hand(70, "땡잡이", "catcher")
    point = (a.month + b.month) % 10
    return Hand(60 + point, "갑오" if point == 9 else f"{point}끗")


def shuffled_deck() -> list[Card]:
    cards = deck()
    random.SystemRandom().shuffle(cards)
    return cards

#!/usr/bin/env python3
"""Offline blackjack PnL simulator.

This is a local educational simulator. It does not connect to, automate, or
interact with any gambling website.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K")
SUITS = ("S", "H", "D", "C")
CARD_VALUES = {
    "A": 11,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
}


@dataclass(frozen=True)
class Rules:
    decks: int = 6
    penetration: float = 0.75
    blackjack_payout: float = 1.5
    dealer_hits_soft_17: bool = False
    double_after_split: bool = True
    max_split_hands: int = 4
    no_resplit_aces: bool = True
    split_aces_one_card: bool = True


@dataclass
class FinishedHand:
    cards: list[str]
    bet_units: float
    actions: list[str]
    from_split_aces: bool = False


@dataclass
class RoundOutcome:
    round_number: int
    initial_running_count: int
    initial_true_count: float
    initial_decks_remaining: float
    player_hands: list[FinishedHand]
    dealer_cards: list[str]
    unit_pnl: float
    result: str
    blackjack: bool


@dataclass
class StrategyBankroll:
    name: str
    bankroll: float
    initial_bankroll: float
    hands_played: int = 0
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    blackjacks: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    high_watermark: float = 0.0
    busted: bool = False

    def __post_init__(self) -> None:
        self.high_watermark = self.bankroll

    def apply_result(self, bet: float, outcome: RoundOutcome) -> dict[str, object]:
        starting_bankroll = self.bankroll
        pnl = bet * outcome.unit_pnl
        self.bankroll += pnl
        self.total_pnl += pnl
        self.hands_played += 1

        if outcome.result == "win" or outcome.result == "blackjack":
            self.wins += 1
        elif outcome.result == "loss":
            self.losses += 1
        else:
            self.pushes += 1

        if outcome.blackjack:
            self.blackjacks += 1

        self.high_watermark = max(self.high_watermark, self.bankroll)
        self.max_drawdown = max(self.max_drawdown, self.high_watermark - self.bankroll)

        if self.bankroll <= 0:
            self.busted = True

        return {
            "hand_number": outcome.round_number,
            "strategy_name": self.name,
            "starting_bankroll": round(starting_bankroll, 6),
            "bet": round(bet, 6),
            "final_pnl": round(pnl, 6),
            "ending_bankroll": round(self.bankroll, 6),
            "result": "busted" if self.busted and self.bankroll <= 0 else outcome.result,
            "player_cards": format_player_hands(outcome.player_hands),
            "dealer_cards": " ".join(outcome.dealer_cards),
            "actions": format_actions(outcome.player_hands),
            "running_count": outcome.initial_running_count,
            "true_count": round(outcome.initial_true_count, 3),
            "decks_remaining_estimate": round(outcome.initial_decks_remaining, 3),
            "unit_pnl": round(outcome.unit_pnl, 6),
            "blackjack": outcome.blackjack,
        }


class Shoe:
    def __init__(self, rules: Rules, seed: int) -> None:
        self.rules = rules
        self.rng = random.Random(seed)
        self.cards: list[str] = []
        self.running_count = 0
        self.cards_dealt_since_shuffle = 0
        self.shuffle()

    @property
    def total_cards(self) -> int:
        return self.rules.decks * len(RANKS) * len(SUITS)

    @property
    def cut_card_cards_dealt(self) -> int:
        return int(self.total_cards * self.rules.penetration)

    def shuffle(self) -> None:
        self.cards = [
            f"{suit}{rank}"
            for _ in range(self.rules.decks)
            for suit in SUITS
            for rank in RANKS
        ]
        self.rng.shuffle(self.cards)
        self.running_count = 0
        self.cards_dealt_since_shuffle = 0

    def maybe_shuffle_before_round(self) -> None:
        if self.cards_dealt_since_shuffle >= self.cut_card_cards_dealt:
            self.shuffle()

    def draw(self) -> str:
        if not self.cards:
            self.shuffle()

        card = self.cards.pop()
        self.cards_dealt_since_shuffle += 1
        self.running_count += hilo_value(card)
        return card

    def decks_remaining(self) -> float:
        return max(len(self.cards) / 52.0, 0.25)

    def true_count(self) -> float:
        return self.running_count / self.decks_remaining()


def card_rank(card: str) -> str:
    return card[1:]


def card_value(card: str) -> int:
    return CARD_VALUES[card_rank(card)]


def hilo_value(card: str) -> int:
    rank = card_rank(card)
    if rank in {"2", "3", "4", "5", "6"}:
        return 1
    if rank in {"T", "J", "Q", "K", "A"}:
        return -1
    return 0


def hand_total(cards: Iterable[str]) -> tuple[int, bool]:
    total = 0
    aces = 0
    for card in cards:
        rank = card_rank(card)
        total += CARD_VALUES[rank]
        if rank == "A":
            aces += 1

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total, aces > 0


def is_blackjack(cards: list[str]) -> bool:
    total, _ = hand_total(cards)
    return len(cards) == 2 and total == 21


def is_bust(cards: list[str]) -> bool:
    total, _ = hand_total(cards)
    return total > 21


def pair_rank(cards: list[str]) -> str | None:
    if len(cards) != 2:
        return None
    left = card_rank(cards[0])
    right = card_rank(cards[1])
    if left == right:
        return left
    return None


def dealer_value(upcard: str) -> int:
    rank = card_rank(upcard)
    if rank == "A":
        return 11
    return CARD_VALUES[rank]


def basic_strategy_action(
    cards: list[str],
    dealer_upcard: str,
    *,
    can_double: bool,
    can_split: bool,
    rules: Rules,
) -> str:
    """Return hit, stand, double, or split using explicit S17 basic strategy."""

    up = dealer_value(dealer_upcard)
    pair = pair_rank(cards)

    if can_split and pair is not None:
        if pair == "A":
            return "split"
        elif pair == "T" or pair == "J" or pair == "Q" or pair == "K":
            return "stand"
        elif pair == "9":
            if up == 7:
                return "stand"
            elif up == 10:
                return "stand"
            elif up == 11:
                return "stand"
            else:
                return "split"
        elif pair == "8":
            return "split"
        elif pair == "7":
            if 2 <= up <= 7:
                return "split"
            else:
                return "hit"
        elif pair == "6":
            if 2 <= up <= 6:
                return "split"
            else:
                return "hit"
        elif pair == "5":
            if can_double and 2 <= up <= 9:
                return "double"
            else:
                return "hit"
        elif pair == "4":
            if rules.double_after_split and 5 <= up <= 6:
                return "split"
            else:
                return "hit"
        elif pair == "3":
            if 2 <= up <= 7:
                return "split"
            else:
                return "hit"
        elif pair == "2":
            if 2 <= up <= 7:
                return "split"
            else:
                return "hit"

    total, soft = hand_total(cards)

    if soft and total <= 21:
        if total >= 20:
            return "stand"
        elif total == 19:
            if can_double and up == 6:
                return "double"
            else:
                return "stand"
        elif total == 18:
            if can_double and 2 <= up <= 6:
                return "double"
            elif 7 <= up <= 8:
                return "stand"
            else:
                return "hit"
        elif total == 17:
            if can_double and 3 <= up <= 6:
                return "double"
            else:
                return "hit"
        elif total == 16:
            if can_double and 4 <= up <= 6:
                return "double"
            else:
                return "hit"
        elif total == 15:
            if can_double and 4 <= up <= 6:
                return "double"
            else:
                return "hit"
        elif total == 14:
            if can_double and 5 <= up <= 6:
                return "double"
            else:
                return "hit"
        elif total == 13:
            if can_double and 5 <= up <= 6:
                return "double"
            else:
                return "hit"
        else:
            return "hit"

    if total >= 17:
        return "stand"
    elif total == 16:
        if 2 <= up <= 6:
            return "stand"
        else:
            return "hit"
    elif total == 15:
        if 2 <= up <= 6:
            return "stand"
        else:
            return "hit"
    elif total == 14:
        if 2 <= up <= 6:
            return "stand"
        else:
            return "hit"
    elif total == 13:
        if 2 <= up <= 6:
            return "stand"
        else:
            return "hit"
    elif total == 12:
        if 4 <= up <= 6:
            return "stand"
        else:
            return "hit"
    elif total == 11:
        if can_double and 2 <= up <= 10:
            return "double"
        else:
            return "hit"
    elif total == 10:
        if can_double and 2 <= up <= 9:
            return "double"
        else:
            return "hit"
    elif total == 9:
        if can_double and 3 <= up <= 6:
            return "double"
        else:
            return "hit"
    else:
        return "hit"


def play_round(round_number: int, shoe: Shoe, rules: Rules) -> RoundOutcome:
    shoe.maybe_shuffle_before_round()
    initial_running_count = shoe.running_count
    initial_decks_remaining = shoe.decks_remaining()
    initial_true_count = shoe.true_count()

    player_cards = [shoe.draw(), shoe.draw()]
    dealer_cards = [shoe.draw(), shoe.draw()]
    dealer_upcard = dealer_cards[0]

    player_blackjack = is_blackjack(player_cards)
    dealer_blackjack = is_blackjack(dealer_cards)

    if player_blackjack or dealer_blackjack:
        hand = FinishedHand(player_cards, 1.0, ["blackjack"] if player_blackjack else ["stand"])
        if player_blackjack and dealer_blackjack:
            unit_pnl = 0.0
            result = "push"
        elif player_blackjack:
            unit_pnl = rules.blackjack_payout
            result = "blackjack"
        else:
            unit_pnl = -1.0
            result = "loss"

        return RoundOutcome(
            round_number=round_number,
            initial_running_count=initial_running_count,
            initial_true_count=initial_true_count,
            initial_decks_remaining=initial_decks_remaining,
            player_hands=[hand],
            dealer_cards=dealer_cards,
            unit_pnl=unit_pnl,
            result=result,
            blackjack=player_blackjack and not dealer_blackjack,
        )

    player_hands = play_player_hands(player_cards, dealer_upcard, shoe, rules)

    if any(not is_bust(hand.cards) for hand in player_hands):
        play_dealer_hand(dealer_cards, shoe, rules)

    unit_pnl = 0.0
    hand_results: list[str] = []
    dealer_total, _ = hand_total(dealer_cards)
    dealer_bust = dealer_total > 21

    for hand in player_hands:
        player_total, _ = hand_total(hand.cards)
        if player_total > 21:
            unit_pnl -= hand.bet_units
            hand_results.append("loss")
        elif dealer_bust:
            unit_pnl += hand.bet_units
            hand_results.append("win")
        elif player_total > dealer_total:
            unit_pnl += hand.bet_units
            hand_results.append("win")
        elif player_total < dealer_total:
            unit_pnl -= hand.bet_units
            hand_results.append("loss")
        else:
            hand_results.append("push")

    if unit_pnl > 0:
        result = "win"
    elif unit_pnl < 0:
        result = "loss"
    else:
        result = "push"

    for hand, hand_result in zip(player_hands, hand_results, strict=True):
        hand.actions.append(f"result:{hand_result}")

    return RoundOutcome(
        round_number=round_number,
        initial_running_count=initial_running_count,
        initial_true_count=initial_true_count,
        initial_decks_remaining=initial_decks_remaining,
        player_hands=player_hands,
        dealer_cards=dealer_cards,
        unit_pnl=unit_pnl,
        result=result,
        blackjack=False,
    )


def play_player_hands(
    initial_cards: list[str],
    dealer_upcard: str,
    shoe: Shoe,
    rules: Rules,
) -> list[FinishedHand]:
    queue: list[FinishedHand] = [FinishedHand(initial_cards, 1.0, [])]
    finished: list[FinishedHand] = []
    total_hands = 1

    while queue:
        hand = queue.pop(0)

        if hand.from_split_aces and rules.split_aces_one_card:
            hand.actions.append("stand")
            finished.append(hand)
            continue

        while True:
            total, _ = hand_total(hand.cards)
            if total > 21:
                hand.actions.append("bust")
                finished.append(hand)
                break

            split_rank = pair_rank(hand.cards)
            can_split = (
                split_rank is not None
                and total_hands < rules.max_split_hands
                and not (rules.no_resplit_aces and hand.from_split_aces)
            )
            can_double = len(hand.cards) == 2

            action = basic_strategy_action(
                hand.cards,
                dealer_upcard,
                can_double=can_double,
                can_split=can_split,
                rules=rules,
            )

            if action == "split" and can_split and split_rank is not None:
                hand.actions.append("split")
                first = FinishedHand(
                    [hand.cards[0], shoe.draw()],
                    hand.bet_units,
                    hand.actions.copy(),
                    from_split_aces=split_rank == "A",
                )
                second = FinishedHand(
                    [hand.cards[1], shoe.draw()],
                    hand.bet_units,
                    hand.actions.copy(),
                    from_split_aces=split_rank == "A",
                )
                total_hands += 1
                queue.insert(0, second)
                queue.insert(0, first)
                break

            if action == "double" and can_double:
                hand.actions.append("double")
                hand.bet_units *= 2.0
                hand.cards.append(shoe.draw())
                if is_bust(hand.cards):
                    hand.actions.append("bust")
                else:
                    hand.actions.append("stand")
                finished.append(hand)
                break

            if action == "stand":
                hand.actions.append("stand")
                finished.append(hand)
                break

            hand.actions.append("hit")
            hand.cards.append(shoe.draw())

    return finished


def play_dealer_hand(dealer_cards: list[str], shoe: Shoe, rules: Rules) -> None:
    while True:
        total, soft = hand_total(dealer_cards)
        if total < 17:
            dealer_cards.append(shoe.draw())
        elif total == 17 and soft and rules.dealer_hits_soft_17:
            dealer_cards.append(shoe.draw())
        else:
            return


def flat_bet(unit: float, _outcome: RoundOutcome) -> float:
    return unit


def hilo_bet(unit: float, outcome: RoundOutcome) -> float:
    true_count = math.floor(outcome.initial_true_count)
    if true_count < 2:
        units = 1
    elif true_count == 2:
        units = 2
    elif true_count == 3:
        units = 4
    elif true_count == 4:
        units = 8
    else:
        units = 12
    return unit * units


def format_player_hands(hands: list[FinishedHand]) -> str:
    return " | ".join(" ".join(hand.cards) for hand in hands)


def format_actions(hands: list[FinishedHand]) -> str:
    return " | ".join(
        f"H{index}:{','.join(hand.actions)}"
        for index, hand in enumerate(hands, start=1)
    )


def simulate(
    *,
    hands: int,
    seed: int,
    unit: float,
    bankroll: float,
    out_path: Path | None,
    rules: Rules,
) -> tuple[list[StrategyBankroll], list[dict[str, object]]]:
    shoe = Shoe(rules, seed)
    strategies = [
        StrategyBankroll("flat", bankroll, bankroll),
        StrategyBankroll("hilo", bankroll, bankroll),
    ]
    rows: list[dict[str, object]] = []

    for round_number in range(1, hands + 1):
        active = [strategy for strategy in strategies if not strategy.busted]
        if not active:
            break

        outcome = play_round(round_number, shoe, rules)

        for strategy in active:
            if strategy.name == "flat":
                bet = flat_bet(unit, outcome)
            elif strategy.name == "hilo":
                bet = hilo_bet(unit, outcome)
            else:
                raise ValueError(f"Unknown strategy {strategy.name}")

            row = strategy.apply_result(bet, outcome)
            rows.append(row)

    if out_path is not None:
        write_csv(out_path, rows)

    return strategies, rows


def write_csv(out_path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return

    with out_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_summary(strategies: list[StrategyBankroll]) -> None:
    headers = [
        "strategy",
        "hands",
        "wins",
        "losses",
        "pushes",
        "blackjacks",
        "win_rate",
        "total_pnl",
        "roi",
        "avg_pnl",
        "max_dd",
        "bankroll",
        "busted",
    ]
    rows = []
    for strategy in strategies:
        win_rate = strategy.wins / strategy.hands_played if strategy.hands_played else 0.0
        roi = strategy.total_pnl / strategy.initial_bankroll if strategy.initial_bankroll else 0.0
        avg_pnl = strategy.total_pnl / strategy.hands_played if strategy.hands_played else 0.0
        rows.append(
            [
                strategy.name,
                str(strategy.hands_played),
                str(strategy.wins),
                str(strategy.losses),
                str(strategy.pushes),
                str(strategy.blackjacks),
                f"{win_rate:.3%}",
                f"{strategy.total_pnl:.2f}",
                f"{roi:.3%}",
                f"{avg_pnl:.4f}",
                f"{strategy.max_drawdown:.2f}",
                f"{strategy.bankroll:.2f}",
                "yes" if strategy.busted else "no",
            ]
        )

    widths = [
        max(len(headers[column]), *(len(row[column]) for row in rows))
        for column in range(len(headers))
    ]

    print()
    print("Blackjack PnL summary")
    print(" ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print(" ".join("-" * width for width in widths))
    for row in rows:
        print(" ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local-only blackjack PnL simulator with flat and Hi-Lo betting.",
    )
    parser.add_argument("--hands", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--unit", type=float, default=1.0)
    parser.add_argument("--bankroll", type=float, default=10_000.0)
    parser.add_argument("--out", type=Path, default=Path("blackjack_results.csv"))
    parser.add_argument("--penetration", type=float, default=0.75)
    parser.add_argument("--no-csv", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.hands <= 0:
        raise SystemExit("--hands must be positive")
    if args.unit <= 0:
        raise SystemExit("--unit must be positive")
    if args.bankroll <= 0:
        raise SystemExit("--bankroll must be positive")
    if not 0 < args.penetration <= 1:
        raise SystemExit("--penetration must be between 0 and 1")

    rules = Rules(penetration=args.penetration)
    out_path = None if args.no_csv else args.out
    strategies, rows = simulate(
        hands=args.hands,
        seed=args.seed,
        unit=args.unit,
        bankroll=args.bankroll,
        out_path=out_path,
        rules=rules,
    )
    print_summary(strategies)
    if out_path is not None:
        print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()

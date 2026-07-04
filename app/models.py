from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal, Optional


def now() -> float:
    return time.time()


@dataclass
class Player:
    token: str
    name: str
    is_host: bool = False
    money: int = 0
    letters: list[str] = field(default_factory=list)
    score: int = 0
    connected_hint: float = field(default_factory=now)  # last poll timestamp

    def public(self, viewer_token: Optional[str]) -> dict:
        d = {
            "name": self.name,
            "is_host": self.is_host,
            "score": self.score,
            "money": self.money,
            "letter_count": len(self.letters),
        }
        if viewer_token == self.token:
            d["letters"] = sorted(self.letters)
        return d


@dataclass
class Auction:
    letters: list[str]
    remaining: list[str] = field(default_factory=list)
    bids: dict[str, int] = field(default_factory=dict)  # token -> amount (secret pre-reveal)
    revealed: bool = False
    pick_order: list[str] = field(default_factory=list)
    assigned: dict[str, str] = field(default_factory=dict)  # token -> letter picked
    turn_index: int = 0

    def __post_init__(self):
        if not self.remaining:
            self.remaining = list(self.letters)

    @property
    def done(self) -> bool:
        return self.revealed and self.turn_index >= len(self.pick_order)

    def current_picker(self) -> Optional[str]:
        if not self.revealed or self.done:
            return None
        return self.pick_order[self.turn_index]


@dataclass
class BidRound:
    kind: Literal["bid"] = "bid"
    auctions: list[Auction] = field(default_factory=list)
    money_deducted: bool = False
    resolved: bool = False
    submitted: set[str] = field(default_factory=set)

    @property
    def all_assigned(self) -> bool:
        return all(a.done for a in self.auctions)


@dataclass
class WordRound:
    kind: Literal["word"] = "word"
    category_id: int = 0
    category_name: str = ""
    submissions: dict[str, str] = field(default_factory=dict)  # token -> word (secret pre-reveal)
    resolved: bool = False
    results: dict[str, dict] = field(default_factory=dict)  # token -> {word, valid, points}


@dataclass
class GameSettings:
    num_auctions: int = 5
    starting_money: int = 100
    refill_amount: int = 20
    refill_interval: int = 5
    round_pattern: list[str] = field(default_factory=lambda: ["bid", "bid", "word"])
    pattern_repeat: int = 3
    category_ids: list[int] = field(default_factory=list)

    def build_round_sequence(self) -> list[str]:
        return (self.round_pattern * self.pattern_repeat)[: len(self.round_pattern) * self.pattern_repeat]


@dataclass
class Game:
    id: str
    settings: GameSettings
    players: dict[str, Player] = field(default_factory=dict)  # token -> Player
    player_order: list[str] = field(default_factory=list)
    status: Literal["lobby", "in_progress", "finished"] = "lobby"
    round_sequence: list[str] = field(default_factory=list)
    current_round_index: int = -1
    current_round: Optional[object] = None  # BidRound | WordRound
    round_history: list[dict] = field(default_factory=list)
    round_categories: dict[int, tuple[int, str]] = field(default_factory=dict)  # word round index -> (category_id, name)
    created_at: float = field(default_factory=now)

    @staticmethod
    def generate_id() -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "".join(random.choice(alphabet) for _ in range(6))

    @staticmethod
    def generate_token() -> str:
        return uuid.uuid4().hex

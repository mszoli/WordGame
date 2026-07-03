import asyncio

from app.models import Game


class GameStore:
    def __init__(self) -> None:
        self.games: dict[str, Game] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def add(self, game: Game) -> None:
        self.games[game.id] = game
        self._locks[game.id] = asyncio.Lock()

    def get(self, game_id: str) -> Game | None:
        return self.games.get(game_id.upper())

    def lock_for(self, game_id: str) -> asyncio.Lock:
        return self._locks[game_id.upper()]


store = GameStore()

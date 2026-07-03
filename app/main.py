from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db, game_logic
from app.models import Game, GameSettings, Player
from app.schemas import (
    AddWordsRequest,
    BidRequest,
    CreateCategoryRequest,
    CreateGameRequest,
    JoinGameRequest,
    PickLetterRequest,
    WordSubmitRequest,
)
from app.store import store

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Szókirakós Játék")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# ---------------------------------------------------------------------------
# Frontend page routes
# ---------------------------------------------------------------------------

@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
def serve_admin():
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/game")
def serve_game():
    return FileResponse(STATIC_DIR / "game.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Admin API: categories & word lists
# ---------------------------------------------------------------------------

@app.get("/api/categories")
def list_categories():
    return db.list_categories()


@app.post("/api/categories")
def create_category(req: CreateCategoryRequest):
    try:
        category_id = db.create_category(req.name)
    except Exception:
        raise HTTPException(status_code=400, detail="Ez a kategórianév már létezik.")
    return {"id": category_id, "name": req.name}


@app.delete("/api/categories/{category_id}")
def delete_category(category_id: int):
    db.delete_category(category_id)
    return {"ok": True}


@app.get("/api/categories/{category_id}/words")
def get_words(category_id: int):
    if not db.get_category(category_id):
        raise HTTPException(status_code=404, detail="Kategória nem található.")
    return {"words": db.get_words(category_id)}


@app.post("/api/categories/{category_id}/words")
def add_words(category_id: int, req: AddWordsRequest):
    if not db.get_category(category_id):
        raise HTTPException(status_code=404, detail="Kategória nem található.")
    added = db.add_words(category_id, req.words)
    return {"added": added}


# ---------------------------------------------------------------------------
# Game lifecycle
# ---------------------------------------------------------------------------

def _get_game_or_404(game_id: str) -> Game:
    game = store.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="A játék nem található.")
    return game


def _get_player_or_403(game: Game, token: str | None) -> Player:
    if not token or token not in game.players:
        raise HTTPException(status_code=403, detail="Érvénytelen vagy hiányzó játékos token.")
    return game.players[token]


@app.post("/api/games")
def create_game(req: CreateGameRequest):
    category_ids = req.category_ids or [c["id"] for c in db.list_categories()]
    settings = GameSettings(
        num_auctions=req.num_auctions,
        starting_money=req.starting_money,
        refill_amount=req.refill_amount,
        refill_interval=req.refill_interval,
        round_pattern=req.round_pattern,
        pattern_repeat=req.pattern_repeat,
        category_ids=category_ids,
    )

    game_id = Game.generate_id()
    while store.get(game_id):
        game_id = Game.generate_id()

    game = Game(id=game_id, settings=settings)
    host_token = Game.generate_token()
    host = Player(token=host_token, name=req.host_name.strip(), is_host=True)
    game.players[host_token] = host
    game.player_order.append(host_token)
    store.add(game)

    return {"game_id": game_id, "player_token": host_token}


@app.post("/api/games/{game_id}/join")
async def join_game(game_id: str, req: JoinGameRequest):
    game = _get_game_or_404(game_id)
    async with store.lock_for(game_id):
        if game.status != "lobby":
            raise HTTPException(status_code=400, detail="A játék már elindult, most nem lehet csatlakozni.")
        name = req.name.strip()
        if any(p.name.lower() == name.lower() for p in game.players.values()):
            raise HTTPException(status_code=400, detail="Ez a név már foglalt ebben a játékban.")
        token = Game.generate_token()
        player = Player(token=token, name=name)
        game.players[token] = player
        game.player_order.append(token)
    return {"game_id": game.id, "player_token": token}


@app.get("/api/games/{game_id}/state")
async def get_state(game_id: str, token: str | None = None):
    game = _get_game_or_404(game_id)
    async with store.lock_for(game_id):
        game_logic.tick(game)
        return game_logic.serialize_state(game, token)


@app.post("/api/games/{game_id}/start")
async def start_game(game_id: str, token: str):
    game = _get_game_or_404(game_id)
    player = _get_player_or_403(game, token)
    if not player.is_host:
        raise HTTPException(status_code=403, detail="Csak a házigazda indíthatja el a játékot.")
    async with store.lock_for(game_id):
        try:
            game_logic.start_game(game)
        except game_logic.GameError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.post("/api/games/{game_id}/force_end")
async def force_end(game_id: str, token: str):
    game = _get_game_or_404(game_id)
    player = _get_player_or_403(game, token)
    if not player.is_host:
        raise HTTPException(status_code=403, detail="Csak a házigazda zárhatja le a kört.")
    async with store.lock_for(game_id):
        game_logic.tick(game)
        try:
            game_logic.force_end_round(game)
        except game_logic.GameError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.post("/api/games/{game_id}/bid")
async def bid(game_id: str, token: str, req: BidRequest):
    game = _get_game_or_404(game_id)
    _get_player_or_403(game, token)
    async with store.lock_for(game_id):
        game_logic.tick(game)
        try:
            game_logic.submit_bid(game, token, req.bids)
        except game_logic.GameError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.post("/api/games/{game_id}/pick")
async def pick(game_id: str, token: str, req: PickLetterRequest):
    game = _get_game_or_404(game_id)
    _get_player_or_403(game, token)
    async with store.lock_for(game_id):
        game_logic.tick(game)
        try:
            game_logic.pick_letter(game, token, req.auction_index, req.letter)
        except game_logic.GameError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.post("/api/games/{game_id}/word")
async def word(game_id: str, token: str, req: WordSubmitRequest):
    game = _get_game_or_404(game_id)
    _get_player_or_403(game, token)
    async with store.lock_for(game_id):
        game_logic.tick(game)
        try:
            game_logic.submit_word(game, token, req.word)
        except game_logic.GameError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}

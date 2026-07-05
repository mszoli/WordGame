from __future__ import annotations

import random
from collections import Counter

from app import db
from app.letters import draw_letters
from app.models import Auction, BidRound, Game, Player, WordRound


class GameError(ValueError):
    pass


def add_bot(game: Game) -> str:
    if game.status != "lobby":
        raise GameError("Csak a váróteremben lehet botot hozzáadni.")
    existing_bots = sum(1 for p in game.players.values() if p.is_bot)
    name = f"Bot {existing_bots + 1}"
    token = Game.generate_token()
    game.players[token] = Player(token=token, name=name, is_bot=True)
    game.player_order.append(token)
    return token


def start_game(game: Game) -> None:
    if game.status != "lobby":
        raise GameError("A játék már elindult.")
    if len(game.player_order) < 2:
        raise GameError("Legalább 2 játékos szükséges az indításhoz.")
    game.round_sequence = game.settings.build_round_sequence()
    for token in game.player_order:
        game.players[token].money = game.settings.starting_money
    game.status = "in_progress"
    _assign_round_categories(game)
    setup_round(game, 0)


def _assign_round_categories(game: Game) -> None:
    """Minden szókirakó körhöz előre kisorsol egy kategóriát, hogy a teljes
    kör-sorrend előre látható legyen. A kategóriák a beállított sorrendben
    (settings.category_ids) ismétlődnek, nincs véletlen keverés."""
    cycle: list[int] = []
    for index, round_type in enumerate(game.round_sequence):
        if round_type != "word":
            continue
        if not cycle:
            cycle = list(game.settings.category_ids)
        if not cycle:
            game.round_categories[index] = (0, "Nincs kategória")
            continue
        cat_id = cycle.pop(0)
        cat = db.get_category(cat_id)
        game.round_categories[index] = (cat_id, cat["name"] if cat else "?")


def _round_schedule(game: Game) -> list[dict]:
    schedule = []
    for index, round_type in enumerate(game.round_sequence):
        if round_type == "word":
            schedule.append({"index": index, "type": "word", "category": game.round_categories.get(index, (0, "?"))[1]})
        else:
            schedule.append({"index": index, "type": "bid"})
    return schedule


def _last_word_result(game: Game) -> dict | None:
    for entry in reversed(game.round_history):
        if entry.get("type") == "word":
            return entry
    return None


def setup_round(game: Game, index: int) -> None:
    game.current_round_index = index
    if index > 0 and game.settings.refill_interval > 0 and index % game.settings.refill_interval == 0:
        for player in game.players.values():
            player.money += game.settings.refill_amount

    round_type = game.round_sequence[index]
    if round_type == "bid":
        n_players = len(game.player_order)
        auctions = [Auction(letters=draw_letters(n_players)) for _ in range(game.settings.num_auctions)]
        game.current_round = BidRound(auctions=auctions)
    else:
        cat_id, cat_name = game.round_categories.get(index, (0, "?"))
        game.current_round = WordRound(category_id=cat_id, category_name=cat_name)


def _finish_current_round(game: Game, history_entry: dict) -> None:
    history_entry["round_index"] = game.current_round_index
    game.round_history.append(history_entry)
    next_index = game.current_round_index + 1
    if next_index >= len(game.round_sequence):
        game.status = "finished"
        game.current_round = None
    else:
        setup_round(game, next_index)


def _reveal_bid_round(game: Game, br: BidRound) -> None:
    for auction in br.auctions:
        if auction.revealed:
            continue
        tokens = list(game.player_order)
        random.shuffle(tokens)
        tokens.sort(key=lambda t: -auction.bids.get(t, 0))
        auction.pick_order = tokens
        auction.revealed = True
        auction.turn_index = 0
    if not br.money_deducted:
        for token in game.player_order:
            spent = sum(a.bids.get(token, 0) for a in br.auctions)
            game.players[token].money -= spent
        br.money_deducted = True


def _assign_letter(game: Game, auction: Auction, token: str, letter: str) -> None:
    auction.remaining.remove(letter)
    auction.assigned[token] = letter
    game.players[token].letters.append(letter)
    auction.turn_index += 1


def _summarize_bid_round(game: Game, br: BidRound) -> dict:
    return {
        "auctions": [
            {
                "letters": a.letters,
                "bids": {game.players[t].name: amt for t, amt in a.bids.items()},
                "assigned": {game.players[t].name: letter for t, letter in a.assigned.items()},
            }
            for a in br.auctions
        ]
    }


def _tick_bid_round(game: Game, br: BidRound) -> None:
    if not all(a.revealed for a in br.auctions):
        if set(game.player_order) <= br.submitted:
            _reveal_bid_round(game, br)
    if br.money_deducted and br.all_assigned:
        _finish_current_round(game, {"type": "bid", **_summarize_bid_round(game, br)})


def can_form_word(letters: list[str], word: str) -> bool:
    available = Counter(letters)
    needed = Counter(word)
    return all(available[c] >= needed[c] for c in needed)


def consume_word_letters(letters: list[str], word: str) -> None:
    for ch in word:
        letters.remove(ch)


def _resolve_word_round(game: Game, wr: WordRound) -> None:
    valid_words = db.get_word_set(wr.category_id)
    for token in game.player_order:
        player = game.players[token]
        word = wr.submissions.get(token, "").strip().upper()
        if word and can_form_word(player.letters, word) and word in valid_words:
            consume_word_letters(player.letters, word)
            points = len(word) ** 2
            player.score += points
            wr.results[token] = {"word": word, "valid": True, "points": points}
        else:
            wr.results[token] = {"word": word, "valid": False, "points": 0}
    wr.resolved = True


def _tick_word_round(game: Game, wr: WordRound) -> None:
    if not wr.resolved:
        if game.player_order and set(game.player_order) <= set(wr.submissions.keys()):
            _resolve_word_round(game, wr)
    if wr.resolved:
        _finish_current_round(
            game,
            {
                "type": "word",
                "category": wr.category_name,
                "results": {game.players[t].name: r for t, r in wr.results.items()},
            },
        )


def _bot_bid_amounts(game: Game, br: BidRound, player: Player) -> dict[str, int]:
    remaining_bid_rounds = sum(
        1
        for i in range(game.current_round_index, len(game.round_sequence))
        if game.round_sequence[i] == "bid"
    )
    share = player.money / max(1, remaining_bid_rounds)
    budget = max(0, min(int(share * random.uniform(0.4, 1.3)), player.money))
    n = len(br.auctions)
    if n == 0 or budget == 0:
        return {str(i): 0 for i in range(n)}
    weights = [random.random() for _ in range(n)]
    total_weight = sum(weights)
    amounts = [int(budget * w / total_weight) for w in weights]
    while sum(amounts) > budget:
        amounts[amounts.index(max(amounts))] -= 1
    return {str(i): amounts[i] for i in range(n)}


def _run_bot_bids(game: Game, br: BidRound) -> None:
    if any(a.revealed for a in br.auctions):
        return
    for token in game.player_order:
        player = game.players[token]
        if not player.is_bot or token in br.submitted:
            continue
        submit_bid(game, token, _bot_bid_amounts(game, br, player))


def _run_bot_picks(game: Game, br: BidRound) -> None:
    for auction in br.auctions:
        if not auction.revealed:
            continue
        while not auction.done:
            picker = auction.current_picker()
            if picker is None or not game.players[picker].is_bot:
                break
            _assign_letter(game, auction, picker, random.choice(auction.remaining))


def _bot_choose_word(category_id: int, letters: list[str]) -> str:
    candidates = [w for w in db.get_words(category_id) if can_form_word(letters, w)]
    if not candidates:
        return ""
    best_len = max(len(w) for w in candidates)
    return random.choice([w for w in candidates if len(w) == best_len])


def _run_bot_words(game: Game, wr: WordRound) -> None:
    if wr.resolved:
        return
    for token in game.player_order:
        player = game.players[token]
        if not player.is_bot or token in wr.submissions:
            continue
        submit_word(game, token, _bot_choose_word(wr.category_id, player.letters))


def _run_bot_logic(game: Game) -> None:
    if game.status != "in_progress" or game.current_round is None:
        return
    round_ = game.current_round
    if isinstance(round_, BidRound):
        _run_bot_bids(game, round_)
        _run_bot_picks(game, round_)
    elif isinstance(round_, WordRound):
        _run_bot_words(game, round_)


def tick(game: Game) -> None:
    if game.status != "in_progress" or game.current_round is None:
        return
    _run_bot_logic(game)
    round_ = game.current_round
    if isinstance(round_, BidRound):
        _tick_bid_round(game, round_)
    elif isinstance(round_, WordRound):
        _tick_word_round(game, round_)
    _run_bot_logic(game)


def force_end_round(game: Game) -> None:
    """Admin/házigazda vezérlésű 'lejárt az idő' — nincs valódi visszaszámláló timer,
    a házigazda dönti el mikor záruljon le az aktuális fázis."""
    if game.status != "in_progress" or game.current_round is None:
        raise GameError("Nincs aktív kör.")
    round_ = game.current_round
    if isinstance(round_, BidRound):
        if not all(a.revealed for a in round_.auctions):
            _reveal_bid_round(game, round_)
        else:
            for auction in round_.auctions:
                while not auction.done:
                    token = auction.current_picker()
                    letter = random.choice(auction.remaining)
                    _assign_letter(game, auction, token, letter)
    elif isinstance(round_, WordRound):
        if not round_.resolved:
            _resolve_word_round(game, round_)
    tick(game)


def submit_bid(game: Game, token: str, bids: dict[str, int]) -> None:
    round_ = game.current_round
    if not isinstance(round_, BidRound) or any(a.revealed for a in round_.auctions):
        raise GameError("A licitkör már lezárult vagy nem aktív.")
    n = len(round_.auctions)
    player = game.players[token]
    amounts = []
    for i in range(n):
        raw = bids.get(str(i), bids.get(i, 0)) or 0
        try:
            amount = int(raw)
        except (TypeError, ValueError):
            amount = 0
        amounts.append(max(0, amount))
    if sum(amounts) > player.money:
        raise GameError("Nincs elég pénzed ehhez a licithez.")
    for i, amount in enumerate(amounts):
        round_.auctions[i].bids[token] = amount
    round_.submitted.add(token)


def pick_letter(game: Game, token: str, auction_index: int, letter: str) -> None:
    round_ = game.current_round
    if not isinstance(round_, BidRound):
        raise GameError("Most nincs aktív licitkör.")
    if auction_index < 0 or auction_index >= len(round_.auctions):
        raise GameError("Érvénytelen licit index.")
    auction = round_.auctions[auction_index]
    letter = letter.upper()
    if auction.current_picker() != token:
        raise GameError("Nem te vagy soron ebben a licitben.")
    if letter not in auction.remaining:
        raise GameError("Ez a betű már nincs a készletben.")
    _assign_letter(game, auction, token, letter)


def submit_word(game: Game, token: str, word: str) -> None:
    round_ = game.current_round
    if not isinstance(round_, WordRound) or round_.resolved:
        raise GameError("A szókirakó kör már lezárult vagy nem aktív.")
    round_.submissions[token] = word.strip().upper()


def serialize_state(game: Game, viewer_token: str | None) -> dict:
    players_public = [game.players[t].public(viewer_token) for t in game.player_order]
    me = game.players.get(viewer_token) if viewer_token else None
    data: dict = {
        "game_id": game.id,
        "status": game.status,
        "players": players_public,
        "you": (
            {
                "name": me.name,
                "is_host": me.is_host,
                "money": me.money,
                "score": me.score,
                "letters": sorted(me.letters),
            }
            if me
            else None
        ),
        "round_index": game.current_round_index,
        "total_rounds": len(game.round_sequence),
        "round_history": game.round_history[-5:],
        "round_schedule": _round_schedule(game) if game.round_sequence else None,
        "last_word_result": _last_word_result(game),
        "round": None,
    }

    round_ = game.current_round
    if isinstance(round_, BidRound):
        auctions_out = []
        for i, a in enumerate(round_.auctions):
            entry = {
                "index": i,
                "letters": a.letters,
                "revealed": a.revealed,
                "your_bid": a.bids.get(viewer_token),
            }
            if a.revealed:
                picker = a.current_picker()
                entry.update(
                    {
                        "bids": {game.players[t].name: amt for t, amt in a.bids.items()},
                        "pick_order": [game.players[t].name for t in a.pick_order],
                        "assigned": {game.players[t].name: letter for t, letter in a.assigned.items()},
                        "remaining": a.remaining,
                        "done": a.done,
                        "current_picker": game.players[picker].name if picker else None,
                        "is_your_turn": picker == viewer_token,
                    }
                )
            auctions_out.append(entry)
        all_revealed = all(a.revealed for a in round_.auctions)
        data["round"] = {
            "type": "bid",
            "auctions": auctions_out,
            "revealed": all_revealed,
            "submitted": viewer_token in round_.submitted,
            "submitted_count": len(round_.submitted),
            "total_players": len(game.player_order),
        }
    elif isinstance(round_, WordRound):
        data["round"] = {
            "type": "word",
            "category_name": round_.category_name,
            "your_submission": round_.submissions.get(viewer_token) if viewer_token else None,
            "submitted_count": len(round_.submissions),
            "total_players": len(game.player_order),
            "resolved": round_.resolved,
            "results": (
                {game.players[t].name: r for t, r in round_.results.items()} if round_.resolved else None
            ),
        }

    return data

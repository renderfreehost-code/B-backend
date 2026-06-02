"""
Educational demo game engines.

These engines are intentionally demo-coin only. They do not connect to real-money
payments, withdrawals, odds providers, or casino services. The existing API flow
stays the same: game_id + amount -> result -> payout -> balance update.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any

ENGINE_VERSION = "separate-demo-engines-v3.0"


def _roll(max_exclusive: int) -> int:
    return secrets.randbelow(max_exclusive)


def _roll_1_100() -> int:
    return _roll(100) + 1


def _float_between(min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return round(min_value, 2)
    step = _roll(10001) / 10000
    return round(min_value + ((max_value - min_value) * step), 2)


def _clamp_multiplier(value: float, game: dict[str, Any]) -> float:
    low = float(game.get("payout_min") or 1.0)
    high = float(game.get("payout_max") or low)
    return round(max(low, min(high, value)), 2)


def _fairness_hash(slug: str, roll: int, multiplier: float, amount: int) -> str:
    salt = secrets.token_hex(8)
    raw = f"{ENGINE_VERSION}|{slug}|{roll}|{multiplier}|{amount}|{salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass
class EngineResult:
    result: str
    payout: int
    multiplier: float
    rng_roll: int
    engine_name: str
    engine_type: str
    details: dict[str, Any]

    @property
    def win(self) -> bool:
        return self.result == "win"


def _base_win(game: dict[str, Any]) -> tuple[int, bool]:
    roll = _roll_1_100()
    chance = int(game.get("win_chance") or 45)
    return roll, roll <= chance


def _finish(game: dict[str, Any], amount: int, win: bool, multiplier: float, roll: int, engine_name: str, engine_type: str, details: dict[str, Any]) -> EngineResult:
    if not win:
        multiplier = 0
    multiplier = round(float(multiplier), 2)
    payout = int(amount * multiplier) if win else 0
    details.update({
        "demo_only": True,
        "engine_version": ENGINE_VERSION,
        "fairness_hash": _fairness_hash(str(game.get("slug", "game")), roll, multiplier, amount),
        "educational_note": "Demo coins only. No real money, no withdrawal, no external odds feed.",
    })
    return EngineResult("win" if win else "loss", payout, multiplier, roll, engine_name, engine_type, details)


# 1) Crash-style engine: produces a demo crash point and checks whether user survived.
def crash_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    target_cashout = _float_between(float(game["payout_min"]), float(game["payout_max"]))
    crash_point = _float_between(1.01, float(game["payout_max"]) + 0.75)
    win = win and crash_point >= target_cashout
    multiplier = target_cashout if win else 0
    return _finish(game, amount, win, multiplier, roll, "Crash Flight Engine", "crash", {
        "target_cashout_x": target_cashout,
        "demo_crash_point_x": round(crash_point, 2),
        "phase": "takeoff-flight-cashout",
    })


# 2) Dice / number prediction engine.
def dice_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    dice = [_roll(6) + 1, _roll(6) + 1]
    total = sum(dice)
    multiplier = _float_between(float(game["payout_min"]), float(game["payout_max"])) if win else 0
    return _finish(game, amount, win, multiplier, roll, "Dice Number Engine", "number", {
        "dice": dice,
        "total": total,
        "prediction_mode": "demo-over-under",
    })


# 3) Mines grid reveal engine.
def mines_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    grid_size = 25
    mine_count = 3 + _roll(5)
    safe_reveals = 2 + _roll(6)
    multiplier = _clamp_multiplier(1 + safe_reveals * 0.22 + mine_count * 0.08, game) if win else 0
    return _finish(game, amount, win, multiplier, roll, "Mines Grid Engine", "mines", {
        "grid_size": grid_size,
        "mine_count": mine_count,
        "safe_reveals": safe_reveals if win else max(0, safe_reveals - 1),
        "hit_mine": not win,
    })


# 4) Plinko peg-drop engine.
def plinko_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    rows = 8 + _roll(5)
    bucket = _roll(rows + 1)
    edge_bonus = abs(bucket - rows / 2) / max(rows / 2, 1)
    multiplier = _clamp_multiplier(float(game["payout_min"]) + edge_bonus * (float(game["payout_max"]) - float(game["payout_min"])), game) if win else 0
    return _finish(game, amount, win, multiplier, roll, "Plinko Drop Engine", "plinko", {
        "rows": rows,
        "bucket": bucket,
        "edge_bonus": round(edge_bonus, 2),
    })


# 5) Roulette wheel engine.
def roulette_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    number = _roll(37)
    color = "green" if number == 0 else ("red" if number % 2 else "black")
    multiplier = _float_between(float(game["payout_min"]), float(game["payout_max"])) if win else 0
    return _finish(game, amount, win, multiplier, roll, "Roulette Wheel Engine", "roulette", {
        "number": number,
        "color": color,
        "bet_style": "demo-color/number mix",
    })


# 6) Blackjack/card duel engine.
def blackjack_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    player_total = 16 + _roll(6) if win else 12 + _roll(10)
    dealer_total = 17 + _roll(5)
    if player_total > 21:
        win = False
    elif dealer_total > 21:
        win = True
    elif player_total <= 21 and player_total > dealer_total:
        win = True
    multiplier = _clamp_multiplier(1.5 + (_roll(80) / 100), game) if win else 0
    return _finish(game, amount, win, multiplier, roll, "Blackjack Hand Engine", "blackjack", {
        "player_total": player_total,
        "dealer_total": dealer_total,
        "hand_mode": "demo totals, no real card deck",
    })


# 7) Poker-style hand rank engine.
def poker_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    ranks = ["high_card", "pair", "two_pair", "three_kind", "straight", "flush", "full_house"]
    rank = ranks[min(len(ranks) - 1, _roll(len(ranks)))]
    rank_boost = ranks.index(rank) * 0.18
    multiplier = _clamp_multiplier(float(game["payout_min"]) + rank_boost, game) if win else 0
    return _finish(game, amount, win, multiplier, roll, "Poker Rank Engine", "cards", {
        "hand_rank": rank,
        "showdown": "demo rank comparison",
    })


# 8) Slot reel engine.
def slot_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    symbols = ["7", "BAR", "STAR", "GEM", "BELL", "CHERRY"]
    reels = [symbols[_roll(len(symbols))] for _ in range(3)]
    if win:
        # keep the visual result consistent with a win sometimes
        if _roll(100) < 65:
            reels = [reels[0], reels[0], reels[0]]
        multiplier = _float_between(float(game["payout_min"]), float(game["payout_max"]))
    else:
        multiplier = 0
    return _finish(game, amount, win, multiplier, roll, "Slot Reels Engine", "slots", {
        "reels": reels,
        "payline": "center-line-demo",
    })


# 9) Sports match simulator.
def sports_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    home = _roll(5)
    away = _roll(5)
    if home == away:
        home += 1 if win else 0
    multiplier = _float_between(float(game["payout_min"]), float(game["payout_max"])) if win else 0
    return _finish(game, amount, win, multiplier, roll, "Sports Match Engine", "sports", {
        "score": {"home": home, "away": away},
        "market": "demo match outcome",
    })


# 10) Live-casino presenter style engine.
def live_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    round_no = secrets.token_hex(3).upper()
    multiplier = _float_between(float(game["payout_min"]), float(game["payout_max"])) if win else 0
    return _finish(game, amount, win, multiplier, roll, "Live Table Demo Engine", "live-casino", {
        "demo_round": round_no,
        "dealer_state": "virtual-host-demo",
    })


# 11) Arcade mini-game engine.
def arcade_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    score = 300 + _roll(9700)
    combo = 1 + _roll(8)
    multiplier = _clamp_multiplier(float(game["payout_min"]) + combo * 0.12, game) if win else 0
    return _finish(game, amount, win, multiplier, roll, "Arcade Score Engine", "arcade", {
        "score": score,
        "combo": combo,
        "mode": "demo skill-score simulation",
    })


# 12) Fallback for any game not mapped.
def generic_engine(game: dict[str, Any], amount: int) -> EngineResult:
    roll, win = _base_win(game)
    multiplier = _float_between(float(game["payout_min"]), float(game["payout_max"])) if win else 0
    return _finish(game, amount, win, multiplier, roll, "Generic Demo Engine", "generic", {
        "mode": "fallback win-chance multiplier simulator",
    })


SLUG_ENGINE_MAP = {
    "aviator": crash_engine,
    "rocket-crash": crash_engine,
    "space-crash": crash_engine,
    "jetx": crash_engine,
    "balloon-crash": crash_engine,
    "multiplier-rush": crash_engine,
    "cash-rocket": crash_engine,
    "turbo-plane": crash_engine,
    "crash-x": crash_engine,
    "galaxy-flight": crash_engine,
    "dice": dice_engine,
    "lucky-number": dice_engine,
    "goal": dice_engine,
    "limbo": dice_engine,
    "coin-flip": dice_engine,
    "hi-lo": dice_engine,
    "hilo-cards": dice_engine,
    "wheel": roulette_engine,
    "mines": mines_engine,
    "tower": mines_engine,
    "keno": dice_engine,
    "plinko": plinko_engine,
    "roulette": roulette_engine,
    "european-roulette": roulette_engine,
    "american-roulette": roulette_engine,
    "sic-bo": dice_engine,
    "craps": dice_engine,
    "blackjack": blackjack_engine,
    "baccarat": blackjack_engine,
    "dragon-tiger": blackjack_engine,
    "andar-bahar": blackjack_engine,
    "teen-patti": poker_engine,
    "casino-holdem": poker_engine,
    "poker": poker_engine,
    "texas-poker": poker_engine,
    "omaha-poker": poker_engine,
    "three-card-poker": poker_engine,
    "red-dog": poker_engine,
    "war-card": blackjack_engine,
    "rummy": poker_engine,
    "bridge-mock": poker_engine,
    "live-roulette": live_engine,
    "live-blackjack": live_engine,
    "live-baccarat": live_engine,
    "live-wheel": live_engine,
    "live-dragon-tiger": live_engine,
    "live-game-show": live_engine,
    "live-sic-bo": live_engine,
    "live-andar-bahar": live_engine,
    "live-teen-patti": live_engine,
    "live-poker": live_engine,
    "penalty-shootout": arcade_engine,
    "penalty-duel": arcade_engine,
    "scratch-card": arcade_engine,
    "spin-wheel": arcade_engine,
    "lucky-box": arcade_engine,
    "treasure-box": arcade_engine,
    "fishing-demo": arcade_engine,
    "race-demo": arcade_engine,
}


def select_engine(game: dict[str, Any]):
    slug = str(game.get("slug") or "").lower()
    category = str(game.get("category") or "").lower()
    if slug in SLUG_ENGINE_MAP:
        return SLUG_ENGINE_MAP[slug]
    if category == "slots":
        return slot_engine
    if category == "sports":
        return sports_engine
    if category == "crash":
        return crash_engine
    if category == "casino":
        return roulette_engine
    if category == "cards":
        return poker_engine
    if category == "live casino":
        return live_engine
    if category == "arcade":
        return arcade_engine
    if category == "number":
        return dice_engine
    return generic_engine


def calculate_demo_game_result(game: dict[str, Any], amount: int) -> EngineResult:
    engine = select_engine(game)
    return engine(game, amount)

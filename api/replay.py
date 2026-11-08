"""Stream a finished game play by play over a WebSocket.

Pacing follows the game clock: at 1x a play that happened 20 game seconds
after the last one arrives 20 seconds later; at 60x, a third of a second.
Plays on the same clock tick (fouls, free throws) still get a short beat.

Client -> server commands (JSON):
    {"cmd": "pause"} | {"cmd": "play"} | {"cmd": "speed", "speed": 60} | {"cmd": "restart"}
    {"cmd": "seek", "i": 120}   (jump to play 120; ?start=120 on connect does the same)

Server -> client messages:
    {"type": "init", "mode": "replay", "game": {...}, "total": N, "speed": S}
    {"type": "play", i, period, clock, elapsed, home_score, away_score, side,
     description, prob, delta}
    {"type": "state", "paused": bool, "speed": S}
    {"type": "reset"}            (after restart)
    {"type": "seek", "i": N, "plays": [...]}   (after a seek: every play before N)
    {"type": "end"}
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import WebSocket, WebSocketDisconnect

from api import settings


def gap_seconds(prev: dict, nxt: dict, speed: float) -> float:
    game_gap = max(nxt["elapsed"] - prev["elapsed"], settings.REPLAY_MIN_GAP_GAME_SECONDS)
    return min(game_gap / speed, settings.REPLAY_MAX_GAP_WALL_SECONDS)


def valid_speed(raw) -> float | None:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    return v if 0.25 <= v <= 600 else None


async def stream_replay(ws: WebSocket, game: dict, plays: list[dict], speed: float, start: int = 0) -> None:
    state = {"i": 0, "speed": speed, "paused": False}
    running = asyncio.Event()
    running.set()
    wake = asyncio.Event()  # interrupts the inter-play sleep

    async def send_state():
        await ws.send_json({"type": "state", "paused": state["paused"], "speed": state["speed"]})

    async def seek(raw) -> bool:
        try:
            i = min(max(int(raw), 0), len(plays))
        except (TypeError, ValueError):
            return False
        state["i"] = i
        await ws.send_json({"type": "seek", "i": i, "plays": plays[:i]})
        return True

    async def reader():
        while True:
            msg = await ws.receive_json()
            cmd = msg.get("cmd") if isinstance(msg, dict) else None
            if cmd == "pause":
                state["paused"] = True
                running.clear()
            elif cmd in ("play", "resume"):
                state["paused"] = False
                running.set()
            elif cmd == "speed" and (v := valid_speed(msg.get("speed"))):
                state["speed"] = v
            elif cmd == "restart":
                state["i"] = 0
                await ws.send_json({"type": "reset"})
            elif cmd == "seek" and await seek(msg.get("i")):
                pass
            else:
                continue
            wake.set()
            await send_state()

    await ws.send_json({"type": "init", "mode": "replay", "game": game, "total": len(plays), "speed": speed})
    if start > 0:
        await seek(start)
    reader_task = asyncio.create_task(reader())
    try:
        while True:
            if state["i"] >= len(plays):
                await ws.send_json({"type": "end"})
                # Stay open for a restart until the client goes away.
                while state["i"] >= len(plays):
                    wake.clear()
                    await _wait_any(wake.wait(), reader_task)
                    if reader_task.done():
                        return
                continue

            await _wait_any(running.wait(), reader_task)
            if reader_task.done():
                return
            i = state["i"]
            await ws.send_json({"type": "play", **plays[i]})
            state["i"] = i + 1
            if state["i"] < len(plays):
                wake.clear()
                delay = gap_seconds(plays[i], plays[i + 1], state["speed"])
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(_wait_any(wake.wait(), reader_task), timeout=delay)
                if reader_task.done():
                    return
    except (WebSocketDisconnect, RuntimeError):
        return
    finally:
        reader_task.cancel()


async def _wait_any(coro, task: asyncio.Task) -> None:
    waiter = asyncio.ensure_future(coro)
    try:
        await asyncio.wait({waiter, task}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        if not waiter.done():
            waiter.cancel()

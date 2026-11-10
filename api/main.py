"""Clutch API: ``uvicorn api.main:app``.

GET  /health                         status, data source, model, live feed health
GET  /meta                           seasons and teams for the search filters
GET  /model                          how the serving model was trained and how it scored on the test season
GET  /games/today                    tonight's games with status, score, probability
GET  /games?team=TOR&season=2025-26  past games for replay (also q, date, sort, paging)
GET  /games/{id}                     one game's summary
GET  /games/{id}/series              full probability series for a finished game
WS   /games/{id}/replay?speed=10     streams a finished game play by play
WS   /games/{id}/live                pushes each new play's probability during a live game

Replay is served entirely from precomputed files; it never calls the NBA site.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api import settings
from api.live import LiveHub, make_source
from api.modelcard import build_card
from api.replay import stream_replay, valid_speed
from api.security import Guard
from api.store import GameStore

log = logging.getLogger("api")


def _load_model():
    from model.predict import load_meta, load_model

    try:
        meta = load_meta(settings.ARTIFACTS_DIR)
        return load_model(meta["production"], str(settings.ARTIFACTS_DIR))
    except FileNotFoundError:
        log.warning("no trained model at %s; live mode disabled", settings.ARTIFACTS_DIR)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    store = GameStore()
    model = _load_model()
    app.state.store = store
    app.state.model = model
    app.state.card = build_card(settings.ARTIFACTS_DIR, settings.REPORTS_DIR)
    app.state.hub = LiveHub(make_source(store) if model else None, store, model)
    log.info(
        "ready: %d games (%s data), model=%s, live=%s",
        len(store.games),
        settings.data_source(),
        model.name if model else None,
        settings.LIVE_SOURCE,
    )
    yield


# The interactive API docs are off unless CLUTCH_DOCS=1 (make api turns them on locally).
docs = settings.DOCS
app = FastAPI(
    title="Clutch",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if docs else None,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.add_middleware(Guard)  # added last = runs first: rate limits, stream caps, security headers

# NBA game IDs are 10 digits; simulated live games add a FAKE prefix.
GameId = Annotated[str, Path(max_length=24, pattern=r"^[A-Za-z0-9]+$")]


def store() -> GameStore:
    return app.state.store


def hub() -> LiveHub:
    return app.state.hub


@app.get("/health")
async def health():
    model = app.state.model
    return {
        "status": "ok",
        "data_source": settings.data_source(),
        "games": int(len(store().games)),
        "model": model.name if model else None,
        "live_source": settings.LIVE_SOURCE,
        "live_ok": hub().live_ok,
        "live_error": (hub().last_error or "")[:200] or None,
    }


@app.get("/meta")
async def meta():
    return {"seasons": store().seasons(), "teams": store().teams(), "data_source": settings.data_source()}


@app.get("/model")
async def model_card():
    if app.state.card is None:
        raise HTTPException(404, "no trained model")
    return app.state.card


@app.get("/games/today")
async def games_today():
    games = await hub().scoreboard()
    return {"games": games, "live_ok": hub().live_ok, "data_source": settings.data_source()}


@app.get("/games")
async def games(
    team: str | None = Query(None, max_length=3),
    season: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    q: str | None = Query(None, max_length=80),
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    sort: str = Query("date", pattern="^(date|swing|close)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    total, rows = store().search(team=team, season=season, q=q, date=date, sort=sort, limit=limit, offset=offset)
    return {"total": total, "games": rows, "limit": limit, "offset": offset}


@app.get("/games/{game_id}")
async def game(game_id: GameId):
    g = store().game(game_id)
    if g is not None:
        return g | {"replay_available": True}
    live = await hub().find(game_id)
    if live is not None:
        return live
    raise HTTPException(404, "game not found")


@app.get("/games/{game_id}/series")
async def series(game_id: GameId):
    data = store().series(game_id)
    if data is None:
        raise HTTPException(404, "no series for this game")
    return data


@app.websocket("/games/{game_id}/replay")
async def replay(ws: WebSocket, game_id: GameId, speed: float = 10, start: Annotated[int, Query(ge=0, le=5000)] = 0):
    await ws.accept()
    data = store().series(game_id)
    if data is None:
        await ws.send_json({"type": "error", "message": "no series for this game"})
        await ws.close(code=4404)
        return
    await stream_replay(ws, data["game"], data["plays"], valid_speed(speed) or 10, start=start)


@app.websocket("/games/{game_id}/live")
async def live(ws: WebSocket, game_id: GameId):
    await ws.accept()
    sub = await hub().subscribe(game_id)
    if sub is None:
        await ws.send_json({"type": "error", "message": "game is not on today's live scoreboard"})
        await ws.close(code=4404)
        return
    lg, queue = sub
    try:
        if not lg.plays:
            await hub().poll_once(lg)
            while not queue.empty():  # history goes out in the init message instead
                queue.get_nowait()
        # (afterwards the queue carries play / reset / status / heartbeat messages)
        await ws.send_json(
            {"type": "init", "mode": "live", "game": lg.info, "plays": lg.plays, "final": lg.final}
        )
        while True:
            get = asyncio.create_task(queue.get())
            recv = asyncio.create_task(ws.receive_text())
            done, pending = await asyncio.wait({get, recv}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            if recv in done:
                recv.result()  # raises WebSocketDisconnect when the client leaves
                continue
            await ws.send_json(get.result())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub().unsubscribe(lg, queue)

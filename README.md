# Clutch

Clutch predicts which NBA team wins from any moment in a game and shows it as a
live chart that moves with every play, with a replay mode for finished games.

> A score alone doesn't tell you how safe a lead is. Up 8 with 2 minutes left
> and up 8 at halftime are very different situations. Win probability puts a
> number on it.

Clutch is a sports analytics project. It does not show odds and has nothing to
do with betting.

## Layout

| Folder | What lives there |
| --- | --- |
| `pipeline/` | Pulls play-by-play with `nba_api`, builds one feature row per play, writes Parquet. Runs locally only. |
| `model/` | Trains logistic regression, XGBoost and a PyTorch MLP; writes the evaluation report; exposes `predict(state)`. |
| `api/` | FastAPI app. Serves precomputed probability series and streams replays and live games over WebSockets. |
| `web/` | React + Vite + Recharts front end: games list and game page. |
| `docs/` | Build log, open questions, blockers. |

## Status

Work in progress. See [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) for what was
built when.

# Security

Clutch serves public, read-only data (NBA play-by-play and the model's
probabilities). There are no accounts, no cookies, no forms and no database,
so there is nothing private to leak and nothing to write to. What's left to
guard against is being flooded, being used as someone else's backend, and
browsers being tricked into framing or misreading the site.

## Checked (2026-11-10)

| Check | Result |
| --- | --- |
| Secrets (keys, tokens, passwords) in files and in every commit | None |
| `.env` files ever committed | Only `web/.env.example` (no secrets) |
| Email address on commits | All 151 use the GitHub noreply address |
| Personal email in tracked files | Removed from `docs/BLOCKERS.md`; still in that file's older versions in git history (repo is private) |
| Python dependencies of the deployed API (`pip-audit -r requirements-api.txt`) | No known vulnerabilities |
| Website dependencies (`npm audit`) | 0 after upgrading React Router 6 → 7.18.4 (two moderate advisories, neither reachable here) |
| Raw HTML / `eval` in the website | None |
| Search input | Matched as plain text, not a regular expression |

## API (`api/security.py`, `api/main.py`, `render.yaml`)

* **Rate limit:** 300 requests and stream opens per visitor per minute (`CLUTCH_RATE_LIMIT`); over it, 429.
* **Streams:** at most 8 open replay/live streams per visitor and 200 overall (`CLUTCH_WS_MAX_PER_VISITOR`, `CLUTCH_WS_MAX`); client messages capped at 64 KB.
* **Origins:** with `CLUTCH_CORS_ORIGINS` set to the site's address, browsers on other sites can't call the API or open its streams. Unset, any origin may read it (it's public data), so **set it on Render**.
* **Input:** game IDs must be letters and digits, at most 24; every query parameter has a type, range or pattern.
* **Headers on every response:** `nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'`, HSTS, no referrer, no server banner.
* **No API docs in production:** `/docs` and `/openapi.json` only exist when `CLUTCH_DOCS=1` (`make api` sets it locally).
* **Errors** return a short message, never a stack trace; `/health` trims the live feed's last error to 200 characters.

## Website (`web/security-headers.json`, sent by Render)

* **Content Security Policy:** scripts only from the site itself; styles from the site and Google Fonts; images from the site and the NBA's logo CDN; network calls only to the site and `*.onrender.com`. Give the API a custom domain and add it to `connect-src`.
* `X-Frame-Options: DENY`, `nosniff`, a strict referrer policy, HSTS, and camera, microphone, location, payment and USB turned off.
* `npm run preview` serves the build with the same headers (plus the local API), so a policy problem shows up before deploying. `tests/test_deploy_config.py` keeps `render.yaml` and the JSON file in step.

## Not covered

* The free Render instance can still be slowed by a determined flood from many addresses; Render's own edge handles the worst of it.
* Team logos load from the NBA's CDN; if it ever refuses them, the site shows each team's two-tone swatch instead.

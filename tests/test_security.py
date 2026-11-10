"""The public API's guard: headers, limits, stream caps, input checks, no docs in production."""

import pytest
from starlette.websockets import WebSocketDisconnect


def test_security_headers_on_every_response(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert "server" not in {k.lower() for k in r.headers} or "uvicorn" not in r.headers.get("server", "")


def test_docs_are_off_by_default(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_game_ids_are_checked(client):
    assert client.get("/games/abc$def").status_code == 422
    assert client.get("/games/" + "1" * 40).status_code == 422
    assert client.get("/games/T0000/series").status_code == 200


def test_rate_limit_per_visitor(client, monkeypatch):
    from api import security

    monkeypatch.setattr(security, "RATE_LIMIT", 3)
    me, other = {"x-forwarded-for": "203.0.113.7"}, {"x-forwarded-for": "198.51.100.2"}
    codes = [client.get("/meta", headers=me).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert client.get("/meta", headers=other).status_code == 200  # someone else isn't affected


def test_streams_only_from_the_site_once_its_address_is_set(client, monkeypatch):
    from api import settings

    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://clutch-web.onrender.com"])
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/games/T0000/replay?speed=60", headers={"origin": "https://evil.example"}):
            pass
    with client.websocket_connect("/games/T0000/replay?speed=60",
                                  headers={"origin": "https://clutch-web.onrender.com"}) as ws:  # fmt: skip
        assert ws.receive_json()["type"] in ("init", "state")


def test_open_streams_capped_per_visitor(client, monkeypatch):
    from api import security

    monkeypatch.setattr(security, "WS_MAX_PER_VISITOR", 1)
    who = {"x-forwarded-for": "192.0.2.44"}
    with client.websocket_connect("/games/T0000/replay?speed=60", headers=who) as first:
        first.receive_json()
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/games/T0000/replay?speed=60", headers=who):
                pass

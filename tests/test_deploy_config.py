"""render.yaml stays in line with what the code expects."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def services():
    return {s["name"]: s for s in yaml.safe_load((ROOT / "render.yaml").read_text())["services"]}


def test_site_sends_the_security_headers():
    want = json.loads((ROOT / "web" / "security-headers.json").read_text())
    sent = {h["name"]: h["value"] for h in services()["clutch-web"]["headers"] if h["path"] == "/*"}
    assert sent == want


def test_api_runs_without_reload_docs_or_banner():
    api = services()["clutch-api"]
    cmd = api["startCommand"]
    assert "--reload" not in cmd and "--no-server-header" in cmd and "--ws-max-size" in cmd
    env = {e["key"]: e for e in api["envVars"]}
    assert "CLUTCH_DOCS" not in env  # API docs stay off in production
    assert env["CLUTCH_API_DATA"]["value"] == "api/data"

"""Screenshot a page in headless Google Chrome after a real-time wait (so charts and fonts finish).

    .venv/bin/python -m scripts.screenshot file:///path/page.html out.png [--wait 4] [--width 1280] [--height 4300]
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

LOUD = ("error", "warning")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9333


async def _shoot(url: str, out: Path, wait: float, width: int, height: int) -> list[str]:
    import websockets

    chrome = shutil.which("google-chrome") or shutil.which("chromium") or CHROME
    profile = tempfile.mkdtemp(prefix="clutch-shot-")
    proc = subprocess.Popen(
        [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={profile}", f"--window-size={width},{height}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    try:
        page = None
        for _ in range(50):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                page = next(t for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        if page is None:
            raise RuntimeError("Chrome didn't start")
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
            pending: dict[int, asyncio.Future] = {}
            logs: list[str] = []
            n = 0

            async def reader():
                async for raw in ws:
                    msg = json.loads(raw)
                    if "id" in msg and msg["id"] in pending:
                        pending.pop(msg["id"]).set_result(msg.get("result", {}))
                    elif msg.get("method") == "Log.entryAdded":
                        e = msg["params"]["entry"]
                        logs.append(f"{e['level']}: {e.get('text', '')} {e.get('url', '')}".strip())
                    elif msg.get("method") == "Runtime.exceptionThrown":
                        logs.append("exception: " + msg["params"]["exceptionDetails"].get("text", ""))
                    elif msg.get("method") == "Runtime.consoleAPICalled" and msg["params"]["type"] in LOUD:
                        args = " ".join(str(a.get("value", a.get("description", ""))) for a in msg["params"]["args"])
                        logs.append(f"console.{msg['params']['type']}: {args}")

            task = asyncio.create_task(reader())

            async def call(method, **params):
                nonlocal n
                n += 1
                fut = asyncio.get_running_loop().create_future()
                pending[n] = fut
                await ws.send(json.dumps({"id": n, "method": method, "params": params}))
                return await fut

            for domain in ("Page", "Log", "Runtime"):
                await call(f"{domain}.enable")
            await call("Page.navigate", url=url)
            await asyncio.sleep(wait)
            shot = await call("Page.captureScreenshot", format="png")
            out.write_bytes(base64.b64decode(shot["data"]))
            task.cancel()
            return logs
    finally:
        proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)


def shoot(url: str, out: Path, wait: float = 4, width: int = 1280, height: int = 1300) -> list[str]:
    """Save a screenshot; return the page's console errors, warnings and security-policy reports."""
    return asyncio.run(_shoot(url, Path(out), wait, width, height))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("out", type=Path)
    ap.add_argument("--wait", type=float, default=4)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=1300)
    a = ap.parse_args()
    for line in shoot(a.url, a.out, a.wait, a.width, a.height):
        print(line)
    print(f"saved {a.out}")

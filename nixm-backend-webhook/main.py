import json
import os
import subprocess
import sys
import hmac
import hashlib
from pathlib import Path
import shutil
import zipfile
import asyncio
import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response
from github import Auth
from github import Github

load_dotenv()

SECRET_KEY = os.getenv("WEBHOOK_SECRET")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if SECRET_KEY is None:
    sys.exit("FATAL: SECRET_KEY not set in .env")

if GITHUB_TOKEN is None:
    sys.exit("GITHUB_TOKEN is not set. Please set it in the .env file.")

auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)
repo = gh.get_repo("Ssentiago/Nixm")

app = FastAPI()


def log(msg: str):
    print(f"[WEBHOOK] {msg}", flush=True)


def download_asset(url: str, dest: Path):
    log(f"Downloading asset: {url} → {dest}")
    try:
        r = httpx.get(url, follow_redirects=True, timeout=60)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        log(f"Downloaded OK: {dest.stat().st_size:,} bytes")
    except Exception as e:
        log(f"Download failed: {e}")
        raise


async def wait_for_assets(tag: str, expected: list[str], timeout: int = 120):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        release = repo.get_release(tag)
        assets = {a.name for a in release.get_assets()}
        log(f"Polling assets: {assets}")
        if all(name in assets for name in expected):
            return
        log("Assets not ready, waiting 5s...")
        await asyncio.sleep(5)
    raise TimeoutError("Assets did not appear in time")


def verify_signature(payload: bytes, secret: str, signature: str) -> bool:
    if not signature:
        log("No signature in headers → reject")
        return False

    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    computed = f"sha256={expected}"

    is_ok = hmac.compare_digest(computed, signature)
    log(
        f"Signature check: {'OK' if is_ok else 'FAIL'} (expected {computed[:12]}..., got {signature[:12]}...)"
    )
    return is_ok


@app.post("/release-webhook")
async def webhook(request: Request):
    log("Webhook received")

    payload = await request.body()
    log(f"Payload size: {len(payload)} bytes")

    headers = request.headers
    signature = headers.get("X-Hub-Signature-256")

    if not verify_signature(payload, SECRET_KEY, signature):
        log("Signature verification failed")
        return Response(status_code=403)

    try:
        data = json.loads(payload)
        log("JSON parsed successfully")
    except json.JSONDecodeError as e:
        log(f"JSON decode error: {e}")
        return Response(status_code=400)

    action = data.get("action")
    log(f"Action: {action}")

    if action != "released":
        log(f"Wrong action ({action}), ignoring")
        return Response(status_code=200)  # GitHub не любит 4xx на игнор

    release_tag = data["release"]["tag_name"]
    log(f"Release tag: {release_tag}")

    temp_dir = Path(__file__).parent / "temp"
    log(f"Temp dir: {temp_dir}")

    if temp_dir.exists():
        log("Removing old temp dir")
        shutil.rmtree(temp_dir, ignore_errors=True)

    temp_dir.mkdir()

    log("Waiting for assets appear in release")
    await wait_for_assets(release_tag, ["dist.zip", "nixm-backend"])

    release = repo.get_release(release_tag)
    for asset in release.get_assets():
        name = asset.name
        url = asset.browser_download_url
        dest = temp_dir / name
        try:
            download_asset(url, dest)
        except Exception:
            log(f"Asset {name} failed, continuing anyway")

    dist = temp_dir / "dist.zip"
    binary = temp_dir / "nixm-backend"

    if not dist.exists() or not binary.exists():
        log(
            f"Critical assets missing: dist.zip={dist.exists()}, nixm-backend={binary.exists()}"
        )
        return Response(status_code=500)

    log("All required assets present")

    server_path = Path(__file__).parent.parent / "nixm"
    if not server_path.exists():
        log(f"Server dir not found: {server_path}")
        return Response(status_code=500)

    log("Stopping service...")
    stop = subprocess.run(
        "sudo systemctl stop nixm.service", shell=True, capture_output=True, text=True
    )
    log(f"Stop exit code: {stop.returncode}")
    if stop.returncode != 0:
        log(f"Stop failed: {stop.stderr.strip()}")

    dest_dist = server_path / "dist"
    dest_bin = server_path / "nixm-backend"

    if dest_dist.exists():
        log("Removing old dist")
        shutil.rmtree(dest_dist)
    if dest_bin.exists():
        log("Removing old binary")
        os.remove(dest_bin)

    log("Extracting dist.zip")
    with zipfile.ZipFile(dist) as zf:
        zf.extractall(dest_dist)
    log("Extraction done")

    log("Moving binary")
    shutil.move(binary, dest_bin)
    os.chmod(dest_bin, 0o755)

    log("Cleaning temp")
    shutil.rmtree(temp_dir, ignore_errors=True)

    log("Starting service...")
    start = subprocess.run(
        "sudo systemctl start nixm.service", shell=True, capture_output=True, text=True
    )
    log(f"Start exit code: {start.returncode}")
    if start.returncode != 0:
        log(f"Start failed: {start.stderr.strip()}")
        return Response(status_code=500)

    log("Deployment completed successfully")
    return Response(status_code=200)


if __name__ == "__main__":
    print("Starting webhook server on 127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

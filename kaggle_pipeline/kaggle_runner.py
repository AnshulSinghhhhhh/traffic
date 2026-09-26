"""
kaggle_runner.py — runs the IDAHR ANPR notebook on Kaggle's free T4 GPU
from your local machine, using the Kaggle API.
"""
import builtins
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

KERNEL_DIR = pathlib.Path(__file__).parent
META_PATH = KERNEL_DIR / "kernel-metadata.json"
OUTPUT_DIR = KERNEL_DIR / "kaggle_output"
ROOT_DIR = KERNEL_DIR.parent
POLL_SECONDS = 30
MAX_WAIT_SECONDS = 60 * 60  # 1 hour max wait


def _kernel_slug() -> str:
    if not META_PATH.exists():
        sys.exit(f"Missing {META_PATH} — check kernel-metadata.json.")
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    slug = meta.get("id", "")
    if "YOUR_KAGGLE_USERNAME" in slug:
        sys.exit("kernel-metadata.json still has placeholder username.")
    return slug


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0 and result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


def push() -> None:
    _run(["kaggle", "kernels", "push", "-p", str(KERNEL_DIR)])


def status() -> str:
    slug = _kernel_slug()
    result = _run(["kaggle", "kernels", "status", slug])
    return result.stdout.lower()


def wait_until_done() -> bool:
    waited = 0
    while waited < MAX_WAIT_SECONDS:
        out = status()
        if "complete" in out:
            print("Kernel run complete.")
            return True
        if "error" in out or "failed" in out or "cancel" in out:
            print(f"Kernel run did not finish cleanly — check https://kaggle.com/code/{_kernel_slug()}")
            return False
        print(f"Still running ({waited}s elapsed) — rechecking in {POLL_SECONDS}s...")
        time.sleep(POLL_SECONDS)
        waited += POLL_SECONDS
    print("Timed out waiting. The run may still be going — check the Kaggle site directly.")
    return False


def pull() -> None:
    slug = _kernel_slug()
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Safe open wrapper to prevent Windows cp1252 charmap encoding errors
    orig_open = builtins.open
    def safe_open(file, mode="r", *args, **kwargs):
        if "w" in mode and "b" not in mode and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
        return orig_open(file, mode, *args, **kwargs)
    builtins.open = safe_open

    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    print("Pulling kernel output via Kaggle API...")
    outfiles, token = api.kernels_output(slug, path=str(OUTPUT_DIR), quiet=False)
    print(f"Files downloaded to {OUTPUT_DIR}: {outfiles}")

    events = OUTPUT_DIR / "events.json"
    if events.exists():
        print(f"events.json ready at: {events}")
        # Copy to root directory for downstream scripts
        root_events = ROOT_DIR / "events.json"
        shutil.copy2(events, root_events)
        print(f"Copied fresh events.json to root: {root_events}")
    else:
        print("events.json not in the pulled output yet — check the kernel's Output tab on kaggle.com.")

    import zipfile
    for zip_name, target_dir_name in [("plate_crops.zip", "plate_crops"), ("vehicle_crops.zip", "vehicle_crops")]:
        zpath = OUTPUT_DIR / zip_name
        if zpath.exists():
            print(f"Unpacking {zip_name}...")
            with zipfile.ZipFile(zpath, "r") as zf:
                zf.extractall(OUTPUT_DIR / target_dir_name)
                zf.extractall(ROOT_DIR / target_dir_name)
            print(f"Extracted {zip_name} to {OUTPUT_DIR / target_dir_name} and {ROOT_DIR / target_dir_name}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    if command == "run":
        push()
        print("Pushed. Kaggle is now running the notebook on GPU.")
        if wait_until_done():
            pull()
    elif command == "wait_pull":
        print("Waiting for Kaggle kernel to finish and pulling...")
        if wait_until_done():
            pull()
    elif command == "push":
        push()
        print("Pushed notebook to Kaggle successfully.")
    elif command == "status":
        print(status())
    elif command == "pull":
        pull()
    else:
        sys.exit(f"Unknown command '{command}'. Use: run | push | wait_pull | status | pull")

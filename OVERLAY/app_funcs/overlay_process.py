# app_funcs/overlay_process.py
from __future__ import annotations

import os
import sys
import subprocess
from typing import Optional

from .settings_codec import b64_encode_settings

def overlay_running(proc: Optional[subprocess.Popen]) -> bool:
    return proc is not None and proc.poll() is None

def start_overlay_process(settings: dict, *, udp_port: int) -> subprocess.Popen:
    settings_b64 = b64_encode_settings(settings)

    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--overlay", "--port", str(udp_port), "--settings-b64", settings_b64]
    else:
        cmd = [
            sys.executable,
            os.path.abspath(sys.argv[0]),
            "--overlay",
            "--port",
            str(udp_port),
            "--settings-b64",
            settings_b64,
        ]

    return subprocess.Popen(cmd)

def stop_overlay_process(proc: Optional[subprocess.Popen]):
    if overlay_running(proc):
        try:
            proc.terminate()
        except Exception:
            pass
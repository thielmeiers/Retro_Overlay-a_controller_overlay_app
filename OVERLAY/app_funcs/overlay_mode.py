# app_funcs/overlay_mode.py
from __future__ import annotations

import sys

import overlay

DEFAULT_UDP_PORT = 29301


def run_as_overlay_mode() -> None:
    port = DEFAULT_UDP_PORT
    settings = {}

    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except Exception:
            port = DEFAULT_UDP_PORT

    if "--settings-b64" in sys.argv:
        try:
            b64 = sys.argv[sys.argv.index("--settings-b64") + 1]
            # b64_decode_settings is in app_funcs/settings_codec.py
            from .settings_codec import b64_decode_settings

            settings = b64_decode_settings(b64)
        except Exception:
            settings = {}

    overlay.run_overlay_live(settings, udp_port=port)
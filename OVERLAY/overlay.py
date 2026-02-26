import os
import sys
import json
import socket
import threading
import importlib

import pygame
import win32gui
import win32con
import win32api

os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

FPS = 120
DEADZONE = 0.12
MAX_CONTROLLERS = 4
COLORKEY = (0, 0, 0)

CORNER_LABELS = [
    ("ul", "Upper Left"),
    ("ur", "Upper Right"),
    ("ll", "Lower Left"),
    ("lr", "Lower Right"),
]


def base_path() -> str:
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def dz(v):
    return 0.0 if abs(v) < DEADZONE else v


def norm_trigger(v):
    if v < -0.2:
        return clamp((v + 1.0) / 2.0, 0.0, 1.0)
    return clamp(v, 0.0, 1.0)


class InputState:
    def __init__(self, joystick, btn_map, axis_map):
        self.joystick = joystick
        self.btn_map = btn_map
        self.axis_map = axis_map

    def button(self, name: str) -> bool:
        if not self.joystick:
            return False
        idx = self.btn_map.get(name)
        if idx is None:
            return False
        try:
            return bool(self.joystick.get_button(idx))
        except pygame.error:
            return False

    def axis(self, name: str) -> float:
        if not self.joystick:
            return 0.0
        idx = self.axis_map.get(name)
        if idx is None:
            return 0.0
        try:
            return float(self.joystick.get_axis(idx))
        except pygame.error:
            return 0.0

    def hat(self, index: int = 0) -> tuple[int, int]:
        if not self.joystick or self.joystick.get_numhats() <= index:
            return (0, 0)
        try:
            return self.joystick.get_hat(index)
        except pygame.error:
            return (0, 0)


def setup_window(width, height, x, y, transparency_percent):
    screen = pygame.display.set_mode((width, height), pygame.NOFRAME)
    pygame.display.set_caption("Retro Overlay")

    hwnd = pygame.display.get_wm_info()["window"]

    ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    ex |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex)

    set_transparency(hwnd, transparency_percent)

    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST,
        x, y, width, height,
        win32con.SWP_SHOWWINDOW,
    )

    return screen, hwnd


def set_transparency(hwnd, transparency_percent):
    alpha = int(255 * (clamp(transparency_percent, 0, 100) / 100.0))
    win32gui.SetLayeredWindowAttributes(
        hwnd,
        win32api.RGB(*COLORKEY),
        alpha,
        win32con.LWA_COLORKEY | win32con.LWA_ALPHA,
    )


def compute_position_in_rect(corner, margin, w, h, rect):
    left, top, right, bottom = rect
    mw = right - left
    mh = bottom - top

    corner = (corner or "ul").lower()
    if corner == "ul":
        return left + margin, top + margin
    if corner == "ur":
        return left + mw - w - margin, top + margin
    if corner == "ll":
        return left + margin, top + mh - h - margin
    if corner == "lr":
        return left + mw - w - margin, top + mh - h - margin
    return left + margin, top + margin


def get_friendly_monitor_name(display_device):
    try:
        i = 0
        while True:
            try:
                dev = win32api.EnumDisplayDevices(display_device, i)
            except win32api.error:
                break
            if dev.StateFlags & win32con.DISPLAY_DEVICE_ACTIVE:
                name = (dev.DeviceString or "").strip()
                if name:
                    return name
            i += 1
    except Exception:
        pass
    return display_device


def list_active_monitors():
    monitors = []
    for hmon, hdc, rect in win32api.EnumDisplayMonitors(None, None):
        info = win32api.GetMonitorInfo(hmon)
        mon_rect = info["Monitor"]
        is_primary = bool(info.get("Flags", 0) & 1)
        device = info.get("Device", "")
        friendly = get_friendly_monitor_name(device)
        monitors.append(
            {"monitor_rect": mon_rect, "primary": is_primary, "device": device, "friendly": friendly}
        )
    monitors.sort(key=lambda m: (m["monitor_rect"][0], m["monitor_rect"][1]))
    return monitors


def load_skin(skin_name):
    skin_mod = importlib.import_module(f"skins.{skin_name}")
    return skin_mod.build()


def make_overlay_surface(w, h):
    surf = pygame.Surface((w, h))
    surf.set_colorkey(COLORKEY)
    return surf


def get_controller(ci: int):
    try:
        js = pygame.joystick.Joystick(ci)
        js.init()
        return js
    except pygame.error:
        return None


# -----------------------
# Live update channel
# -----------------------
class LiveConfig:
    def __init__(self, initial: dict):
        self.lock = threading.Lock()
        self.data = initial
        self.dirty_window = True
        self.dirty_layout = True
        self.stop = False

    def apply_update(self, patch: dict):
        with self.lock:
            if patch.get("_stop") is True:
                self.stop = True
                return

            for k, v in patch.items():
                self.data[k] = v

            if "monitor_index" in patch:
                self.dirty_window = True

            if any(k in patch for k in ["scale", "margin", "overlays"]):
                self.dirty_layout = True

    def snapshot(self) -> dict:
        with self.lock:
            return json.loads(json.dumps(self.data))


def start_udp_listener(live: LiveConfig, port: int):
    def run():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", port))

        while True:
            data, _addr = sock.recvfrom(65535)
            try:
                msg = json.loads(data.decode("utf-8", errors="ignore"))
            except Exception:
                continue
            if not isinstance(msg, dict):
                continue

            if msg.get("type") == "update":
                patch = msg.get("settings", {})
                if isinstance(patch, dict):
                    live.apply_update(patch)

    t = threading.Thread(target=run, daemon=True)
    t.start()


# -----------------------
# Overlay engine
# -----------------------
def run_overlay_live(initial_settings: dict, udp_port: int = 29301):
    pygame.init()
    pygame.joystick.init()

    settings = {
        "monitor_index": 0,
        "scale": 1.0,
        "margin": 24,
        "transparency": 100,
        "overlays": [],
    }
    if isinstance(initial_settings, dict):
        settings.update(initial_settings)

    live = LiveConfig(settings)
    start_udp_listener(live, udp_port)

    screen = None
    hwnd = None
    mon_w = mon_h = 0
    mon_left = mon_top = 0

    loaded = []

    def rebuild_window(s):
        nonlocal screen, hwnd, mon_w, mon_h, mon_left, mon_top

        mons = list_active_monitors()
        if not mons:
            return False

        mi = int(clamp(int(s.get("monitor_index", 0)), 0, len(mons) - 1))
        mon = mons[mi]

        mon_left, mon_top, mon_right, mon_bottom = mon["monitor_rect"]
        mon_w = mon_right - mon_left
        mon_h = mon_bottom - mon_top

        screen, hwnd = setup_window(mon_w, mon_h, mon_left, mon_top, int(s.get("transparency", 100)))
        return True

    def rebuild_layout(s):
        nonlocal loaded
        loaded = []

        scale = float(s.get("scale", 1.0))
        margin = int(s.get("margin", 24))
        overlays_cfg = s.get("overlays", [])
        if not isinstance(overlays_cfg, list):
            overlays_cfg = []

        for cfg in overlays_cfg:
            try:
                ci = int(cfg.get("controller_index", 0))
                skin_name = str(cfg.get("skin_name", "default"))
                corner = str(cfg.get("corner", "ul")).lower().strip()

                skin = load_skin(skin_name)

                base_w = int(getattr(skin, "design_width", 400))
                base_h = int(getattr(skin, "design_height", 300))
                out_w = max(1, int(base_w * scale))
                out_h = max(1, int(base_h * scale))

                surf = make_overlay_surface(out_w, out_h)

                px, py = compute_position_in_rect(corner, margin, out_w, out_h, (0, 0, mon_w, mon_h))
                js = get_controller(ci)

                loaded.append({"cfg": cfg, "skin": skin, "surf": surf, "pos": (px, py), "joystick": js})
            except Exception:
                continue

    s0 = live.snapshot()
    if not rebuild_window(s0):
        return
    rebuild_layout(s0)
    live.dirty_window = False
    live.dirty_layout = False

    clock = pygame.time.Clock()

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

        s = live.snapshot()

        if live.stop:
            return

        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            return

        if hwnd is not None:
            set_transparency(hwnd, int(s.get("transparency", 100)))

        if live.dirty_window:
            if rebuild_window(s):
                rebuild_layout(s)
            live.dirty_window = False
            live.dirty_layout = False

        if live.dirty_layout:
            rebuild_layout(s)
            live.dirty_layout = False

        screen.fill(COLORKEY)

        scale = float(s.get("scale", 1.0))

        for item in loaded:
            skin = item["skin"]
            js = item["joystick"]
            surf = item["surf"]

            surf.fill(COLORKEY)
            inp = InputState(js, skin.btn_map, skin.axis_map)
            skin.draw(surf, inp, dz, norm_trigger, scale)
            screen.blit(surf, item["pos"])

        pygame.display.update()


if __name__ == "__main__":
    run_overlay_live({}, udp_port=29301)
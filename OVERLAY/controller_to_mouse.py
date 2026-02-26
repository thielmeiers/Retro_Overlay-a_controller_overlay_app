import ctypes
import math
import time
import pygame

# =========================
# CONFIG
# =========================

DEADZONE = 0.10
SMOOTHING = 0.22
CURVE = 1.6

BASE_SPEED = 1800.0
TARGET_HZ = 500

PRECISION_MULT = 0.35

TRIGGER_THRESHOLD = 0.55
CLICK_DEBOUNCE = 0.05

# Trigger auto-detect tuning
DETECT_IDLE_SEC = 0.35
DETECT_STEP_TIMEOUT_SEC = 4.0
DETECT_DELTA = 0.35


# =========================
# Windows SendInput
# =========================

user32 = ctypes.windll.user32

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", MOUSEINPUT)]


def send_mouse_move(dx: int, dy: int) -> None:
    if dx == 0 and dy == 0:
        return
    inp = INPUT(
        type=INPUT_MOUSE,
        mi=MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, None),
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def send_mouse_flag(flag: int) -> None:
    inp = INPUT(
        type=INPUT_MOUSE,
        mi=MOUSEINPUT(0, 0, 0, flag, 0, None),
    )
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def set_left(down: bool) -> None:
    send_mouse_flag(MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP)


def set_right(down: bool) -> None:
    send_mouse_flag(MOUSEEVENTF_RIGHTDOWN if down else MOUSEEVENTF_RIGHTUP)


def set_middle(down: bool) -> None:
    send_mouse_flag(MOUSEEVENTF_MIDDLEDOWN if down else MOUSEEVENTF_MIDDLEUP)


# =========================
# Helpers
# =========================

def apply_deadzone(v: float, dz: float) -> float:
    av = abs(v)
    if av <= dz:
        return 0.0
    return math.copysign((av - dz) / (1.0 - dz), v)


def apply_curve(v: float, curve: float) -> float:
    return math.copysign(abs(v) ** curve, v)


def ema(prev: float, new: float, alpha: float) -> float:
    return prev + (new - prev) * alpha


def norm_trigger(raw: float) -> float:
    # Normalize to 0..1 for either style: -1..1 (rest=-1) or 0..1 (rest=0)
    if raw < 0.0:
        return max(0.0, min(1.0, (raw + 1.0) * 0.5))
    return max(0.0, min(1.0, raw))


def safe_axis(joy: pygame.joystick.Joystick, idx: int) -> float:
    return joy.get_axis(idx) if joy.get_numaxes() > idx else 0.0


def safe_button(joy: pygame.joystick.Joystick, idx: int) -> int:
    return joy.get_button(idx) if joy.get_numbuttons() > idx else 0


def sample_axis_baseline(joy: pygame.joystick.Joystick, seconds: float) -> list[float]:
    n_axes = joy.get_numaxes()
    sums = [0.0] * n_axes
    n = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < seconds:
        pygame.event.pump()
        for i in range(n_axes):
            sums[i] += joy.get_axis(i)
        n += 1
        time.sleep(0.005)
    if n == 0:
        return [0.0] * n_axes
    return [s / n for s in sums]


def detect_trigger_axis(joy: pygame.joystick.Joystick, baseline: list[float], banned: set[int], step_name: str) -> int | None:
    print(f"\nTrigger detect: {step_name}")
    print("  Keep sticks still. Pull/release the trigger once...")

    n_axes = joy.get_numaxes()
    t0 = time.perf_counter()

    best_i = None
    best_delta = 0.0

    while time.perf_counter() - t0 < DETECT_STEP_TIMEOUT_SEC:
        pygame.event.pump()
        for i in range(n_axes):
            if i in banned:
                continue
            d = abs(joy.get_axis(i) - baseline[i])
            if d > best_delta:
                best_delta = d
                best_i = i
        if best_delta >= DETECT_DELTA:
            print(f"  Detected axis {best_i} (delta {best_delta:.2f})")
            return best_i
        time.sleep(0.01)

    print("  Detect timed out (no strong axis movement).")
    return None


# =========================
# Main
# =========================

def main() -> None:
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        raise SystemExit("No controller detected.")

    joy = pygame.joystick.Joystick(0)
    joy.init()

    
    AX_LX = 0
    AX_LY = 1

    BTN_LB = 4
    BTN_RB = 5
    BTN_L3 = 8

    # --- Trigger axis auto-detect ---
    # Ban left stick axes so triggers can never be mistaken for stick movement.
    banned = {AX_LX, AX_LY}

    print("Calibrating (hands off sticks/triggers)...")
    baseline = sample_axis_baseline(joy, DETECT_IDLE_SEC)

    ax_lt = detect_trigger_axis(joy, baseline, banned=banned, step_name="LT -> Right Click")
    if ax_lt is not None:
        banned.add(ax_lt)

    ax_rt = detect_trigger_axis(joy, baseline, banned=banned, step_name="RT -> Left Click")
    if ax_rt is not None:
        banned.add(ax_rt)

    # If detect fails, fall back to common Xbox mapping (still protected from using 0/1)
    if ax_lt is None:
        ax_lt = 2 if joy.get_numaxes() > 2 and 2 not in banned else None
    if ax_rt is None:
        ax_rt = 5 if joy.get_numaxes() > 5 and 5 not in banned else None

    print(f"\nUsing trigger axes: LT={ax_lt} RT={ax_rt}")
    print("Only reading: LS(0/1), LT axis, RT axis, LB(4), RB(5), L3(8).")
    print("All other inputs ignored.\n")

    # Smoothed cursor state
    sx = 0.0
    sy = 0.0

    # Mouse button states
    left_down = False
    right_down = False
    middle_down = False

    # Drag lock toggle
    drag_lock = False
    l3_prev = 0

    # Debounce timers
    last_left_time = 0.0
    last_right_time = 0.0

    last_t = time.perf_counter()
    clock = pygame.time.Clock()

    try:
        while True:
            pygame.event.pump()

            now = time.perf_counter()
            dt = now - last_t
            last_t = now
            if dt <= 0:
                dt = 1.0 / TARGET_HZ

            # ----- L3 drag lock toggle -----
            l3 = safe_button(joy, BTN_L3)
            if l3 and not l3_prev:
                drag_lock = not drag_lock
                if drag_lock and not left_down:
                    set_left(True)
                    left_down = True
                elif (not drag_lock) and left_down:
                    set_left(False)
                    left_down = False
            l3_prev = l3

            # ----- Left stick -> cursor move (ONLY axes 0 and 1) -----
            raw_x = safe_axis(joy, AX_LX)
            raw_y = safe_axis(joy, AX_LY)

            x = apply_curve(apply_deadzone(raw_x, DEADZONE), CURVE)
            y = apply_curve(apply_deadzone(raw_y, DEADZONE), CURVE)

            sx = ema(sx, x, SMOOTHING)
            sy = ema(sy, y, SMOOTHING)

            speed = BASE_SPEED
            if safe_button(joy, BTN_LB):
                speed *= PRECISION_MULT

            dx = int(round(sx * speed * dt))
            dy = int(round(sy * speed * dt))
            send_mouse_move(dx, dy)

            # ----- RB -> middle click (ONLY button 5) -----
            rb = bool(safe_button(joy, BTN_RB))
            if rb != middle_down:
                set_middle(rb)
                middle_down = rb

            # ----- Triggers -> clicks (ONLY detected axes) -----
            lt = norm_trigger(safe_axis(joy, ax_lt)) if ax_lt is not None else 0.0
            rt = norm_trigger(safe_axis(joy, ax_rt)) if ax_rt is not None else 0.0

            want_left = rt >= TRIGGER_THRESHOLD   # RT -> Left Click
            want_right = lt >= TRIGGER_THRESHOLD  # LT -> Right Click

            if not drag_lock:
                if want_left != left_down and (now - last_left_time) >= CLICK_DEBOUNCE:
                    set_left(want_left)
                    left_down = want_left
                    last_left_time = now

            if want_right != right_down and (now - last_right_time) >= CLICK_DEBOUNCE:
                set_right(want_right)
                right_down = want_right
                last_right_time = now

            clock.tick(TARGET_HZ)

    except KeyboardInterrupt:
        if left_down:
            set_left(False)
        if right_down:
            set_right(False)
        if middle_down:
            set_middle(False)
        print("\nStopped.")


if __name__ == "__main__":
    main()
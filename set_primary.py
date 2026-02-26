import sys
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

# --- Win32 constants ---
ENUM_CURRENT_SETTINGS = -1

CDS_UPDATEREGISTRY = 0x00000001
CDS_NORESET        = 0x10000000
CDS_SET_PRIMARY    = 0x00000010

DISP_CHANGE_SUCCESSFUL = 0

DISPLAY_DEVICE_ACTIVE = 0x00000001
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004

# DEVMODE dmFields flags
DM_POSITION = 0x00000020

# --- Structs ---
class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]

class POINTL(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),

        ("dmPosition", POINTL),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),

        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),

        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),

        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),

        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),

        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),

        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]

# --- Win32 signatures ---
user32.EnumDisplayDevicesW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DISPLAY_DEVICEW), wintypes.DWORD
]
user32.EnumDisplayDevicesW.restype = wintypes.BOOL

user32.EnumDisplaySettingsW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DEVMODEW)
]
user32.EnumDisplaySettingsW.restype = wintypes.BOOL

user32.ChangeDisplaySettingsExW.argtypes = [
    wintypes.LPCWSTR, ctypes.POINTER(DEVMODEW), wintypes.HWND, wintypes.DWORD, wintypes.LPVOID
]
user32.ChangeDisplaySettingsExW.restype = wintypes.LONG


def get_active_displays():
    displays = []
    i = 0
    while True:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(dd)

        ok = user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0)
        if not ok:
            break

        if dd.StateFlags & DISPLAY_DEVICE_ACTIVE:
            dm = DEVMODEW()
            dm.dmSize = ctypes.sizeof(DEVMODEW)

            if user32.EnumDisplaySettingsW(dd.DeviceName, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
                displays.append({
                    "name": dd.DeviceName,
                    "desc": dd.DeviceString,
                    "x": dm.dmPosition.x,
                    "y": dm.dmPosition.y,
                    "w": dm.dmPelsWidth,
                    "h": dm.dmPelsHeight,
                    "is_primary": bool(dd.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE),
                    "state_flags": dd.StateFlags,
                })

        i += 1

    return displays


def print_displays(displays, title="Active displays"):
    print(f"\n=== {title} ===")
    if not displays:
        print("No active displays found.")
        return

    for d in displays:
        primary_tag = " [PRIMARY?]" if d["is_primary"] else ""
        print(f"- {d['name']}{primary_tag}")
        print(f"  Desc: {d['desc']}")
        print(f"  Pos : ({d['x']}, {d['y']})")
        print(f"  Res : {d['w']}x{d['h']}")
    print("")


def normalize_target(arg: str) -> str:
    r"""Accept '1' -> \\.\DISPLAY1, or '\\.\DISPLAY2' -> itself."""
    a = arg.strip().strip('"')
    if a.isdigit():
        return rf"\\.\DISPLAY{a}"
    return a


def _read_devmode(display_name: str) -> DEVMODEW | None:
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    if not user32.EnumDisplaySettingsW(display_name, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
        return None
    return dm


def _apply_staged() -> int:
    return int(user32.ChangeDisplaySettingsExW(None, None, None, 0, None))


def set_primary(target_name: str) -> int:
    displays = get_active_displays()
    print_displays(displays, "Before change")

    target = next((d for d in displays if d["name"].upper() == target_name.upper()), None)
    if not target:
        print(f"ERROR: Target display not found: {target_name}")
        print("Tip: run with --list to see exact names, or pass 1/2/3.")
        return 2

    print(f"Requested primary: {target['name']}  ({target['desc']})")

    dx = -target["x"]
    dy = -target["y"]
    print(f"Shifting desktop so target becomes (0,0): dx={dx}, dy={dy}")

    # Build desired positions
    desired = {}
    for d in displays:
        desired[d["name"].upper()] = (d["x"] + dx, d["y"] + dy)

    # Phase 1: move only displays that actually need to move (stage, no primary change yet).
    # Do non-primary first, then current primary last (less driver-flaky).
    move_order = sorted(displays, key=lambda d: (d["is_primary"], d["name"]))

    staged_any = False
    for d in move_order:
        name = d["name"]
        new_x, new_y = desired[name.upper()]

        # Skip if no change needed
        
        if new_x == d["x"] and new_y == d["y"]:
            continue

        dm = _read_devmode(name)
        if dm is None:
            print(f"WARNING: Could not read settings for {name}, skipping.")
            continue

        dm.dmPosition.x = new_x
        dm.dmPosition.y = new_y

        # Critical: advertise ONLY what we're changing
        dm.dmFields = DM_POSITION

        flags = CDS_UPDATEREGISTRY | CDS_NORESET
        res = int(user32.ChangeDisplaySettingsExW(name, ctypes.byref(dm), None, flags, None))
        if res != DISP_CHANGE_SUCCESSFUL:
            print(f"ERROR: Move stage failed for {name} (code {res})")
            return 3

        staged_any = True
        print(f"Staged move: {name} -> ({new_x}, {new_y})")

    if staged_any:
        print("Applying moves...")
        res = _apply_staged()
        if res != DISP_CHANGE_SUCCESSFUL:
            print(f"ERROR: Apply moves failed (code {res})")
            return 4
    else:
        print("No moves needed.")

    # Phase 2: set primary (don’t stage with NORESET; just set and apply)
    dm_target = _read_devmode(target_name)
    if dm_target is None:
        print(f"ERROR: Could not read settings for target {target_name}.")
        return 5

    # Some drivers want dmFields consistent; DM_POSITION is safe here even if position is already correct.
    dm_target.dmFields = DM_POSITION

    print("Setting primary...")
    res = int(user32.ChangeDisplaySettingsExW(
        target_name,
        ctypes.byref(dm_target),
        None,
        CDS_UPDATEREGISTRY | CDS_SET_PRIMARY,
        None
    ))
    if res != DISP_CHANGE_SUCCESSFUL:
        print(f"ERROR: Set primary failed for {target_name} (code {res})")
        return 6

    print("Applying primary...")
    res = _apply_staged()
    if res != DISP_CHANGE_SUCCESSFUL:
        print(f"ERROR: Apply primary failed (code {res})")
        return 7

    displays_after = get_active_displays()
    print_displays(displays_after, "After change")
    print("Done.")
    return 0


def main():
    if len(sys.argv) == 1 or sys.argv[1] in ("-h", "--help"):
        print(
            "Usage:\n"
            "  python set_primary.py --list\n"
            "  python set_primary.py 1\n"
            "  python set_primary.py 2\n"
            "  python set_primary.py 3\n"
        )
        return 0

    if sys.argv[1] == "--list":
        displays = get_active_displays()
        print_displays(displays, "Active displays (what they are called)")
        return 0

    target = normalize_target(sys.argv[1])
    return set_primary(target)


if __name__ == "__main__":
    raise SystemExit(main())
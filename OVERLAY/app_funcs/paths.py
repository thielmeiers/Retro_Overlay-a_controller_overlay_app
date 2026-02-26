import os
import sys


def base_path() -> str:
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__ + "/..")))
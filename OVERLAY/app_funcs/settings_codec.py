import base64
import json


def b64_encode_settings(settings: dict) -> str:
    raw = json.dumps(settings, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def b64_decode_settings(s: str) -> dict:
    raw = base64.urlsafe_b64decode(s.encode("ascii"))
    obj = json.loads(raw.decode("utf-8"))
    return obj if isinstance(obj, dict) else {}
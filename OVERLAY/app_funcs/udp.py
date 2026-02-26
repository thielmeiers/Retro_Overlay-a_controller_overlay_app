# app_funcs/udp.py
import json
import socket


def send_update(settings_full: dict, udp_port: int) -> None:
    msg = {"type": "update", "settings": settings_full}
    data = json.dumps(msg).encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(data, ("127.0.0.1", udp_port))
    finally:
        sock.close()
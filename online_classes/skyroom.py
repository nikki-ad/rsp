from urllib.parse import urlsplit

import requests
from django.conf import settings


def _skyroom_url(url):
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname not in {"www.skyroom.online", "skyroom.online"}
        or parts.username or parts.password
    ):
        raise ValueError("A Skyroom HTTPS URL is required.")
    return parts


def _call(api_url, action, params):
    response = requests.post(
        api_url, json={"action": action, "params": params},
        timeout=(3, 5), allow_redirects=False,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise ValueError("Skyroom rejected the request.")
    return data.get("result")


def operator_join_url(online_class, user):
    api_url = settings.RSP_SKYROOM_API_URL
    _skyroom_url(api_url)
    room_url = _skyroom_url(online_class.skyroom_url)
    parts = room_url.path.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "ch":
        raise ValueError("A Skyroom public room URL is required.")
    room = _call(api_url, "getRoom", {"name": parts[2]})
    if not isinstance(room, dict) or not isinstance(room.get("id"), int):
        raise ValueError("Skyroom room lookup failed.")
    result = _call(api_url, "createLoginUrl", {
        "room_id": room["id"],
        "user_id": str(user.pk),
        "nickname": user.get_full_name() or user.username,
        "access": 3,  # Skyroom room operator
        "concurrent": 1,
        "language": "fa",
        "ttl": 120,
    })
    if not isinstance(result, str):
        raise ValueError("Skyroom did not return a login URL.")
    if not _skyroom_url(result).path.startswith(room_url.path.rstrip("/") + "/"):
        raise ValueError("The Skyroom link belongs to a different room.")
    return result

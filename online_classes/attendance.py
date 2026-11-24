"""Signed event ingestion and refresh-only attendance snapshots."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import BBBAttendanceEvent, BBBAttendanceHook
from .services import build_bbb_meeting_id, validate_bbb_response

EVENT_TYPES = {"meeting-created", "meeting-ended", "user-joined", "user-left"}


def register_attendance_hook(online_class, force=False):
    config = online_class.bbb_configuration
    if not config or not config.is_active:
        raise ValueError("سرویس BBB فعال نیست.")
    base = getattr(settings, "BBB_CALLBACK_BASE_URL", "https://rsp.roshangaran-elementary.com").rstrip("/")
    callback = base + reverse("bbb_attendance_callback", args=[config.pk, online_class.pk])
    hook, _ = BBBAttendanceHook.objects.get_or_create(online_class=online_class,
        defaults={"configuration": config, "callback_url": callback})
    now = timezone.now()
    same = hook.configuration_id == config.pk and hook.callback_url == callback
    if not force and same and hook.last_attempt_at and now - hook.last_attempt_at < timedelta(minutes=5):
        return hook
    hook.configuration = config
    hook.callback_url = callback
    hook.last_attempt_at = now
    if not same:
        hook.registered_at = None
        hook.last_received_at = None
    hook.save()
    params = urlencode({"callbackURL": callback, "meetingID": build_bbb_meeting_id(online_class),
        "getRaw": "false", "eventID": ",".join(sorted(EVENT_TYPES))})
    checksum = hashlib.sha1(("hooks/create" + params + config.secret).encode()).hexdigest()
    response = requests.get(config.api_url.rstrip("/") + "/hooks/create?" + params + "&checksum=" + checksum, timeout=5)
    response.raise_for_status()
    validate_bbb_response(response.text)
    hook.registered_at = now
    hook.save(update_fields=["registered_at"])
    return hook


def valid_callback_signature(hook, body, checksum):
    algorithm = {40: "sha1", 64: "sha256", 96: "sha384", 128: "sha512"}.get(len(checksum))
    if not algorithm:
        return False
    expected = hashlib.new(algorithm, hook.callback_url.encode() + body + hook.configuration.secret.encode()).hexdigest()
    return hmac.compare_digest(expected, checksum)


def parse_event(online_class, data):
    """Validate mapped (getRaw=false) BBB events; ignore unrelated event types."""
    event_type = data.get("id")
    if event_type not in EVENT_TYPES:
        return None
    attributes = data["attributes"]
    meeting = attributes["meeting"]
    if meeting["external-meeting-id"] != build_bbb_meeting_id(online_class):
        raise ValueError("Wrong meeting")
    session = meeting["internal-meeting-id"]
    if not isinstance(session, str) or not session or len(session) > 256:
        raise ValueError("Missing session")
    timestamp = int(data["event"]["ts"])
    occurred = datetime.fromtimestamp(timestamp / 1000, tz=dt_timezone.utc)
    if occurred.year < 2000 or occurred > timezone.now() + timedelta(minutes=5):
        raise ValueError("Invalid event time")
    user = attributes.get("user", {})
    uid = user.get("external-user-id", "")
    participant = user.get("internal-user-id", "")
    if event_type.startswith("user-") and (not uid or not participant):
        raise ValueError("Missing participant")
    for value in (uid, participant):
        if not isinstance(value, str) or len(value) > 256:
            raise ValueError("Invalid user ID")
    identity = json.dumps([str(online_class.pk), str(online_class.bbb_configuration_id), session,
        participant, uid, event_type, timestamp], separators=(",", ":"))
    return {"session_id": session, "participant_id": participant, "external_user_id": uid,
        "full_name": str(user.get("name", ""))[:200], "role": str(user.get("role", ""))[:20],
        "event_type": event_type, "occurred_at": occurred,
        "fingerprint": hashlib.sha256(identity.encode()).hexdigest()}


@transaction.atomic
def store_callback(hook, payload):
    entries = payload if isinstance(payload, list) else [payload]
    if len(entries) > 100:
        raise ValueError("Too many events")
    # Parse the complete batch before saving: invalid batches must not be partially applied.
    rows = [parse_event(hook.online_class, item["data"]) for item in entries]
    for row in rows:
        if row:
            BBBAttendanceEvent.objects.get_or_create(fingerprint=row["fingerprint"], defaults={
                "online_class": hook.online_class, "configuration": hook.configuration,
                **{key: value for key, value in row.items() if key != "fingerprint"}})
    hook.last_received_at = timezone.now()
    hook.save(update_fields=["last_received_at"])


def attendance_rows(online_class, snapshot, cutoff):
    """Live status comes from BBB; timestamps only come from authenticated events."""
    events = online_class.attendance_events.filter(configuration_id=online_class.bbb_configuration_id,
        occurred_at__lte=cutoff, received_at__lte=cutoff)
    session = snapshot["session_id"]
    if not session and not snapshot["running"]:
        session = events.order_by("-occurred_at", "-id").values_list("session_id", flat=True).first()
    events = list(events.filter(session_id=session)) if session else []
    known = {}
    for kind, profiles in (("دانش‌آموز", online_class.students.select_related("user").all()),
                            ("معلم", online_class.teachers.select_related("user").all())):
        for profile in profiles:
            uid = str(profile.user_id)
            known[uid] = {"user_id": uid, "name": str(profile.user), "kind": kind,
                "is_present": False, "history": [], "first_join": None, "last_join": None, "last_exit": None}
    present = {item["user_id"]: item for item in snapshot["attendees"] if item.get("user_id")}
    for event in events:
        if not event.external_user_id:
            continue
        uid = event.external_user_id
        if uid not in known:
            known[uid] = {"user_id": uid, "name": event.full_name or uid, "kind": "سایر شرکت‌کنندگان",
                "is_present": False, "history": [], "first_join": None, "last_join": None, "last_exit": None}
        row = known[uid]
        if event.full_name and row["kind"] == "سایر شرکت‌کنندگان":
            row["name"] = event.full_name
        row["history"].append({"label": "ورود" if event.event_type == "user-joined" else "خروج", "time": event.occurred_at})
        if event.event_type == "user-joined":
            row["first_join"] = row["first_join"] or event.occurred_at
            row["last_join"] = event.occurred_at
        elif event.event_type == "user-left":
            row["last_exit"] = event.occurred_at
    for uid, item in present.items():
        if uid not in known:
            known[uid] = {"user_id": uid, "name": item["full_name"] or uid, "kind": "سایر شرکت‌کنندگان",
                "history": [], "first_join": None, "last_join": None, "last_exit": None}
        known[uid]["is_present"] = True
    # Meeting ended is an exact server event, not an inferred refresh timestamp.
    ended = next((e.occurred_at for e in reversed(events) if e.event_type == "meeting-ended"), None)
    if ended and not snapshot["running"]:
        for row in known.values():
            if row["last_join"] and (not row["last_exit"] or row["last_exit"] < row["last_join"]):
                row["last_exit"] = ended
                row["history"].append({"label": "پایان جلسه", "time": ended})
    return sorted(known.values(), key=lambda row: (row["kind"] != "معلم", row["kind"] != "دانش‌آموز", row["name"]))

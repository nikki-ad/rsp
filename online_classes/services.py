import hashlib
import requests
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

def validate_bbb_response(response_text):
    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as exc:
        raise ValueError("پاسخ معتبر BBB دریافت نشد؛ آدرس API را بررسی کنید.") from exc
    if root.findtext("returncode") != "SUCCESS":
        key = root.findtext("messageKey") or "unknown"
        if key == "checksumError":
            raise ValueError("کلید محرمانه یا آدرس API سرویس BBB صحیح نیست.")
        raise ValueError("درخواست BBB ناموفق بود؛ تنظیمات سرویس را بررسی کنید.")
    return root


def test_bbb_connection(configuration):

    api_url = configuration.api_url.rstrip("/") + "/"

    api_method = "getMeetings"

    checksum = hashlib.sha1(
        f"{api_method}{configuration.secret}".encode("utf-8")
    ).hexdigest()

    url = (
        f"{api_url}{api_method}"
        f"?checksum={checksum}"
    )

    response = requests.get(
        url,
        timeout=10,
    )

    response.raise_for_status()

    validate_bbb_response(response.text)
    return response.text


def build_bbb_meeting_id(online_class):
    return f"online-class-{online_class.id}"



def create_bbb_meeting(online_class):

    configuration = online_class.bbb_configuration

    if not configuration or not configuration.is_active:
        raise ValueError(
            "برای این کلاس سرویس BigBlueButton انتخاب نشده است."
        )

    api_url = configuration.api_url.rstrip("/") + "/"
    api_method = "create"

    meeting_id = build_bbb_meeting_id(online_class)

    params = urlencode(
        {
            "name": online_class.title,
            "meetingID": meeting_id,
            "record": "false",
            "moderatorPW": "teacher-pass",
            "attendeePW": "student-pass",
        }
    )

    checksum = hashlib.sha1(
        f"{api_method}{params}{configuration.secret}".encode("utf-8")
    ).hexdigest()

    url = (
        f"{api_url}{api_method}"
        f"?{params}"
        f"&checksum={checksum}"
    )

    response = requests.get(
        url,
        timeout=10,
    )

    response.raise_for_status()

    validate_bbb_response(response.text)
    return response.text


def build_bbb_join_url(
    online_class,
    user,
    role,
):

    configuration = online_class.bbb_configuration

    if not configuration or not configuration.is_active:
        raise ValueError(
            "برای این کلاس سرویس BigBlueButton انتخاب نشده است."
        )

    api_url = configuration.api_url.rstrip("/") + "/"
    api_method = "join"

    meeting_id = build_bbb_meeting_id(online_class)

    full_name = (
        user.get_full_name()
        or user.username
    )

    if role == "moderator":
        password = "teacher-pass"
    else:
        password = "student-pass"

    params = urlencode(
        {
            "fullName": full_name,
            "meetingID": meeting_id,
            "password": password,
            "role": "MODERATOR" if role == "moderator" else "VIEWER",
            "userID": str(user.id),
        }
    )

    checksum = hashlib.sha1(
        f"{api_method}{params}{configuration.secret}".encode("utf-8")
    ).hexdigest()

    return (
        f"{api_url}{api_method}"
        f"?{params}"
        f"&checksum={checksum}"
    )



def get_bbb_live_snapshot(online_class):

    configuration = online_class.bbb_configuration

    if not configuration or not configuration.is_active:
        raise ValueError(
            "برای این کلاس سرویس BigBlueButton انتخاب نشده است."
        )

    api_url = configuration.api_url.rstrip("/") + "/"
    api_method = "getMeetingInfo"

    meeting_id = build_bbb_meeting_id(
        online_class
    )

    params = urlencode(
        {
            "meetingID": meeting_id,
        }
    )

    checksum = hashlib.sha1(
        f"{api_method}{params}{configuration.secret}".encode("utf-8")
    ).hexdigest()

    url = (
        f"{api_url}{api_method}"
        f"?{params}"
        f"&checksum={checksum}"
    )

    response = requests.get(
        url,
        timeout=10,
    )

    response.raise_for_status()

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        raise ValueError("پاسخ معتبر BBB دریافت نشد.") from exc
    if root.findtext("messageKey") == "notFound":
        return {"session_id": None, "attendees": [], "running": False}
    validate_bbb_response(response.text)

    attendees = []

    for attendee in root.findall(
        ".//attendees/attendee"
    ):

        attendees.append(
            {
                "user_id": attendee.findtext("userID"),
                "full_name": attendee.findtext("fullName"),
                "role": attendee.findtext("role"),
            }
        )

    return {"session_id": root.findtext("internalMeetingID"), "attendees": attendees, "running": True}


def get_bbb_live_attendees(online_class):
    return get_bbb_live_snapshot(online_class)["attendees"]

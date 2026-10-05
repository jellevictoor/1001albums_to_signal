"""Sending through signal-cli-rest-api, with recovery for the known group-send hang."""
from pathlib import Path

import requests

import config
from signal_store import AccountStore

# Must exceed signal-cli-rest-api's own send timeout (120s), so that a slow
# send returns its real error instead of the client abandoning a live request.
SEND_TIMEOUT = 150


def _post_send(recipients, message, image_base64=None):
    payload = {
        "message": message,
        "number": config.SIGNAL_PHONE_NUMBER,
        "recipients": recipients,
    }
    if image_base64:
        payload["base64_attachments"] = [f"data:image/jpeg;base64,{image_base64}"]

    response = requests.post(f"{config.SIGNAL_API_URL}/v2/send", json=payload, timeout=SEND_TIMEOUT)
    if not response.ok:
        print(f"Signal API error {response.status_code}: {response.text}")
    response.raise_for_status()
    return response.json()


def send_to_group(message, image_base64=None):
    return _post_send([config.SIGNAL_GROUP_ID], message, image_base64)


def send_note_to_self(message):
    """Diagnostics for the operator.

    This is also the single-recipient path, which still receives device-list
    corrections (409) while the group path hangs. Never fatal.
    """
    try:
        _post_send([config.SIGNAL_PHONE_NUMBER], f"1001albums bot: {message}")
    except requests.RequestException as e:
        print(f"Note to self failed: {e}")


def account_store():
    return AccountStore(Path(config.SIGNAL_CLI_DATA_DIR), config.SIGNAL_PHONE_NUMBER)


def send_group_message(message, image_base64=None):
    """Send to the group; on failure reset the sender key and retry once.

    signal-cli reuses a group sender key whose device list it believes is
    current. When the server disagrees, the multi-recipient send hangs instead
    of returning 409 (AsamK/signal-cli #2101, #2113). Forgetting the shared key
    forces a per-device redistribution, which does get the corrections.
    """
    try:
        return send_to_group(message, image_base64)
    except requests.RequestException as e:
        failure = e
    print(f"Group send failed: {failure}")

    send_note_to_self(f"group send failed ({failure}). Resetting sender key and retrying.")
    try:
        forgotten = account_store().reset_shared_sender_key(config.SIGNAL_GROUP_ID)
    except Exception as e:
        send_note_to_self(f"sender key reset failed ({e}). Giving up.")
        raise
    print(f"Forgot sender key for {forgotten} devices, retrying...")

    try:
        result = send_to_group(message, image_base64)
    except requests.RequestException as e:
        send_note_to_self(f"retry after sender key reset ({forgotten} devices) failed ({e}). Giving up.")
        raise
    send_note_to_self(f"retry after sender key reset ({forgotten} devices) succeeded.")
    return result

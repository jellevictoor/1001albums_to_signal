import pytest
import requests

import signal_client


class FakeStore:
    def __init__(self, forgotten=10):
        self.forgotten = forgotten
        self.resets = []

    def reset_shared_sender_key(self, group_id):
        self.resets.append(group_id)
        return self.forgotten


class Recorder:
    def __init__(self):
        self.notes = []
        self.group_sends = []


@pytest.fixture
def signal(monkeypatch):
    recorder = Recorder()
    recorder.store = FakeStore()
    monkeypatch.setattr(signal_client, "account_store", lambda: recorder.store)
    monkeypatch.setattr(signal_client, "send_note_to_self", recorder.notes.append)

    def send_to_group(message, image_base64=None):
        recorder.group_sends.append((message, image_base64))
        outcome = recorder.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(signal_client, "send_to_group", send_to_group)
    return recorder


def test_healthy_send_touches_nothing(signal):
    signal.outcomes = [{"timestamp": "1"}]

    assert signal_client.send_group_message("hi", "img") == {"timestamp": "1"}

    assert signal.group_sends == [("hi", "img")]
    assert signal.store.resets == []
    assert signal.notes == []


def test_failed_send_resets_sender_key_and_retries(signal):
    signal.outcomes = [requests.ReadTimeout("read timed out"), {"timestamp": "2"}]

    assert signal_client.send_group_message("hi", "img") == {"timestamp": "2"}

    assert signal.group_sends == [("hi", "img"), ("hi", "img")]
    assert signal.store.resets == [signal_client.config.SIGNAL_GROUP_ID]
    assert [n.split(" (")[0] for n in signal.notes] == [
        "group send failed",
        "retry after sender key reset",
    ]
    assert "succeeded" in signal.notes[1]


def test_failed_retry_reports_and_raises(signal):
    signal.outcomes = [requests.ReadTimeout("first"), requests.ReadTimeout("second")]

    with pytest.raises(requests.ReadTimeout, match="second"):
        signal_client.send_group_message("hi")

    assert len(signal.group_sends) == 2
    assert "Giving up" in signal.notes[-1]


def test_failed_reset_reports_and_raises(signal):
    signal.outcomes = [requests.ReadTimeout("first")]
    signal.store.reset_shared_sender_key = lambda group_id: (_ for _ in ()).throw(FileNotFoundError("no store"))

    with pytest.raises(FileNotFoundError):
        signal_client.send_group_message("hi")

    assert len(signal.group_sends) == 1
    assert "sender key reset failed" in signal.notes[-1]

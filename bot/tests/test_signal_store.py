import base64
import json
import sqlite3

import pytest

from signal_store import AccountStore, group_id_bytes

RAW_GROUP_ID = bytes(range(32))
OTHER_GROUP_ID = bytes(range(32, 64))
DISTRIBUTION = b"d" * 16
OTHER_DISTRIBUTION = b"o" * 16


def rest_group_id(raw):
    return "group." + base64.b64encode(base64.b64encode(raw)).decode()


def test_group_id_decodes_both_base64_layers():
    assert group_id_bytes(rest_group_id(RAW_GROUP_ID)) == RAW_GROUP_ID


def test_group_id_rejects_other_recipient_kinds():
    with pytest.raises(ValueError):
        group_id_bytes("+32400000000")


@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "accounts.json").write_text(json.dumps({
        "accounts": [{"path": "440925", "number": "+32400000000"}],
    }))
    account_dir = tmp_path / "440925.d"
    account_dir.mkdir()
    with sqlite3.connect(account_dir / "account.db") as conn:
        conn.executescript("""
            CREATE TABLE group_v2 (_id INTEGER PRIMARY KEY, group_id BLOB UNIQUE NOT NULL,
                                   distribution_id BLOB UNIQUE NOT NULL) STRICT;
            CREATE TABLE sender_key_shared (_id INTEGER PRIMARY KEY, address TEXT NOT NULL,
                                            device_id INTEGER NOT NULL, distribution_id BLOB NOT NULL,
                                            timestamp INTEGER NOT NULL) STRICT;
        """)
        conn.execute("INSERT INTO group_v2 (group_id, distribution_id) VALUES (?, ?)", (RAW_GROUP_ID, DISTRIBUTION))
        conn.execute("INSERT INTO group_v2 (group_id, distribution_id) VALUES (?, ?)", (OTHER_GROUP_ID, OTHER_DISTRIBUTION))
        for device in (1, 2):
            conn.execute("INSERT INTO sender_key_shared VALUES (NULL, 'aci-a', ?, ?, 0)", (device, DISTRIBUTION))
        conn.execute("INSERT INTO sender_key_shared VALUES (NULL, 'aci-b', 1, ?, 0)", (DISTRIBUTION,))
        conn.execute("INSERT INTO sender_key_shared VALUES (NULL, 'aci-a', 1, ?, 0)", (OTHER_DISTRIBUTION,))
    return tmp_path


def remaining_distributions(data_dir):
    with sqlite3.connect(data_dir / "440925.d" / "account.db") as conn:
        return [row[0] for row in conn.execute("SELECT distribution_id FROM sender_key_shared")]


def test_reset_forgets_only_the_groups_shared_sender_key(data_dir):
    store = AccountStore(data_dir, "+32400000000")

    forgotten = store.reset_shared_sender_key(rest_group_id(RAW_GROUP_ID))

    assert forgotten == 3
    assert remaining_distributions(data_dir) == [OTHER_DISTRIBUTION]


def test_reset_of_unknown_group_forgets_nothing(data_dir):
    store = AccountStore(data_dir, "+32400000000")

    assert store.reset_shared_sender_key(rest_group_id(b"x" * 32)) == 0
    assert len(remaining_distributions(data_dir)) == 4


def test_unknown_account_is_an_error(data_dir):
    with pytest.raises(LookupError):
        AccountStore(data_dir, "+32499999999").reset_shared_sender_key(rest_group_id(RAW_GROUP_ID))

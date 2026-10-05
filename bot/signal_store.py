"""Direct access to signal-cli's account store, for repairs the REST API cannot do."""
import base64
import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

GROUP_ID_PREFIX = "group."


def group_id_bytes(rest_group_id):
    """signal-cli-rest-api group ids are 'group.' + base64(base64(raw id))."""
    if not rest_group_id.startswith(GROUP_ID_PREFIX):
        raise ValueError(f"Not a signal-cli-rest-api group id: {rest_group_id}")
    internal_id = base64.b64decode(rest_group_id[len(GROUP_ID_PREFIX):])
    return base64.b64decode(internal_id)


@dataclass(frozen=True)
class AccountStore:
    data_dir: Path
    phone_number: str

    @property
    def database(self):
        accounts_file = self.data_dir / "accounts.json"
        with open(accounts_file) as f:
            accounts = json.load(f)["accounts"]
        for account in accounts:
            if account["number"] == self.phone_number:
                return self.data_dir / f"{account['path']}.d" / "account.db"
        raise LookupError(f"{self.phone_number} not found in {accounts_file}")

    def reset_shared_sender_key(self, rest_group_id):
        """Forget which devices hold the group's sender key.

        The next group send then redistributes the key per device, over the
        path that does report device-list changes. Returns the number of
        device entries forgotten.
        """
        database = self.database
        with closing(sqlite3.connect(database, timeout=30)) as conn, conn:
            deleted = conn.execute(
                "DELETE FROM sender_key_shared WHERE distribution_id = "
                "(SELECT distribution_id FROM group_v2 WHERE group_id = ?)",
                (group_id_bytes(rest_group_id),),
            ).rowcount
        self._keep_daemon_ownership(database)
        return deleted

    @staticmethod
    def _keep_daemon_ownership(database):
        """The daemon runs as another user and must stay able to write the WAL side files."""
        owner = database.stat()
        for suffix in ("-wal", "-shm"):
            side_file = database.with_name(database.name + suffix)
            if side_file.exists():
                os.chown(side_file, owner.st_uid, owner.st_gid)

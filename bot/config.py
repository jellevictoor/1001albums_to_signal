import os

ALBUMS_PROJECT_NAME = os.environ["ALBUMS_PROJECT_NAME"]
SIGNAL_PHONE_NUMBER = os.environ["SIGNAL_PHONE_NUMBER"]
SIGNAL_GROUP_ID = os.environ["SIGNAL_GROUP_ID"]
SIGNAL_API_URL = os.environ.get("SIGNAL_API_URL", "http://signal:8080")

ALBUMS_API_URL = f"https://1001albumsgenerator.com/api/v1/projects/{ALBUMS_PROJECT_NAME}"

#!/usr/bin/env python3
import base64
import sys
import time

import requests

import config


def fetch_album():
    """Fetch current album from 1001albumsgenerator API."""
    response = requests.get(config.ALBUMS_API_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "currentAlbum" not in data or data["currentAlbum"] is None:
        return None

    return data["currentAlbum"]


def download_image(url):
    """Download image and return as base64 string."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("utf-8")


def format_message(album):
    """Format album info as a message."""
    artist = album.get("artist", "Unknown Artist")
    name = album.get("name", "Unknown Album")
    year = album.get("releaseDate", "")[:4] if album.get("releaseDate") else "Unknown"
    genres = ", ".join(album.get("genres", [])) or "Unknown"

    # Build streaming URLs from IDs
    spotify_id = album.get("spotifyId", "")
    deezer_id = album.get("deezerId", "")
    youtube_id = album.get("youtubeMusicId", "")

    # Group URL for reviewing
    review_url = f"https://1001albumsgenerator.com/groups/{config.ALBUMS_PROJECT_NAME}"

    lines = [
        "🎵 Album of the Day",
        "",
        f"{artist} - {name} ({year})",
        f"Genre: {genres}",
        "",
    ]

    if spotify_id:
        lines.append(f"🟢 https://open.spotify.com/album/{spotify_id}")
    if deezer_id:
        lines.append(f"🎵 https://www.deezer.com/album/{deezer_id}")
    if youtube_id:
        lines.append(f"🔴 https://music.youtube.com/playlist?list={youtube_id}")

    lines.append(f"\n⭐ Rate & review: {review_url}")
    lines.append("Don't forget to rate yesterday's album!")

    return "\n".join(lines)


def send_signal_message(message, image_base64=None):
    """Send message to Signal group via REST API."""
    url = f"{config.SIGNAL_API_URL}/v2/send"

    payload = {
        "message": message,
        "number": config.SIGNAL_PHONE_NUMBER,
        "recipients": [config.SIGNAL_GROUP_ID],
    }

    if image_base64:
        payload["base64_attachments"] = [f"data:image/jpeg;base64,{image_base64}"]

    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def main():
    print("Fetching album from 1001albumsgenerator...")

    for attempt in range(3):
        try:
            album = fetch_album()
            break
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
            else:
                print("Failed to fetch album after 3 attempts")
                sys.exit(1)

    if album is None:
        print("No current album (project may be paused or finished)")
        sys.exit(0)

    print(f"Album: {album.get('name')} by {album.get('artist')}")

    message = format_message(album)

    # Try to download cover image
    image_base64 = None
    images = album.get("images", [])
    if images:
        # Get largest image
        image_url = max(images, key=lambda x: x.get("width", 0)).get("url")
        if image_url:
            try:
                print(f"Downloading cover image...")
                image_base64 = download_image(image_url)
            except requests.RequestException as e:
                print(f"Failed to download image: {e}, sending text-only")

    print("Sending to Signal...")
    try:
        send_signal_message(message, image_base64)
        print("Message sent successfully!")
    except requests.RequestException as e:
        print(f"Failed to send Signal message: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

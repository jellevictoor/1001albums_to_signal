#!/usr/bin/env python3
import argparse
import base64
import sys
import time

import requests

import config


def fetch_group_data():
    """Fetch full group data from 1001albumsgenerator API."""
    response = requests.get(config.ALBUMS_API_URL, timeout=30)
    response.raise_for_status()
    return response.json()


def download_image(url):
    """Download image and return as base64 string."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("utf-8")


def format_message(album, album_number, total_albums):
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
        f"🎵 Album of the Day ({album_number}/{total_albums})",
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


def format_milestone_message(group_data):
    """Format a milestone summary message from group stats."""
    count = group_data.get("numberOfGeneratedAlbums", 0)
    avg_rating = group_data.get("averageRating")
    total_votes = group_data.get("totalVotes", 0)
    members = group_data.get("members", [])

    lines = [
        f"🏆 Milestone: {count} Albums!",
        "",
    ]

    if avg_rating is not None:
        lines.append(f"Average rating: {avg_rating:.1f}/5.0")
    lines.append(f"Total votes: {total_votes} by {len(members)} members")
    if count > 0:
        lines.append(f"Votes per album: {total_votes / count:.1f}")
    lines.append("")

    top = group_data.get("highestRatedAlbums", [])[:5]
    if top:
        lines.append("⬆️ Top rated:")
        for album in top:
            rating = album.get("averageRating", 0)
            lines.append(f"  {rating:.1f} - {album.get('artist', '?')} - {album.get('name', '?')}")
        lines.append("")

    bottom = group_data.get("lowestRatedAlbums", [])[:5]
    if bottom:
        lines.append("⬇️ Bottom rated:")
        for album in bottom:
            rating = album.get("averageRating", 0)
            lines.append(f"  {rating:.1f} - {album.get('artist', '?')} - {album.get('name', '?')}")
        lines.append("")

    fav_genres = group_data.get("favoriteGenres", [])
    worst_genres = group_data.get("worstGenres", [])
    if fav_genres or worst_genres:
        lines.append("🎶 Genres:")
        for g in fav_genres:
            lines.append(f"  ❤️ {g.get('genre', '?')} ({g.get('rating', 0):.1f}, {g.get('numberOfAlbums', 0)} albums)")
        for g in worst_genres:
            lines.append(f"  💔 {g.get('genre', '?')} ({g.get('rating', 0):.1f}, {g.get('numberOfAlbums', 0)} albums)")
        lines.append("")

    by_decade = group_data.get("ratingByDecade", [])
    if by_decade:
        by_decade_sorted = sorted(by_decade, key=lambda d: d.get("rating", 0), reverse=True)
        lines.append("📅 Decades:")
        for d in by_decade_sorted:
            lines.append(f"  {d.get('decade', '?')}s: {d.get('rating', 0):.1f} ({d.get('numberOfAlbums', 0)} albums)")

    return "\n".join(lines)


def sync_signal():
    """Receive pending messages to keep signal-cli in sync (required for group messaging)."""
    url = f"{config.SIGNAL_API_URL}/v1/receive/{config.SIGNAL_PHONE_NUMBER}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        print("Signal sync completed")
    except requests.RequestException as e:
        print(f"Signal sync warning (continuing anyway): {e}")


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print messages instead of sending to Signal")
    parser.add_argument("--force-milestone", action="store_true", help="Force milestone message regardless of album count")
    args = parser.parse_args()

    print("Fetching album from 1001albumsgenerator...")

    for attempt in range(3):
        try:
            group_data = fetch_group_data()
            break
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
            else:
                print("Failed to fetch album after 3 attempts")
                sys.exit(1)

    album = group_data.get("currentAlbum")
    if album is None:
        print("No current album (project may be paused or finished)")
        sys.exit(0)

    print(f"Album: {album.get('name')} by {album.get('artist')}")

    album_count = group_data.get("numberOfGeneratedAlbums", 0)
    total_albums = group_data.get("totalAlbums", 1001)
    message = format_message(album,1+ album_count, total_albums)

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

    if args.dry_run:
        print("\n--- DRY RUN (not sending to Signal) ---")
        print(message)
        print(f"\n[Image: {'yes' if image_base64 else 'no'}]")
        print(f"Album count: {album_count}")
        if args.force_milestone or (album_count > 0 and album_count % 25 == 0):
            print("\n--- MILESTONE MESSAGE ---")
            print(format_milestone_message(group_data))
        return

    print("Syncing Signal (receiving pending messages)...")
    sync_signal()

    print("Sending to Signal...")
    try:
        send_signal_message(message, image_base64)
        print("Message sent successfully!")
    except requests.RequestException as e:
        print(f"Failed to send Signal message: {e}")
        sys.exit(1)

    # Check for milestone
    print(f"Album count: {album_count}")
    if album_count > 0 and album_count % 25 == 0:
        print(f"Milestone reached: {album_count} albums! Sending summary...")
        milestone_msg = format_milestone_message(group_data)
        try:
            send_signal_message(milestone_msg)
            print("Milestone message sent!")
        except requests.RequestException as e:
            print(f"Failed to send milestone message: {e}")


if __name__ == "__main__":
    main()

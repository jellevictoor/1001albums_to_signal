#!/usr/bin/env python3
"""Check tracked albums for ratings and post summaries to Signal when >= 80% voted."""
import argparse
import math
import sys
import time

import requests

import config
from main import load_state, save_state, fetch_group_data, sync_signal, send_signal_message

RATING_THRESHOLD = 0.8  # Post when 80% of members have rated
API_DELAY = 20  # Seconds between album API calls (rate limit: 3 req/60s)


def fetch_album_reviews(album_uuid):
    """Fetch individual reviews for a specific album."""
    url = f"{config.ALBUMS_API_URL}/albums/{album_uuid}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def has_rated(review):
    """Check if a member has given a numeric rating (did-not-listen doesn't count)."""
    return isinstance(review.get("rating"), (int, float))


def format_ratings_message(album_data, reviews_data, group_rating):
    """Format a ratings summary message."""
    artist = album_data["artist"]
    name = album_data["name"]
    reviews = reviews_data.get("reviews", [])

    rated = [r for r in reviews if has_rated(r)]
    avg = sum(r["rating"] for r in rated) / len(rated) if rated else 0

    lines = [
        f"\U0001f4ca Ratings: {artist} - {name}",
        f"Group Rating: {avg:.1f}/5 ({len(rated)} votes)",
        "",
    ]

    for r in reviews:
        if not has_rated(r):
            continue
        rating = r["rating"]
        comment = r.get("review")
        entry = f"  {r.get('projectName', '?')}: {'*' * rating} ({rating})"
        if comment:
            entry += f'\n    "{comment}"'
        lines.append(entry)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print messages instead of sending")
    args = parser.parse_args()

    state = load_state()
    tracked = state.get("tracked_albums", [])
    pending = [a for a in tracked if not a.get("ratings_posted")]

    if not pending:
        print("No albums pending rating checks.")
        return

    print(f"Checking ratings for {len(pending)} album(s)...")

    # Fetch group data to get member count
    try:
        group_data = fetch_group_data()
    except requests.RequestException as e:
        print(f"Failed to fetch group data: {e}")
        sys.exit(1)

    members = group_data.get("members", [])
    member_count = len(members)
    if member_count == 0:
        print("No members found in group")
        sys.exit(1)

    required_votes = math.ceil(member_count * RATING_THRESHOLD)
    print(f"Group has {member_count} members, need {required_votes} votes (80%)")

    if not args.dry_run:
        print("Syncing Signal...")
        sync_signal()

    posted_any = False
    for i, album in enumerate(pending):
        if i > 0:
            print(f"Waiting {API_DELAY}s for rate limit...")
            time.sleep(API_DELAY)

        uuid = album["uuid"]
        print(f"Checking: {album['artist']} - {album['name']} ({uuid})")

        try:
            reviews_data = fetch_album_reviews(uuid)
        except requests.RequestException as e:
            print(f"  Failed to fetch reviews: {e}")
            continue

        reviews = reviews_data.get("reviews", [])
        rated_count = sum(1 for r in reviews if has_rated(r))
        print(f"  {rated_count}/{member_count} ratings in")

        if rated_count < required_votes:
            print(f"  Not enough votes yet (need {required_votes})")
            continue

        message = format_ratings_message(album, reviews_data, group_data)
        print(f"  Threshold reached! Posting summary.")

        if args.dry_run:
            print(f"\n--- DRY RUN ---\n{message}\n---\n")
        else:
            try:
                send_signal_message(message)
                print(f"  Ratings posted!")
            except requests.RequestException as e:
                print(f"  Failed to send: {e}")
                continue

        # Mark as posted
        album["ratings_posted"] = True
        posted_any = True

    if posted_any:
        save_state(state)
        print("State saved.")
    else:
        print("No albums ready to post.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Application: TubeDigest
Description: Automated pipeline that monitors multiple YouTube channels via RSS,
             stores channel definitions and processed videos in SQLite, generates
             AI summaries with Google Gemini, and dispatches HTML email digests.

Usage:
    - Normal pipeline execution (e.g. via cron):
      python tubedigest.py

    - Channel management via CLI:
      python tubedigest.py --add-channel <CHANNEL_ID> [--name <CHANNEL_NAME>] [--prompt <PROMPT_FILE>]
      python tubedigest.py --remove-channel <CHANNEL_ID>
      python tubedigest.py --list-channels
"""

import os
import sys
import argparse

try:
  import tomllib  # Python 3.11+
except ImportError:
  import tomli as tomllib

from core.state_manager import StateManager
from core.tube_digest import TubeDigest
from core.database import DatabaseManager

CONFIG_FILE = "config.toml"


def load_config() -> dict:
  """Loads the TOML configuration file."""
  if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError(f"Configuration file '{CONFIG_FILE}' not found!")
  with open(CONFIG_FILE, "rb") as f:
    return tomllib.load(f)


def handle_cli_channels(args, db: DatabaseManager) -> bool:
  """Handles CLI channel management arguments. Returns True if a command was handled."""
  if args.add_channel:
    db.add_channel(
        channel_id=args.add_channel,
        channel_name=args.name,
        prompt_file=args.prompt,
    )
    name_display = f" '{args.name}'" if args.name else ""
    prompt_display = f" with prompt '{args.prompt}'" if args.prompt else ""
    print(f"✓ Channel{name_display} ({args.add_channel}) added/updated successfully{prompt_display}.")
    return True

  if args.remove_channel:
    removed = db.remove_channel(args.remove_channel)
    if removed:
      print(f"✓ Channel '{args.remove_channel}' removed successfully.")
    else:
      print(f"⚠ Channel '{args.remove_channel}' not found in database.")
    return True

  if args.list_channels:
    channels = db.list_channels()
    if not channels:
      print("No channels found in database.")
      print("Add a channel using: python tubedigest.py --add-channel <CHANNEL_ID> [--name <NAME>]")
      return True

    header = f"{'Status':<10} {'Channel ID':<26} {'Channel Name':<25} {'Author / Creator':<20} {'Prompt File'}"
    print("\n" + "=" * len(header))
    print("Tracked YouTube Channels (SQLite):")
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    for ch in channels:
      status = "[ACTIVE]" if ch["is_active"] else "[DISABLED]"
      name = (ch["channel_name"] or "Unknown")[:23]
      author = (ch.get("author_name") or "-")[:18]
      prompt = ch["prompt_file"] or "Default"
      print(f"{status:<10} {ch['channel_id']:<26} {name:<25} {author:<20} {prompt}")
    print("=" * len(header))
    print(f"Total: {len(channels)} channel(s)\n")
    return True

  return False


def run_pipeline(config: dict, state_manager: StateManager, db: DatabaseManager, digest: TubeDigest):
  """Runs the digest check for all active channels in the database."""
  active_channels = db.get_active_channels()

  # Auto-migration fallback: if DB is empty, seed from config.toml if channel_id exists
  if not active_channels:
    default_ch = config.get("youtube", {}).get("channel_id")
    if default_ch:
      state_manager.log_message(f"Seeding database with default channel from config.toml: {default_ch}")
      db.add_channel(default_ch, channel_name="Default Channel")
      active_channels = db.get_active_channels()

  if not active_channels:
    state_manager.log_message("No active channels configured in SQLite database.")
    state_manager.log_message("Add a channel using: python tubedigest.py --add-channel <CHANNEL_ID> [--name <NAME>]")
    return

  state_manager.log_message(f"Starting check for {len(active_channels)} active channel(s)...")

  storage = config.get("storage", {})
  transcripts_dir = storage.get("transcripts_dir", "transcripts")

  for channel in active_channels:
    channel_id = channel["channel_id"]
    channel_label = channel.get("channel_name") or channel_id
    prompt_file = channel.get("prompt_file")

    state_manager.log_message(f"[{channel_label}] Checking for latest video...")
    video_url, video_title, video_id, detected_channel_title, author_info = digest.get_latest_video(channel_id)

    # Persist or update author metadata if detected from RSS
    if author_info and (author_info.get("author_name") or detected_channel_title):
      db.upsert_channel_author(
          channel_id=channel_id,
          author_name=author_info.get("author_name"),
          author_url=author_info.get("author_url"),
          channel_title=detected_channel_title,
      )

    if not video_id:
      state_manager.log_message(f"[{channel_label}] No video found or feed parsing error.")
      continue

    # Update channel name in DB if we now know the official title
    if detected_channel_title and not channel.get("channel_name"):
      db.update_channel_checked(channel_id, channel_name=detected_channel_title)
      channel_label = detected_channel_title
    else:
      db.update_channel_checked(channel_id)

    # Check if video was already processed
    if db.is_video_processed(video_id):
      state_manager.log_message(f"[{channel_label}] Latest video '{video_title}' ({video_id}) already processed.")
      continue

    state_manager.log_message(f"[{channel_label}] Found new video: {video_title} ({video_id})")
    state_manager.log_message(f"[{channel_label}] Downloading transcript...")
    transcript = digest.get_transcript(video_id)

    if transcript:
      # Save raw backup transcript in filesystem
      state_manager.save_transcript(video_id, transcript)
      state_manager.log_message(f"[{channel_label}] Transcript saved to {transcripts_dir}/{video_id}.txt")

      state_manager.log_message(f"[{channel_label}] Generating summary with Gemini...")
      sunto_markdown = digest.summarize_transcript(
          video_title, transcript, prompt_file=prompt_file
      )

      email_subject = f"{detected_channel_title or channel_label} - {video_title}"
      state_manager.log_message(f"[{channel_label}] Sending email...")
      digest.send_email(email_subject, sunto_markdown, video_url, video_id)

      # Archive video, transcript, and summary in SQLite
      db.save_processed_video(
          video_id=video_id,
          channel_id=channel_id,
          video_title=video_title,
          video_url=video_url,
          transcript=transcript,
          summary_markdown=sunto_markdown,
          status="COMPLETED",
      )
      state_manager.log_message(f"[{channel_label}] Video archived and processed successfully!")
      state_manager.log_message("-" * 60)

    else:
      state_manager.log_message(f"[{channel_label}] Transcript not available for video ({video_id}). Archiving status.")
      # Archive with NO_TRANSCRIPT status to avoid retrying continuously
      db.save_processed_video(
          video_id=video_id,
          channel_id=channel_id,
          video_title=video_title,
          video_url=video_url,
          transcript="",
          summary_markdown="",
          status="NO_TRANSCRIPT",
      )


def main():
  parser = argparse.ArgumentParser(
      description="TubeDigest: Automated Multi-Channel YouTube Monitor & Gemini Digest Pipeline."
  )
  parser.add_argument(
      "--add-channel",
      metavar="CHANNEL_ID",
      help="Add or update a YouTube Channel ID to monitor in SQLite.",
  )
  parser.add_argument(
      "--name",
      metavar="CHANNEL_NAME",
      help="Optional human-readable name for the channel (used with --add-channel).",
  )
  parser.add_argument(
      "--prompt",
      metavar="PROMPT_FILE",
      help="Optional path to a custom prompt file for this channel (used with --add-channel).",
  )
  parser.add_argument(
      "--remove-channel",
      metavar="CHANNEL_ID",
      help="Remove a channel from SQLite database.",
  )
  parser.add_argument(
      "--list-channels",
      action="store_true",
      help="List all tracked channels in SQLite database.",
  )

  args = parser.parse_args()

  config = load_config()
  storage = config.get("storage", {})
  db_path = storage.get("db_path")
  if not db_path:
    raise KeyError("Missing required 'db_path' in [storage] configuration section.")
  db = DatabaseManager(db_path=db_path)

  # If a CLI channel management command was provided, handle it and exit
  if handle_cli_channels(args, db):
    return

  # Otherwise run the automated pipeline
  state_manager = StateManager(storage)
  digest = TubeDigest(config)
  run_pipeline(config, state_manager, db, digest)


if __name__ == "__main__":
  main()

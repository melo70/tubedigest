#!/usr/bin/env python3
"""
Application: TubeDigest
Description: Automated pipeline that monitors a YouTube channel via RSS, downloads 
             video transcripts, generates structured summaries using the Google 
             Gemini API, and dispatches formatted HTML email digests.

Workflow Steps:
    1. Reads configuration parameters, API keys, and paths from 'config.toml'.
    2. Parses the target YouTube channel RSS feed to check for the latest published video.
    3. Compares the latest video ID with the local state file to prevent duplicate processing.
    4. Automatically downloads the video transcript (with language fallback support).
    5. Saves a local copy of the raw transcript inside the configured transcripts directory.
    6. Sends the transcript to the configured Google Gemini model to generate a markdown summary.
    7. Formats the summary into an HTML email with video thumbnail and dispatches it via SMTP.
    8. Updates the local state file with the processed video ID and writes execution logs.

Usage:
    - Standard execution:
      python tubedigest.py

    - Automated execution via cron (e.g., run every hour):
      0 * * /path/to/python /path/to/tubedigest.py >> /path/to/logs/cron.log 2>&1
"""

import os

try:
  import tomllib  # Python 3.11+
except ImportError:
  import tomli as tomllib

from core.state_manager import StateManager
from core.tube_digest import TubeDigest

CONFIG_FILE = "config.toml"

def main():
  if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError(f"Configuration file '{CONFIG_FILE}' not found!")

  with open(CONFIG_FILE, "rb") as f:
    config = tomllib.load(f)

  # Initialize state manager
  storage = config.get("storage", {})
  state_manager = StateManager(storage)
  
  # Initialize main digest instance
  digest = TubeDigest(config)

  state_manager.log_message("Checking for new videos...")
  video_url, video_title, video_id, channel_title = digest.get_latest_video()

  if not video_id:
    state_manager.log_message("No video found or feed parsing error.")
    return

  last_id = state_manager.load_last_id()
  if video_id == last_id:
    state_manager.log_message(
        "No new video detected since last check."
    )
    return

  state_manager.log_message(
      f"Found new video: {video_title} ({video_id})"
  )

  state_manager.log_message("Downloading transcript...")
  transcript = digest.get_transcript(video_id)

  if transcript:
    # Save raw transcript in the configured directory
    state_manager.save_transcript(video_id, transcript)
    state_manager.log_message(
        f"Transcript saved to {storage.get('transcripts_dir', 'transcripts')}/{video_id}.txt"
    )

    state_manager.log_message("Generating summary with Gemini...")
    sunto_markdown = digest.summarize_transcript(video_title, transcript)

    email_subject = f"{channel_title} - {video_title}"

    state_manager.log_message("Sending email...")
    digest.send_email(email_subject, sunto_markdown, video_url, video_id)

    state_manager.save_last_id(video_id)
    state_manager.log_message("Process completed successfully!")
    state_manager.log_message("---------------------------------------------------------------")

  else:
    state_manager.log_message(
        "Unable to proceed: transcript not available for this video."
    )


if __name__ == "__main__":
  main()

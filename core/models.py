"""Data models and enumerated types for TubeDigest."""

import sys

if sys.version_info >= (3, 11):
  from enum import StrEnum
else:
  from enum import Enum

  class StrEnum(str, Enum):
    """Fallback StrEnum implementation for Python < 3.11."""
    pass


class VideoStatus(StrEnum):
  """Lifecycle status indicators for processed videos in SQLite database.

  - COMPLETED: Full pipeline finished (transcribed, summarized by Gemini, email sent).
  - PENDING_SUMMARY: Transcript cached in SQLite, awaiting Gemini AI summary retry.
  - PENDING_EMAIL: Gemini summary cached in SQLite, awaiting email dispatch retry.
  - NO_TRANSCRIPT: Video has no subtitles/transcript available on YouTube.
  """
  COMPLETED = "COMPLETED"
  PENDING_SUMMARY = "PENDING_SUMMARY"
  PENDING_EMAIL = "PENDING_EMAIL"
  NO_TRANSCRIPT = "NO_TRANSCRIPT"

import os
import sqlite3
from typing import List, Optional, Dict, Any

from core.queries import DatabaseQueries


class DatabaseManager:
  """Manages the SQLite database for channels, authors, prompts, and processed video archives."""

  def __init__(self, db_path: str):
    if not db_path:
      raise ValueError("db_path must be specified and cannot be empty.")
    self.db_path = db_path
    db_dir = os.path.dirname(self.db_path)
    if db_dir:
      os.makedirs(db_dir, exist_ok=True)
    self.init_db()

  def get_connection(self) -> sqlite3.Connection:
    """Returns a new database connection configured with Row factory and foreign keys."""
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

  def init_db(self):
    """Initializes tables, indexes, and default prompt seed."""
    with self.get_connection() as conn:
      # Migration safeguard: if channels had old prompt_file column, migrate to prompt_id
      cursor = conn.execute("PRAGMA table_info(channels)")
      columns = [row["name"] for row in cursor.fetchall()]
      if columns and "prompt_file" in columns and "prompt_id" not in columns:
        conn.execute("ALTER TABLE channels ADD COLUMN prompt_id TEXT DEFAULT 'default'")

      conn.executescript(DatabaseQueries.CREATE_TABLES)

      # Seed default prompt if not already present
      conn.execute(
          DatabaseQueries.SEED_DEFAULT_PROMPT,
          (
              DatabaseQueries.DEFAULT_PROMPT_ID,
              DatabaseQueries.DEFAULT_PROMPT_TITLE,
              DatabaseQueries.DEFAULT_PROMPT_TEXT,
          ),
      )

      # Backfill any existing channel missing author metadata
      conn.execute("""
          INSERT OR IGNORE INTO channel_authors (channel_id, author_name, author_url, channel_title)
          SELECT channel_id, channel_name, 'https://www.youtube.com/channel/' || channel_id, channel_name
          FROM channels
          WHERE channel_name IS NOT NULL
      """)
      conn.commit()

  # ----------------------------------------------------------------------------
  # Prompt Operations
  # ----------------------------------------------------------------------------
  def list_prompts(self) -> List[Dict[str, Any]]:
    """Retrieves all stored prompts."""
    with self.get_connection() as conn:
      rows = conn.execute(DatabaseQueries.LIST_PROMPTS).fetchall()
      return [dict(row) for row in rows]

  def get_prompt_details(self, prompt_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves full details and text of a specific prompt."""
    with self.get_connection() as conn:
      row = conn.execute(DatabaseQueries.GET_PROMPT_DETAILS, (prompt_id,)).fetchone()
      return dict(row) if row else None

  def get_prompt_text(self, prompt_id: Optional[str] = None) -> str:
    """Retrieves prompt text by prompt_id or falls back to the default prompt."""
    with self.get_connection() as conn:
      if prompt_id:
        row = conn.execute(DatabaseQueries.GET_PROMPT, (prompt_id,)).fetchone()
        if row and row["prompt_text"]:
          return row["prompt_text"]

      # Fallback to default prompt
      default_row = conn.execute(DatabaseQueries.GET_DEFAULT_PROMPT).fetchone()
      if default_row and default_row["prompt_text"]:
        return default_row["prompt_text"]

    return DatabaseQueries.DEFAULT_PROMPT_TEXT

  def upsert_prompt(
      self,
      prompt_id: str,
      prompt_title: str,
      prompt_text: str,
      is_default: int = 0,
  ):
    """Inserts or updates a prompt template in the database."""
    with self.get_connection() as conn:
      conn.execute(
          DatabaseQueries.UPSERT_PROMPT,
          (prompt_id, prompt_title, prompt_text, is_default),
      )
      conn.commit()

  # ----------------------------------------------------------------------------
  # Channel Operations
  # ----------------------------------------------------------------------------
  def add_channel(
      self,
      channel_id: str,
      channel_name: Optional[str] = None,
      prompt_id: Optional[str] = None,
      author_name: Optional[str] = None,
      author_url: Optional[str] = None,
      channel_title: Optional[str] = None,
  ) -> bool:
    """Adds a new channel or reactivates/updates an existing one, automatically populating author profile."""
    resolved_prompt_id = prompt_id or "default"
    resolved_author_name = author_name or channel_name
    resolved_channel_title = channel_title or channel_name
    resolved_author_url = author_url or f"https://www.youtube.com/channel/{channel_id}"

    with self.get_connection() as conn:
      existing = conn.execute(
          DatabaseQueries.CHECK_CHANNEL_EXISTS,
          (channel_id,),
      ).fetchone()
      if existing:
        conn.execute(
            DatabaseQueries.UPDATE_CHANNEL,
            (channel_name, resolved_prompt_id, channel_id),
        )
      else:
        conn.execute(
            DatabaseQueries.INSERT_CHANNEL,
            (channel_id, channel_name, resolved_prompt_id),
        )

      # Automatically populate or update channel_authors metadata
      if resolved_author_name or resolved_channel_title:
        conn.execute(
            DatabaseQueries.UPSERT_CHANNEL_AUTHOR,
            (channel_id, resolved_author_name, resolved_author_url, resolved_channel_title, None),
        )
      conn.commit()
    return True

  def remove_channel(self, identifier: str) -> Optional[Dict[str, Any]]:
    """Deletes a channel and cascades deletion to all associated records (authors, videos).

    Accepts either a channel_id or channel_name. Returns a summary dictionary of deleted
    records across tables, or None if the channel does not exist.
    """
    with self.get_connection() as conn:
      channel = conn.execute(
          DatabaseQueries.FIND_CHANNEL, (identifier, identifier)
      ).fetchone()
      if not channel:
        return None

      channel_id = channel["channel_id"]
      channel_name = channel["channel_name"]

      videos_count = conn.execute(
          DatabaseQueries.COUNT_CHANNEL_VIDEOS, (channel_id,)
      ).fetchone()[0]
      authors_count = conn.execute(
          DatabaseQueries.COUNT_CHANNEL_AUTHORS, (channel_id,)
      ).fetchone()[0]

      # Explicit cascading deletion across all linked tables
      conn.execute(DatabaseQueries.DELETE_CHANNEL_AUTHORS, (channel_id,))
      conn.execute(DatabaseQueries.DELETE_CHANNEL_VIDEOS, (channel_id,))
      cur = conn.execute(DatabaseQueries.REMOVE_CHANNEL, (channel_id,))
      conn.commit()

      return {
          "channel_id": channel_id,
          "channel_name": channel_name,
          "authors_deleted": authors_count,
          "videos_deleted": videos_count,
          "success": cur.rowcount > 0,
      }

  def list_channels(self) -> List[Dict[str, Any]]:
    """Retrieves all tracked channels joined with author and prompt metadata."""
    with self.get_connection() as conn:
      rows = conn.execute(DatabaseQueries.LIST_CHANNELS).fetchall()
      return [dict(row) for row in rows]

  def get_active_channels(self) -> List[Dict[str, Any]]:
    """Retrieves only active channels for processing."""
    with self.get_connection() as conn:
      rows = conn.execute(DatabaseQueries.GET_ACTIVE_CHANNELS).fetchall()
      return [dict(row) for row in rows]

  def update_channel_checked(
      self, channel_id: str, channel_name: Optional[str] = None
  ):
    """Updates the last_checked_at timestamp and optionally the channel name."""
    with self.get_connection() as conn:
      conn.execute(
          DatabaseQueries.UPDATE_CHANNEL_CHECKED,
          (channel_name, channel_id),
      )
      conn.commit()

  # ----------------------------------------------------------------------------
  # Author Operations
  # ----------------------------------------------------------------------------
  def upsert_channel_author(
      self,
      channel_id: str,
      author_name: Optional[str] = None,
      author_url: Optional[str] = None,
      channel_title: Optional[str] = None,
      custom_url: Optional[str] = None,
  ):
    """Saves or updates profile information for a channel author."""
    with self.get_connection() as conn:
      conn.execute(
          DatabaseQueries.UPSERT_CHANNEL_AUTHOR,
          (channel_id, author_name, author_url, channel_title, custom_url),
      )
      conn.commit()

  def get_channel_author(self, channel_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves profile information for a channel author."""
    with self.get_connection() as conn:
      row = conn.execute(
          DatabaseQueries.GET_CHANNEL_AUTHOR, (channel_id,)
      ).fetchone()
      return dict(row) if row else None

  # ----------------------------------------------------------------------------
  # Video Archive Operations
  # ----------------------------------------------------------------------------
  def is_video_processed(self, video_id: str) -> bool:
    """Checks whether a video ID has already been processed."""
    with self.get_connection() as conn:
      row = conn.execute(
          DatabaseQueries.IS_VIDEO_PROCESSED, (video_id,)
      ).fetchone()
      return row is not None

  def save_processed_video(
      self,
      video_id: str,
      channel_id: str,
      video_title: str,
      video_url: str,
      transcript: str,
      summary_markdown: str,
      status: str = "COMPLETED",
  ):
    """Archives a processed video, its transcript, and summary in SQLite."""
    with self.get_connection() as conn:
      conn.execute(
          DatabaseQueries.SAVE_PROCESSED_VIDEO,
          (
              video_id,
              channel_id,
              video_title,
              video_url,
              transcript,
              summary_markdown,
              status,
          ),
      )
      conn.commit()

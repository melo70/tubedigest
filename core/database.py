import os
import sqlite3
from typing import List, Optional, Dict, Any

from core.queries import DatabaseQueries


class DatabaseManager:
  """Manages the SQLite database for channels, authors, and processed video archives."""

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
    """Initializes tables and indexes using DatabaseQueries.CREATE_TABLES."""
    with self.get_connection() as conn:
      conn.executescript(DatabaseQueries.CREATE_TABLES)

  def add_channel(
      self,
      channel_id: str,
      channel_name: Optional[str] = None,
      prompt_file: Optional[str] = None,
  ) -> bool:
    """Adds a new channel or reactivates/updates an existing one."""
    with self.get_connection() as conn:
      existing = conn.execute(
          DatabaseQueries.CHECK_CHANNEL_EXISTS,
          (channel_id,),
      ).fetchone()
      if existing:
        conn.execute(
            DatabaseQueries.UPDATE_CHANNEL,
            (channel_name, prompt_file, channel_id),
        )
      else:
        conn.execute(
            DatabaseQueries.INSERT_CHANNEL,
            (channel_id, channel_name, prompt_file),
        )
      conn.commit()
    return True

  def remove_channel(self, channel_id: str) -> bool:
    """Removes a channel from the database."""
    with self.get_connection() as conn:
      cur = conn.execute(DatabaseQueries.REMOVE_CHANNEL, (channel_id,))
      conn.commit()
      return cur.rowcount > 0

  def list_channels(self) -> List[Dict[str, Any]]:
    """Retrieves all tracked channels joined with author information."""
    with self.get_connection() as conn:
      rows = conn.execute(DatabaseQueries.LIST_CHANNELS).fetchall()
      return [dict(row) for row in rows]

  def get_active_channels(self) -> List[Dict[str, Any]]:
    """Retrieves only active channels for processing."""
    with self.get_connection() as conn:
      rows = conn.execute(DatabaseQueries.GET_ACTIVE_CHANNELS).fetchall()
      return [dict(row) for row in rows]

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

import os
import sqlite3
from typing import List, Optional, Dict, Any


class DatabaseManager:
  """Manages the SQLite database for channels and processed video archives."""

  def __init__(self, db_path: str = "tubedigest.db"):
    self.db_path = db_path
    db_dir = os.path.dirname(self.db_path)
    if db_dir:
      os.makedirs(db_dir, exist_ok=True)
    self.init_db()

  def get_connection(self) -> sqlite3.Connection:
    """Returns a new database connection configured with Row factory."""
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

  def init_db(self):
    """Initializes tables and indexes if they do not exist."""
    with self.get_connection() as conn:
      conn.executescript("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id TEXT PRIMARY KEY,
            channel_name TEXT,
            prompt_file TEXT DEFAULT 'prompts/default_summary.txt',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_checked_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS processed_videos (
            video_id TEXT PRIMARY KEY,
            channel_id TEXT NOT NULL,
            video_title TEXT,
            video_url TEXT,
            transcript TEXT,
            summary_markdown TEXT,
            status TEXT DEFAULT 'COMPLETED',
            email_sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (channel_id) REFERENCES channels (channel_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_processed_videos_channel ON processed_videos(channel_id);
      """)

  def add_channel(
      self,
      channel_id: str,
      channel_name: Optional[str] = None,
      prompt_file: Optional[str] = None,
  ) -> bool:
    """Adds a new channel or reactivates/updates an existing one."""
    with self.get_connection() as conn:
      existing = conn.execute(
          "SELECT channel_id FROM channels WHERE channel_id = ?",
          (channel_id,),
      ).fetchone()
      if existing:
        conn.execute(
            """
            UPDATE channels 
            SET channel_name = COALESCE(?, channel_name),
                prompt_file = COALESCE(?, prompt_file),
                is_active = 1
            WHERE channel_id = ?
            """,
            (channel_name, prompt_file, channel_id),
        )
      else:
        conn.execute(
            """
            INSERT INTO channels (channel_id, channel_name, prompt_file, is_active)
            VALUES (?, ?, COALESCE(?, 'prompts/default_summary.txt'), 1)
            """,
            (channel_id, channel_name, prompt_file),
        )
      conn.commit()
    return True

  def remove_channel(self, channel_id: str) -> bool:
    """Removes a channel from the database."""
    with self.get_connection() as conn:
      cur = conn.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
      conn.commit()
      return cur.rowcount > 0

  def list_channels(self) -> List[Dict[str, Any]]:
    """Retrieves all tracked channels."""
    with self.get_connection() as conn:
      rows = conn.execute(
          "SELECT channel_id, channel_name, prompt_file, is_active, last_checked_at FROM channels ORDER BY is_active DESC, channel_name ASC, channel_id ASC"
      ).fetchall()
      return [dict(row) for row in rows]

  def get_active_channels(self) -> List[Dict[str, Any]]:
    """Retrieves only active channels for processing."""
    with self.get_connection() as conn:
      rows = conn.execute(
          "SELECT channel_id, channel_name, prompt_file FROM channels WHERE is_active = 1 ORDER BY channel_id ASC"
      ).fetchall()
      return [dict(row) for row in rows]

  def is_video_processed(self, video_id: str) -> bool:
    """Checks whether a video ID has already been processed."""
    with self.get_connection() as conn:
      row = conn.execute(
          "SELECT 1 FROM processed_videos WHERE video_id = ?", (video_id,)
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
          """
          INSERT OR REPLACE INTO processed_videos (
              video_id, channel_id, video_title, video_url, transcript, summary_markdown, status, email_sent_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
          """,
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
      if channel_name:
        conn.execute(
            """
            UPDATE channels 
            SET last_checked_at = CURRENT_TIMESTAMP,
                channel_name = COALESCE(channel_name, ?)
            WHERE channel_id = ?
            """,
            (channel_name, channel_id),
        )
      else:
        conn.execute(
            "UPDATE channels SET last_checked_at = CURRENT_TIMESTAMP WHERE channel_id = ?",
            (channel_id,),
        )
      conn.commit()

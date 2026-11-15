import os
import sqlite3
from typing import List, Optional, Dict, Any

from core.queries import DatabaseQueries


class DatabaseManager:
  """Manages the SQLite database for channels, authors, prompts, and processed video archives."""

  def __init__(self, db_path: str, templates_dir: Optional[str] = "templates"):
    if not db_path:
      raise ValueError("db_path must be specified and cannot be empty.")
    self.db_path = db_path
    self.templates_dir = templates_dir or "templates"
    db_dir = os.path.dirname(self.db_path)
    if db_dir:
      os.makedirs(db_dir, exist_ok=True)
    self.init_db()

  def load_template_file(self, filename: str) -> str:
    """Loads a template file from the external templates directory."""
    path = os.path.join(self.templates_dir, filename)
    if os.path.exists(path):
      with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()
    return ""

  def get_connection(self) -> sqlite3.Connection:
    """Returns a new database connection configured with Row factory and foreign keys."""
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

  def init_db(self):
    """Initializes tables, indexes, and default prompt seed from external templates."""
    with self.get_connection() as conn:
      # Migration safeguard: if channels had old prompt_file column, migrate to prompt_id
      cursor = conn.execute("PRAGMA table_info(channels)")
      columns = [row["name"] for row in cursor.fetchall()]
      if columns and "prompt_file" in columns and "prompt_id" not in columns:
        conn.execute("ALTER TABLE channels ADD COLUMN prompt_id TEXT DEFAULT 'default'")

      conn.executescript(DatabaseQueries.CREATE_TABLES)

      # Migration safeguard: if prompts table is missing email_template column, migrate it
      p_cursor = conn.execute("PRAGMA table_info(prompts)")
      p_columns = [row["name"] for row in p_cursor.fetchall()]
      if p_columns and "email_template" not in p_columns:
        conn.execute("ALTER TABLE prompts ADD COLUMN email_template TEXT")

      # Seed default prompt and email layout from external template files
      default_prompt_text = self.load_template_file("default_prompt.txt")
      default_email_html = self.load_template_file("default_email.html")

      conn.execute(
          DatabaseQueries.SEED_DEFAULT_PROMPT,
          (
              DatabaseQueries.DEFAULT_PROMPT_ID,
              DatabaseQueries.DEFAULT_PROMPT_TITLE,
              default_prompt_text,
              default_email_html,
          ),
      )

      # Ensure existing default prompt has email_template populated if empty
      if default_email_html:
        conn.execute(
            """UPDATE prompts SET email_template = ? WHERE prompt_id = ? AND (email_template IS NULL OR email_template = '')""",
            (default_email_html, DatabaseQueries.DEFAULT_PROMPT_ID),
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

    # Final fallback if not found in database: read external template file
    return self.load_template_file("default_prompt.txt")

  def get_email_template(self, prompt_id: Optional[str] = None) -> Optional[str]:
    """Retrieves email HTML template for the given prompt_id, or None if not configured."""
    with self.get_connection() as conn:
      if prompt_id:
        row = conn.execute(DatabaseQueries.GET_PROMPT_DETAILS, (prompt_id,)).fetchone()
        if row:
          val = row["email_template"]
          return val if val and val.strip() else None

      # If no specific prompt was specified, check default prompt
      default_row = conn.execute(DatabaseQueries.GET_DEFAULT_PROMPT).fetchone()
      if default_row:
        val = default_row["email_template"]
        return val if val and val.strip() else None

    return None

  def upsert_prompt(
      self,
      prompt_id: str,
      prompt_title: str,
      prompt_text: str,
      email_template: Optional[str] = None,
      is_default: int = 0,
  ):
    """Inserts or updates a prompt template and its email HTML layout in the database."""
    with self.get_connection() as conn:
      conn.execute(
          DatabaseQueries.UPSERT_PROMPT,
          (prompt_id, prompt_title, prompt_text, email_template, is_default),
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

  def get_channel(self, identifier: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single channel by channel_id or channel_name (with normalized fallback)."""
    with self.get_connection() as conn:
      row = conn.execute(
          DatabaseQueries.GET_CHANNEL, (identifier, identifier)
      ).fetchone()
      if row:
        return dict(row)

      # Normalized case-insensitive fallback (ignoring spaces, underscores, and dots)
      clean_id = identifier.strip().lower().replace("_", "").replace(" ", "").replace(".", "")
      all_channels = conn.execute("SELECT channel_id, channel_name, prompt_id, is_active FROM channels").fetchall()
      for ch in all_channels:
        c_name = (ch["channel_name"] or "").strip().lower().replace("_", "").replace(" ", "").replace(".", "")
        if c_name == clean_id:
          return dict(ch)

      return None

  def find_channel_for_video(
      self, channel_id: Optional[str] = None, author_name: Optional[str] = None
  ) -> Optional[Dict[str, Any]]:
    """Locates a tracked channel matching the given channel_id, channel_name, or author_name."""
    if channel_id:
      ch = self.get_channel(channel_id)
      if ch:
        return ch

    if author_name:
      ch = self.get_channel(author_name)
      if ch:
        return ch

      # Also search inside channel_authors table directly
      with self.get_connection() as conn:
        row = conn.execute(
            DatabaseQueries.FIND_CHANNEL_BY_AUTHOR,
            (author_name, author_name),
        ).fetchone()
        if row:
          return dict(row)

    return None

  def set_channel_active(
      self, identifier: str, is_active: bool
  ) -> Optional[Dict[str, Any]]:
    """Enables or disables a channel by channel_id or channel_name.

    Returns a dictionary with channel details and updated status, or None if not found.
    """
    channel = self.get_channel(identifier)
    if not channel:
      return None

    channel_id = channel["channel_id"]
    channel_name = channel["channel_name"]
    status_val = 1 if is_active else 0

    with self.get_connection() as conn:
      cur = conn.execute(
          DatabaseQueries.SET_CHANNEL_ACTIVE, (status_val, channel_id)
      )
      conn.commit()
      return {
          "channel_id": channel_id,
          "channel_name": channel_name,
          "is_active": status_val,
          "success": cur.rowcount > 0,
      }

  def remove_channel(self, identifier: str) -> Optional[Dict[str, Any]]:
    """Deletes a channel and cascades deletion to all associated records (authors, videos).

    Accepts either a channel_id or channel_name. Returns a summary dictionary of deleted
    records across tables, or None if the channel does not exist.
    """
    channel = self.get_channel(identifier)
    if not channel:
      return None

    channel_id = channel["channel_id"]
    channel_name = channel["channel_name"]

    with self.get_connection() as conn:
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
    """Checks whether a video ID has already been fully completed."""
    with self.get_connection() as conn:
      row = conn.execute(
          DatabaseQueries.IS_VIDEO_PROCESSED, (video_id,)
      ).fetchone()
      return row is not None

  def get_processed_video(self, video_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves full archive record for a video by its video_id."""
    with self.get_connection() as conn:
      row = conn.execute(
          DatabaseQueries.GET_PROCESSED_VIDEO, (video_id,)
      ).fetchone()
      return dict(row) if row else None

  def list_processed_videos(self) -> List[Dict[str, Any]]:
    """Retrieves all archived/processed videos joined with channel and author metadata."""
    with self.get_connection() as conn:
      rows = conn.execute(DatabaseQueries.LIST_PROCESSED_VIDEOS).fetchall()
      return [dict(row) for row in rows]

  def get_pending_email_videos(
      self, channel_id: Optional[str] = None
  ) -> List[Dict[str, Any]]:
    """Retrieves all videos awaiting email dispatch, optionally filtered by channel_id."""
    with self.get_connection() as conn:
      if channel_id:
        rows = conn.execute(
            DatabaseQueries.GET_PENDING_EMAIL_VIDEOS, (channel_id,)
        ).fetchall()
      else:
        rows = conn.execute(
            DatabaseQueries.GET_ALL_PENDING_EMAIL_VIDEOS
        ).fetchall()
      return [dict(row) for row in rows]

  def mark_video_completed(self, video_id: str) -> bool:
    """Marks a pending video as COMPLETED and timestamps its email dispatch."""
    with self.get_connection() as conn:
      cur = conn.execute(DatabaseQueries.MARK_VIDEO_COMPLETED, (video_id,))
      conn.commit()
      return cur.rowcount > 0

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
    """Archives or updates a processed video, transcript, and summary in SQLite."""
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
              status,
          ),
      )
      conn.commit()

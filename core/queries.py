"""SQL queries and schema definitions for the TubeDigest SQLite database."""


class DatabaseQueries:
  """Centralized SQL query store for DatabaseManager."""

  # ----------------------------------------------------------------------------
  # DDL: Schema Initialization
  # ----------------------------------------------------------------------------
  CREATE_TABLES = """
    CREATE TABLE IF NOT EXISTS channels (
        channel_id          TEXT PRIMARY KEY,
        channel_name        TEXT,
        prompt_file         TEXT DEFAULT 'prompts/default_summary.txt',
        is_active           INTEGER DEFAULT 1,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_checked_at     TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS channel_authors (
        channel_id          TEXT PRIMARY KEY,
        author_name         TEXT,
        author_url          TEXT,
        channel_title       TEXT,
        custom_url          TEXT,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (channel_id) REFERENCES channels (channel_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS processed_videos (
        video_id            TEXT PRIMARY KEY,
        channel_id          TEXT NOT NULL,
        video_title         TEXT,
        video_url           TEXT,
        transcript          TEXT,
        summary_markdown    TEXT,
        status              TEXT DEFAULT 'COMPLETED',
        email_sent_at       TIMESTAMP,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (channel_id) REFERENCES channels (channel_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_processed_videos_channel ON processed_videos(channel_id);
    CREATE INDEX IF NOT EXISTS idx_channel_authors_name ON channel_authors(author_name);
  """

  # ----------------------------------------------------------------------------
  # Channel Queries
  # ----------------------------------------------------------------------------
  CHECK_CHANNEL_EXISTS = """
    SELECT channel_id FROM channels WHERE channel_id = ?
  """

  INSERT_CHANNEL = """
    INSERT INTO channels (channel_id, channel_name, prompt_file, is_active)
    VALUES (?, ?, COALESCE(?, 'prompts/default_summary.txt'), 1)
  """

  UPDATE_CHANNEL = """
    UPDATE channels 
    SET channel_name = COALESCE(?, channel_name),
        prompt_file = COALESCE(?, prompt_file),
        is_active = 1
    WHERE channel_id = ?
  """

  REMOVE_CHANNEL = """
    DELETE FROM channels WHERE channel_id = ?
  """

  LIST_CHANNELS = """
    SELECT 
        c.channel_id,
        c.channel_name,
        c.prompt_file,
        c.is_active,
        c.last_checked_at,
        a.author_name,
        a.author_url
    FROM channels c
    LEFT JOIN channel_authors a ON c.channel_id = a.channel_id
    ORDER BY c.is_active DESC, c.channel_name ASC, c.channel_id ASC
  """

  GET_ACTIVE_CHANNELS = """
    SELECT channel_id, channel_name, prompt_file 
    FROM channels 
    WHERE is_active = 1 
    ORDER BY channel_id ASC
  """

  UPDATE_CHANNEL_CHECKED = """
    UPDATE channels 
    SET last_checked_at = CURRENT_TIMESTAMP,
        channel_name = COALESCE(channel_name, ?)
    WHERE channel_id = ?
  """

  # ----------------------------------------------------------------------------
  # Channel Author Queries
  # ----------------------------------------------------------------------------
  UPSERT_CHANNEL_AUTHOR = """
    INSERT INTO channel_authors (
        channel_id, author_name, author_url, channel_title, custom_url, updated_at
    ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(channel_id) DO UPDATE SET
        author_name = COALESCE(excluded.author_name, channel_authors.author_name),
        author_url = COALESCE(excluded.author_url, channel_authors.author_url),
        channel_title = COALESCE(excluded.channel_title, channel_authors.channel_title),
        custom_url = COALESCE(excluded.custom_url, channel_authors.custom_url),
        updated_at = CURRENT_TIMESTAMP
  """

  GET_CHANNEL_AUTHOR = """
    SELECT channel_id, author_name, author_url, channel_title, custom_url, updated_at
    FROM channel_authors
    WHERE channel_id = ?
  """

  # ----------------------------------------------------------------------------
  # Video Archive Queries
  # ----------------------------------------------------------------------------
  IS_VIDEO_PROCESSED = """
    SELECT 1 FROM processed_videos WHERE video_id = ?
  """

  SAVE_PROCESSED_VIDEO = """
    INSERT OR REPLACE INTO processed_videos (
        video_id, channel_id, video_title, video_url, transcript, summary_markdown, status, email_sent_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
  """

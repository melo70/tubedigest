"""SQL queries and schema definitions for the TubeDigest SQLite database."""

from core.models import VideoStatus


class DatabaseQueries:
  """Centralized SQL query store for DatabaseManager."""

  DEFAULT_PROMPT_ID = "default"
  DEFAULT_PROMPT_TITLE = "Standard Markdown Summary"

  # ----------------------------------------------------------------------------
  # DDL: Schema Initialization
  # ----------------------------------------------------------------------------
  CREATE_TABLES = f"""
    CREATE TABLE IF NOT EXISTS prompts (
        prompt_id           TEXT PRIMARY KEY,
        prompt_title        TEXT,
        prompt_text         TEXT NOT NULL,
        email_template      TEXT,
        is_default          INTEGER DEFAULT 0,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS channels (
        channel_id          TEXT PRIMARY KEY,
        channel_name        TEXT,
        prompt_id           TEXT DEFAULT 'default',
        is_active           INTEGER DEFAULT 1,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_checked_at     TIMESTAMP,
        FOREIGN KEY (prompt_id) REFERENCES prompts (prompt_id)
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
        duration_seconds    INTEGER,
        transcript          TEXT,
        summary_markdown    TEXT,
        status              TEXT DEFAULT '{VideoStatus.COMPLETED}',
        email_sent_at       TIMESTAMP,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (channel_id) REFERENCES channels (channel_id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_processed_videos_channel ON processed_videos(channel_id);
    CREATE INDEX IF NOT EXISTS idx_channel_authors_name ON channel_authors(author_name);
  """

  # ----------------------------------------------------------------------------
  # Prompt Queries
  # ----------------------------------------------------------------------------
  SEED_DEFAULT_PROMPT = """
    INSERT OR IGNORE INTO prompts (prompt_id, prompt_title, prompt_text, email_template, is_default)
    VALUES (?, ?, ?, ?, 1)
  """

  LIST_PROMPTS = """
    SELECT prompt_id, prompt_title, is_default, prompt_text, email_template, updated_at
    FROM prompts
    ORDER BY is_default DESC, prompt_id ASC
  """

  GET_PROMPT = """
    SELECT prompt_text FROM prompts WHERE prompt_id = ?
  """

  GET_PROMPT_DETAILS = """
    SELECT prompt_id, prompt_title, is_default, prompt_text, email_template, created_at, updated_at
    FROM prompts
    WHERE prompt_id = ?
  """

  GET_DEFAULT_PROMPT = """
    SELECT prompt_text, email_template FROM prompts WHERE is_default = 1 LIMIT 1
  """

  UPSERT_PROMPT = """
    INSERT INTO prompts (prompt_id, prompt_title, prompt_text, email_template, is_default)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(prompt_id) DO UPDATE SET
        prompt_title = excluded.prompt_title,
        prompt_text = excluded.prompt_text,
        email_template = COALESCE(excluded.email_template, prompts.email_template),
        is_default = excluded.is_default,
        updated_at = CURRENT_TIMESTAMP
  """

  # ----------------------------------------------------------------------------
  # Channel Queries
  # ----------------------------------------------------------------------------
  CHECK_CHANNEL_EXISTS = """
    SELECT channel_id FROM channels WHERE channel_id = ?
  """

  INSERT_CHANNEL = """
    INSERT INTO channels (channel_id, channel_name, prompt_id, is_active)
    VALUES (?, ?, COALESCE(?, 'default'), 1)
  """

  UPDATE_CHANNEL = """
    UPDATE channels 
    SET channel_name = COALESCE(?, channel_name),
        prompt_id = COALESCE(?, prompt_id),
        is_active = 1
    WHERE channel_id = ?
  """

  SET_CHANNEL_ACTIVE = """
    UPDATE channels
    SET is_active = ?
    WHERE channel_id = ?
  """

  FIND_CHANNEL = """
    SELECT channel_id, channel_name FROM channels
    WHERE channel_id = ? OR channel_name = ?
    LIMIT 1
  """

  FIND_CHANNEL_BY_AUTHOR = """
    SELECT c.channel_id, c.channel_name, c.prompt_id, c.is_active
    FROM channels c
    JOIN channel_authors a ON c.channel_id = a.channel_id
    WHERE LOWER(a.author_name) = LOWER(?) 
       OR LOWER(a.channel_title) = LOWER(?)
    LIMIT 1
  """

  COUNT_CHANNEL_VIDEOS = """
    SELECT COUNT(*) FROM processed_videos WHERE channel_id = ?
  """

  COUNT_CHANNEL_AUTHORS = """
    SELECT COUNT(*) FROM channel_authors WHERE channel_id = ?
  """

  DELETE_CHANNEL_AUTHORS = """
    DELETE FROM channel_authors WHERE channel_id = ?
  """

  DELETE_CHANNEL_VIDEOS = """
    DELETE FROM processed_videos WHERE channel_id = ?
  """

  REMOVE_CHANNEL = """
    DELETE FROM channels WHERE channel_id = ?
  """

  LIST_CHANNELS = """
    SELECT 
        c.channel_id,
        c.channel_name,
        c.prompt_id,
        c.is_active,
        c.last_checked_at,
        a.author_name,
        a.author_url,
        p.prompt_title
    FROM channels c
    LEFT JOIN channel_authors a ON c.channel_id = a.channel_id
    LEFT JOIN prompts p ON c.prompt_id = p.prompt_id
    ORDER BY c.is_active DESC, c.channel_name ASC, c.channel_id ASC
  """

  GET_ACTIVE_CHANNELS = """
    SELECT channel_id, channel_name, prompt_id 
    FROM channels 
    WHERE is_active = 1 
    ORDER BY channel_id ASC
  """

  GET_CHANNEL = """
    SELECT channel_id, channel_name, prompt_id, is_active
    FROM channels
    WHERE channel_id = ? OR channel_name = ?
    LIMIT 1
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
  IS_VIDEO_PROCESSED = f"""
    SELECT 1 FROM processed_videos WHERE video_id = ? AND status = '{VideoStatus.COMPLETED}'
  """

  GET_PROCESSED_VIDEO = """
    SELECT 
        v.video_id, 
        v.channel_id, 
        COALESCE(c.channel_name, a.channel_title, a.author_name, v.channel_id) AS channel_name,
        COALESCE(a.author_name, c.channel_name, '-') AS author_name,
        v.video_title, 
        v.video_url, 
        v.duration_seconds,
        v.transcript, 
        v.summary_markdown, 
        v.status, 
        v.email_sent_at, 
        v.created_at
    FROM processed_videos v
    LEFT JOIN channels c ON v.channel_id = c.channel_id
    LEFT JOIN channel_authors a ON v.channel_id = a.channel_id
    WHERE v.video_id = ?
    LIMIT 1
  """

  LIST_PROCESSED_VIDEOS = """
    SELECT 
        v.video_id, 
        v.channel_id, 
        COALESCE(c.channel_name, a.channel_title, a.author_name, v.channel_id) AS channel_name,
        COALESCE(a.author_name, c.channel_name, '-') AS author_name,
        v.video_title, 
        v.video_url, 
        v.duration_seconds,
        LENGTH(COALESCE(v.transcript, '')) AS transcript_len,
        LENGTH(COALESCE(v.summary_markdown, '')) AS summary_len,
        v.status, 
        v.email_sent_at, 
        v.created_at
    FROM processed_videos v
    LEFT JOIN channels c ON v.channel_id = c.channel_id
    LEFT JOIN channel_authors a ON v.channel_id = a.channel_id
    ORDER BY v.created_at
  """

  GET_PENDING_EMAIL_VIDEOS = f"""
    SELECT video_id, channel_id, video_title, video_url, duration_seconds, transcript, summary_markdown, status, email_sent_at, created_at
    FROM processed_videos
    WHERE status = '{VideoStatus.PENDING_EMAIL}' AND channel_id = ?
    ORDER BY created_at ASC
  """

  GET_ALL_PENDING_EMAIL_VIDEOS = f"""
    SELECT video_id, channel_id, video_title, video_url, duration_seconds, transcript, summary_markdown, status, email_sent_at, created_at
    FROM processed_videos
    WHERE status = '{VideoStatus.PENDING_EMAIL}'
    ORDER BY created_at ASC
  """

  GET_PENDING_SUMMARY_VIDEOS = f"""
    SELECT video_id, channel_id, video_title, video_url, duration_seconds, transcript, summary_markdown, status, email_sent_at, created_at
    FROM processed_videos
    WHERE status = '{VideoStatus.PENDING_SUMMARY}' AND channel_id = ?
    ORDER BY created_at ASC
  """

  GET_ALL_PENDING_SUMMARY_VIDEOS = f"""
    SELECT video_id, channel_id, video_title, video_url, duration_seconds, transcript, summary_markdown, status, email_sent_at, created_at
    FROM processed_videos
    WHERE status = '{VideoStatus.PENDING_SUMMARY}'
    ORDER BY created_at ASC
  """

  MARK_VIDEO_COMPLETED = f"""
    UPDATE processed_videos
    SET status = '{VideoStatus.COMPLETED}',
        email_sent_at = CURRENT_TIMESTAMP
    WHERE video_id = ?
  """

  SAVE_PROCESSED_VIDEO = f"""
    INSERT INTO processed_videos (
        video_id, channel_id, video_title, video_url, duration_seconds, transcript, summary_markdown, status, email_sent_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = '{VideoStatus.COMPLETED}' THEN CURRENT_TIMESTAMP ELSE NULL END)
    ON CONFLICT(video_id) DO UPDATE SET
        channel_id = excluded.channel_id,
        video_title = COALESCE(excluded.video_title, processed_videos.video_title),
        video_url = COALESCE(excluded.video_url, processed_videos.video_url),
        duration_seconds = COALESCE(excluded.duration_seconds, processed_videos.duration_seconds),
        transcript = COALESCE(excluded.transcript, processed_videos.transcript),
        summary_markdown = COALESCE(excluded.summary_markdown, processed_videos.summary_markdown),
        status = excluded.status,
        email_sent_at = CASE WHEN excluded.status = '{VideoStatus.COMPLETED}' THEN CURRENT_TIMESTAMP ELSE processed_videos.email_sent_at END
  """

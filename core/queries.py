"""SQL queries and schema definitions for the TubeDigest SQLite database."""


class DatabaseQueries:
  """Centralized SQL query store for DatabaseManager."""

  DEFAULT_PROMPT_ID = "default"
  DEFAULT_PROMPT_TITLE = "Standard Markdown Summary"
  DEFAULT_PROMPT_TEXT = """Sei un assistente esperto nell'analisi di contenuti video. 
Analizza la trascrizione del video di YouTube dal titolo "{video_title}" fornita di seguito.

Genera un sunto approfondito e ben strutturato in lingua italiana, formattato rigorosamente in Markdown elegante e leggibile.
Usa questa struttura:
- Un titolo principale (`# {video_title}`)
- Una sezione `## Panoramica Generale` (2-3 frasi chiare)
- Una sezione `## Punti Chiave` (usa elenchi puntati con parole chiave in **grassetto**)
- Una sezione `## Conclusioni e Riflessioni`

Non aggiungere preamboli o commenti fuori dal Markdown.
Trascrizione:
{transcript}"""

  DEFAULT_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <style>
      body { font-family: Arial, sans-serif; color: #333; line-height: 1.6; }
      h1 { color: #1a73e8; font-size: 22px; border-bottom: 2px solid #1a73e8; padding-bottom: 5px; }
      h2, h3, h4 { color: #444; margin-top: 20px; }
      ul { padding-left: 20px; }
      strong { color: #000; }
      .video-box { text-align: center; margin-bottom: 20px; }
      .thumbnail { max-width: 100%; height: auto; border-radius: 6px; border: 1px solid #ccc; display: block; margin: 0 auto; }
      .container { background-color: #f9f9f9; padding: 20px; border-radius: 8px; border: 1px solid #ddd; }
      .footer-link { margin-top: 25px; padding-top: 15px; border-top: 1px solid #ddd; font-size: 14px; }
    </style>
  </head>
  <body>
    <h2>New video published!</h2>
    <hr style="border: none; border-top: 1px solid #ddd; margin: 15px 0;">
    <div class="video-box">
      <a href="{video_url}" target="_blank">
        <img src="{thumbnail_url}" alt="{subject}" class="thumbnail" />
      </a>
    </div>
    <div class="container">
      {html_body}
      <div class="footer-link">
        <a href="{video_url}" target="_blank">Watch video on YouTube</a>
      </div>
    </div>
  </body>
</html>"""

  # ----------------------------------------------------------------------------
  # DDL: Schema Initialization
  # ----------------------------------------------------------------------------
  CREATE_TABLES = """
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
  IS_VIDEO_PROCESSED = """
    SELECT 1 FROM processed_videos WHERE video_id = ?
  """

  SAVE_PROCESSED_VIDEO = """
    INSERT OR REPLACE INTO processed_videos (
        video_id, channel_id, video_title, video_url, transcript, summary_markdown, status, email_sent_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
  """

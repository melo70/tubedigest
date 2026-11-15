# TECHNICAL & FUNCTIONAL SPECIFICATIONS: TUBE-DIGEST PIPELINE

## 1. Project Overview

**TubeDigest** is a headless Python application designed for automated execution (e.g., via `cron` scheduler on Linux / Raspberry Pi systems). Its purpose is to monitor a target YouTube channel via an RSS feed, detect new video uploads, extract the textual transcript, generate a structured Markdown summary using the Google Gemini API, and deliver a formatted HTML email containing the video thumbnail and a direct link.

---

## 2. Architectural Requirements & Design Patterns

The software strictly adheres to standard software engineering principles:
* **Separation of Concerns (SoC)**: Clear separation between orchestration (`tubedigest.py`), internal application modules organized within the `core/` package, and external configuration (`config.toml`).
* **Single Responsibility Principle (SRP)**: Each class resides in a dedicated module with a single, well-defined responsibility (filesystem I/O and state persistence are separated from business logic and third-party API interactions).
* **Object-Oriented Programming (OOP)**: Logic encapsulation within dedicated `TubeDigest` and `StateManager` classes.
* **Zero Hardcoding**: No configuration parameters, credentials, file paths, model names, or prompts are hardcoded in the Python source code; everything is externally driven through the TOML configuration file.

---

## 3. Project Structure & Components

The project is structured with an internal `core/` package divided into the following files and directories:

```text
/tubedigest
│
├── config.toml              # Centralized configuration file (ignored by Git)
├── config.example.toml      # Configuration template with placeholder values
├── tubedigest               # Main executable entry point & CLI channel/prompt manager
├── templates/               # External default templates (prompts and email layout)
│   ├── default_prompt.txt
│   └── default_email.html
├── exports/                 # Export directory for Markdown video summaries (ignored by Git)
├── data/                    # Local SQLite database directory (ignored by Git)
│   └── .gitkeep
├── /core                    # Python package for internal application modules
│   ├── __init__.py          # Package initializer
│   ├── models.py            # Data models and lifecycle enumerated types (VideoStatus StrEnum)
│   ├── ui.py                # UI styling, ASCII art banner, Unicode box-drawing, and ANSI color support
│   ├── queries.py           # DatabaseQueries class (centralized SQL store)
│   ├── database.py          # DatabaseManager module (SQLite channels, authors, prompts, and archive)
│   ├── state_manager.py     # StateManager module (filesystem I/O and logging)
│   └── tube_digest.py       # TubeDigest module (RSS, Gemini API, SMTP email)
└── /logs                    # Output directory for execution logs
```

---

## 4. Detailed Component Specifications

### 4.1. Configuration File (`config.toml`)

The configuration file must contain the following sections and keys:

* `[youtube]`: `feed_url_template` (RSS feed URL template containing the `{channel_id}` placeholder).
* `[gemini]`: `api_key` (Google Gemini API key) and `model` (e.g., `gemini-2.5-flash`).
* `[email]`: SMTP parameters (`sender`, `password`, `receiver`, `smtp_server`, `smtp_port`).
* `[storage]`: File and directory paths (`db_path`, `logs_dir`, `log_file`, `log_max_bytes`, `log_backup_count`).

---

### 4.2. Database & SQL Architecture (`core/models.py`, `core/queries.py` & `core/database.py`)

Database logic is split between domain data types, a dedicated SQL query repository, and an operational manager:

* **`VideoStatus` (`core/models.py`)**: Type-safe `StrEnum` defining all video processing lifecycle states (`COMPLETED`, `PENDING_SUMMARY`, `PENDING_EMAIL`, `NO_TRANSCRIPT`), eliminating raw magic strings across the codebase.
* **`DatabaseQueries` (`core/queries.py`)**: Centralized repository containing all DDL and DML statements, isolating raw SQL from Python logic.
* **`DatabaseManager` (`core/database.py`)**: Executes queries, handles connections, transactions, and foreign keys.
* **Schema Tables**:
  * `prompts`: `prompt_id` (PK), `prompt_title`, `prompt_text`, `email_template`, `is_default`, `created_at`, `updated_at`.
  * `channels`: `channel_id` (PK), `channel_name`, `prompt_id` (FK -> prompts), `is_active`, `last_checked_at`, `created_at`.
  * `channel_authors`: `channel_id` (PK, FK -> channels), `author_name`, `author_url`, `channel_title`, `custom_url`, `updated_at`.
  * `processed_videos`: `video_id` (PK), `channel_id` (FK -> channels), `video_title`, `video_url`, `duration_seconds`, `transcript`, `summary_markdown`, `status`, `email_sent_at`, `created_at`.
* **Key Methods**:
  * `add_channel(...)`: Adds or reactivates a channel in SQLite linked to a `prompt_id` and auto-populates author metadata.
  * `set_channel_active(...)`: Enables (`is_active = 1`) or disables (`is_active = 0`) a channel by Channel ID or Name.
  * `find_channel_for_video(...)`: Locates a tracked channel record matching a video's channel ID, channel name, or author name.
  * `remove_channel(...)`: Explicit cascading delete of a channel and all associated records across tables (`channel_authors`, `processed_videos`) by Channel ID or Name.
  * `list_channels()`: Returns all channels joined with author and prompt metadata.
  * `list_prompts()`: Returns all stored prompt templates.
  * `get_prompt_details(...)`: Returns full record and template content for a prompt.
  * `get_prompt_text(...)`: Retrieves prompt text by ID or falls back to default.
  * `get_email_template(...)`: Retrieves email HTML layout template by prompt_id or falls back to default.
  * `upsert_channel_author(...)`: Automatically updates author biographical information when detected from RSS feeds.
  * `get_active_channels()`: Returns active channels for batch processing.
  * `is_video_processed(video_id)`: Instant index lookup preventing duplicate processing.
  * `get_processed_video(video_id)`: Returns stored video record including processing status, cached summary, and channel/author details.
  * `list_processed_videos()`: Returns all processed video records joined with channel and author metadata.
  * `remove_processed_video(video_id)`: Deletes an archived video record and its transcript/summary from SQLite by video ID, returning the deleted video's metadata or None if not found.
  * `get_pending_email_videos(...)`: Retrieves videos in `PENDING_EMAIL` status for email delivery recovery.
  * `get_pending_summary_videos(...)`: Retrieves videos in `PENDING_SUMMARY` status for AI summarization recovery with cached transcripts.
  * `mark_video_completed(video_id)`: Updates status to `COMPLETED` and stamps `email_sent_at`.
  * `save_processed_video(...)`: Archives the video, transcript, and generated summary with status (`COMPLETED`, `PENDING_EMAIL`, `PENDING_SUMMARY`, `NO_TRANSCRIPT`).

---

### 4.3. Logging Module (`core/state_manager.py` -> `StateManager`)

The `StateManager` class handles application execution logging with automatic rotation, level-based formatting, and ASCII art banner headers:

* **Initialization (`__init__`)**: Reads storage configuration, configures `BannerRotatingFileHandler` with configurable `max_bytes` and `backup_count`, and ensures new log files start with an ASCII art header banner.
* **`log_message(message)`**: Prints informational message to stdout and appends it to the rotated log file (e.g., `logs/tubedigest.log`) formatted as `[timestamp] [INFO] message`.
* **`log_error(message, exc=None)`**: Prints a user-friendly warning (`⚠ message`) to `stderr` and records technical error details and full stack trace (`exc_info=exc`) to the log file formatted as `[timestamp] [ERROR] message - Exception: ...`.

---

### 4.4. Business Logic Module (`core/tube_digest.py` -> `TubeDigest`)

The `TubeDigest` class encapsulates all interactions with external services:

* **Initialization (`__init__`)**: Receives the complete configuration dictionary and optional `StateManager` instance. Initializes the Google GenAI client (`genai.Client(api_key=...)`), sets the target Gemini model, SMTP credentials, and RSS template.
* **`_report_error(message, exc=None)`**: Dispatches user-friendly alerts to the terminal while recording complete tracebacks via `state_manager.log_error()`.
* **`get_latest_video()`**: Parses the YouTube RSS feed using `feedparser`. Detects feed/parsing failures via `feed.bozo` and `feed.bozo_exception`. Extracts the latest published video (`video_id`, `video_title`, `channel_title`, `author_info`). Returns `None` tuples upon failure without crashing.
* **`get_video_details(video_id)`**: Resolves video title, author, channel ID, and duration in seconds for an arbitrary YouTube video using standard oEmbed and watch page metadata extraction without requiring a YouTube Data API key.
* **`get_video_duration(video_id)`**: Retrieves exact video duration in seconds via watch page HTML player response (`lengthSeconds`, `approxDurationMs`, ISO 8601 duration) or subtitle timestamp fallbacks.
* **`get_transcript(video_id)`**: Extracts the text transcript using `youtube_transcript_api`. Catches exceptions (`TranscriptsDisabled`, `NoTranscriptFound`, network drops), logs the stack trace to the log file, and returns `None`.
* **`summarize_transcript(video_title, transcript, prompt_template)`**: Injects `video_title` and `transcript` into the template loaded from SQLite. Submits request via `client.models.generate_content`. If an API or quota error occurs, records the traceback and returns `None`; the pipeline caches the downloaded transcript into SQLite under `PENDING_SUMMARY` so it is safely retried on subsequent runs without re-downloading subtitles from YouTube.
* **`send_email(subject, markdown_content, video_url, video_id, email_template=None, channel_label=None, duration_str=None)`**: Converts Markdown content into HTML using `markdown`. Embeds the YouTube thumbnail (`https://img.youtube.com/vi/{video_id}/hqdefault.jpg`) and duration badge (`{duration}`) into the prompt's customized HTML layout loaded from SQLite and transmits the email via authenticated STARTTLS SMTP. Returns `True` on success and `False` on failure, preventing incomplete states from being marked as completed.

---

### 4.5. Main Orchestrator Script (`tubedigest`)

The main entry point coordinates CLI management and pipeline execution:

1. **Global Exception Interception (`sys.excepthook`)**: Captures unhandled crashes globally. Prevents terminal clutter by displaying polite error summaries on screen while logging complete diagnostic tracebacks as `[CRITICAL]` in `logs/tubedigest.log`.
2. **Early State & Logging Setup**: Loads `config.toml` and initializes `StateManager` so all subsequent operations are traced.
3. **Database Setup**: Connects to SQLite (`DatabaseManager`), handling channel and prompt migrations.
4. **CLI Handler**: Processes `--add-channel`, `--disable-channel` (or `--deactivate-channel`), `--enable-channel` (or `--activate-channel`), `--delete-channel` (or `--remove-channel`), `--list-channels`, `--list-prompts`, `--show-prompt`, `--video` (or `-v`), `--list-videos` (or `--list-summaries`), `--show-summary`, `--export-markdown` (or `--export-summary`), `--show-transcript`, and `--delete-video` (or `--remove-video`) arguments.
5. **Two-Tier Resilient Pipeline**: Iterates through active channels (or single target channel via `--channel` / `-c`, or target individual video via `--video`), executing a resilient two-tier recovery mechanism:
   * **Tier 1 (AI Recovery - `PENDING_SUMMARY`)**: Re-attempts Gemini summarization using SQLite-cached transcripts, eliminating unnecessary YouTube subtitle downloads.
   * **Tier 2 (Email Recovery - `PENDING_EMAIL`)**: Re-attempts SMTP delivery using SQLite-cached Markdown summaries, bypassing both YouTube downloads and Gemini API calls.
   * **New Uploads**: Detects latest RSS uploads, downloads transcripts, generates summaries, dispatches HTML emails, and archives state in SQLite.

---

### 4.6. UI & Terminal Presentation Module (`core/ui.py` -> `UI`)

The `UI` class centralizes all visual styling and TUI formatting:

* **Retro-Futuristic ASCII Art Header**: Stylized raster block banner for `TUBEDIGEST` with a smooth horizontal 3-stop RGB gradient (Cyan -> Magenta -> Coral) and prompt indicator (`>`).
* **Unicode Box-Drawing Tables**: Renders data tables with rounded corners (`╭─╮`, `╰─╯`, `│`, `├─┤`, `┼`) and aligned columns for channels, prompt templates, and video archives.
* **Card Panels**: Renders bordered card containers with embedded titles (`draw_panel`) and automated text wrapping to fit within terminal width.
* **Terminal Markdown Rendering Engine (`render_markdown`)**: Parses and renders Markdown syntax (headers, bold, italic, code, bullet/numbered lists with hanging indents, and wrapped Unicode comparison tables) into rich, beautifully formatted terminal output without third-party dependencies.
* **Status Badges & Bullets**: Minimalist bullet indicators matching modern TUIs (`● Active`, `○ Disabled`, `● Yes`, `○ No`, `● COMPLETED`, `⏳ PENDING_AI`, `⏳ PEND_EMAIL`, `○ NO_SUBS`).
* **ANSI Color Support & Safe Fallback**: Uses standard ANSI escape codes for colors, automatically disabling them when output is piped, redirected to a file, or when `NO_COLOR` is set.
* **Clean Logging Integration**: Automatically strips all ANSI escape codes before writing output to `logs/tubedigest.log`.

---

## 5. Constraints & External Dependencies (Tech Stack)

* **Language**: Python 3.11+
* **Required Third-Party Dependencies**:
  * `feedparser` (RSS feed parsing)
  * `youtube-transcript-api` (YouTube transcript extraction)
  * `google-genai` (Official Google GenAI SDK for Gemini models)
  * `markdown` (Markdown to HTML email conversion)
  * `tomli` (TOML parser fallback for Python < 3.11)
* **Automated Execution (Cron)**: The script is designed to run in headless Linux environments via `cron`, with proper working directory configuration (e.g., `cd /path/to/project && /path/to/venv/bin/python tubedigest.py`).

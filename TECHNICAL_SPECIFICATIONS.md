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
│   ├── i18n.py              # Internationalization module (I18nManager, Locale, and EmailLocalization)
│   ├── state_manager.py     # StateManager module (filesystem I/O and logging)
│   └── tube_digest.py       # TubeDigest module (RSS, Gemini API, SMTP email)
└── /logs                    # Output directory for execution logs
```

---

## 4. Detailed Component Specifications

### 4.1. Configuration File (`config.toml`)

The configuration file must contain the following sections and keys:

* `[general]`: `language` (default output summary and transcript priority language, e.g. `"en"`, `"it"`, `"es"`, `"zh"`, `"hi"`).
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
  * `channels`: `channel_id` (PK), `channel_name`, `prompt_id` (FK -> prompts), `output_language`, `is_active`, `last_checked_at`, `created_at`.
  * `channel_authors`: `channel_id` (PK, FK -> channels), `author_name`, `author_url`, `channel_title`, `custom_url`, `updated_at`.
  * `processed_videos`: `video_id` (PK), `channel_id` (FK -> channels), `video_title`, `video_url`, `duration_seconds`, `transcript`, `summary_markdown`, `status`, `email_sent_at`, `created_at`.
* **Key Methods**:
  * `add_channel(...)`: Adds or reactivates a channel in SQLite linked to a `prompt_id`, optional `output_language`, and auto-populates author metadata.
  * `set_channel_language(...)`: Sets or updates the output summary language for a channel by ID or Name.
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
* **`log_message(message, to_file=True)`**: Prints informational message to stdout and appends it to the rotated log file (e.g., `logs/tubedigest.log`) formatted as `[timestamp] [INFO] message`.
* **`print_screen(message)`**: Prints output directly to stdout without appending to the rotated log file, used for read-only CLI display commands (`--list-channels`, `--list-prompts`, `--show-prompt`, `--list-videos`, `--show-summary`, `--show-transcript`) to prevent log file clutter.
* **`log_error(message, exc=None)`**: Prints a user-friendly warning (`⚠ message`) to `stderr` and records technical error details and full stack trace (`exc_info=exc`) to the log file formatted as `[timestamp] [ERROR] message - Exception: ...`.

---

### 4.4. Business Logic Module (`core/tube_digest.py` -> `TubeDigest`)

The `TubeDigest` class encapsulates all interactions with external services:

* **Initialization (`__init__`)**: Receives the complete configuration dictionary and optional `StateManager` instance. Initializes the Google GenAI client (`genai.Client(api_key=...)`), sets the target Gemini model, SMTP credentials, and RSS template.
* **`_report_error(message, exc=None)`**: Dispatches user-friendly alerts to the terminal while recording complete tracebacks via `state_manager.log_error()`.
* **`_fetch_rss_feed(target_url, channel_id)`**: Fetches YouTube RSS feeds with browser headers (`User-Agent`, `Accept: application/atom+xml,application/xml,text/xml`) and 15s timeout. Intercepts Google consent redirects and HTML responses before parsing via `feedparser`, avoiding cryptic XML Expat parsing errors.
* **`fetch_channel_metadata(channel_id)`**: Retrieves channel title, creator/author name, and canonical channel URL directly from YouTube's Atom RSS feed.
* **`_resolve_channel_from_page(page_url)`**: Inspects YouTube channel pages (handles, vanity URLs, custom paths) to extract canonical `channelId`, `externalId`, `browseId`, or canonical `/channel/UC...` links along with page titles.
* **`resolve_channel_target(target)`**: Multi-input resolver accepting 24-character Channel IDs (`UC...`), channel URLs, handles (`@handle`), or arbitrary video URLs/IDs. Automatically extracts the underlying Channel ID and enriches it with channel title and author profile information without requiring a YouTube Data API key.
* **`get_latest_video()`**: Parses the YouTube RSS feed using `_fetch_rss_feed`. Extracts the latest published video (`video_id`, `video_title`, `channel_title`, `author_info`). Returns `None` tuples upon failure without crashing.
* **`get_video_details(video_id)`**: Resolves video title, author, channel ID, and duration in seconds for an arbitrary YouTube video using standard oEmbed and watch page metadata extraction without requiring a YouTube Data API key.
* **`get_video_duration(video_id)`**: Retrieves exact video duration in seconds via watch page HTML player response (`lengthSeconds`, `approxDurationMs`, ISO 8601 duration) or subtitle timestamp fallbacks.
* **`get_transcript(video_id, preferred_languages=None)`**: Extracts the text transcript using `youtube_transcript_api`. Prioritizes the channel's configured language, then system global language, then common fallbacks (`en`, `it`, `es`, `fr`, `de`), and ultimately falls back to the first available transcript in any language (manual or auto-generated). Logs exceptions to the log file and returns `None` if no transcript exists.
* **`summarize_transcript(video_title, transcript, prompt_template=None, output_language=None)`**: Injects `video_title`, `transcript`, and localized `{output_language}` into the template loaded from SQLite. If the template lacks `{output_language}`, appends a critical instruction to enforce the target output language. Submits request via `client.models.generate_content`. If an API or quota error occurs, records the traceback and returns `None`; the pipeline caches the downloaded transcript into SQLite under `PENDING_SUMMARY` so it is safely retried on subsequent runs without re-downloading subtitles from YouTube.
* **`send_email(subject, markdown_content, video_url, video_id, email_template=None, channel_label=None, duration_str=None)`**: Converts Markdown content into HTML using `markdown`. Embeds the YouTube thumbnail (`https://img.youtube.com/vi/{video_id}/hqdefault.jpg`) and duration badge (`{duration}`) into the prompt's customized HTML layout loaded from SQLite and transmits the email via authenticated STARTTLS SMTP. Returns `True` on success and `False` on failure, preventing incomplete states from being marked as completed.

---

### 4.5. Main Orchestrator Script (`tubedigest`)

The main entry point coordinates CLI management and pipeline execution:

1. **Global Exception Interception (`sys.excepthook`)**: Captures unhandled crashes globally. Prevents terminal clutter by displaying polite error summaries on screen while logging complete diagnostic tracebacks as `[CRITICAL]` in `logs/tubedigest.log`.
2. **Early State & Logging Setup**: Loads `config.toml` and initializes `StateManager` so all subsequent operations are traced.
3. **Database Setup**: Connects to SQLite (`DatabaseManager`), handling channel, prompt, and column migrations.
4. **CLI Handler**: Processes `--add-channel` (supporting `--lang`, `--prompt`, and automatic resolution from Channel ID, URL, handle, or any video URL/ID), `--set-language`, `--disable-channel` (or `--deactivate-channel`), `--enable-channel` (or `--activate-channel`), `--delete-channel` (or `--remove-channel`), `--list-channels`, `--list-prompts`, `--show-prompt`, `--add-video` (or `--video`, `-v`), `--list-videos` (or `--list-summaries`), `--show-video-details` (or `--video-details`, `--video-info`), `--show-summary`, `--export-markdown` (or `--export-summary`), `--show-transcript`, and `--delete-video` (or `--remove-video`) arguments.
5. **Two-Tier Resilient Pipeline**: Iterates through active channels (or single target channel via `--channel` / `-c`, or target individual video via `--add-video`), executing a resilient two-tier recovery mechanism:
   * **Tier 1 (AI Recovery - `PENDING_SUMMARY`)**: Re-attempts Gemini summarization using SQLite-cached transcripts, eliminating unnecessary YouTube subtitle downloads.
   * **Tier 2 (Email Recovery - `PENDING_EMAIL`)**: Re-attempts SMTP delivery using SQLite-cached Markdown summaries, bypassing both YouTube downloads and Gemini API calls.
   * **New Uploads**: Detects latest RSS uploads, downloads transcripts, generates summaries, dispatches HTML emails, and archives state in SQLite.

---

### 4.6. UI & Terminal Presentation Module (`core/ui.py` -> `UI`)

The `UI` class centralizes all visual styling and TUI formatting:

* **Retro-Futuristic ASCII Art Header**: Stylized raster block banner for `TUBEDIGEST` with a smooth horizontal 3-stop RGB gradient (Cyan -> Magenta -> Coral) and prompt indicator (`>`).
* **Unicode Box-Drawing Tables**: Renders data tables with rounded corners (`╭─╮`, `╰─╯`, `│`, `├─┤`, `┼`) and aligned columns for channels, prompt templates, and video archives.
* **Key-Value Inspection Tables (`draw_key_value_table`)**: Formats single-record details into two-column structured tables with clean vertical bar separators (`│`) between properties and values, featuring ANSI-aware and Unicode East Asian Width (emoji/wide character) cell calculation that guarantees exact border alignment and word wrapping without using `:` delimiters.
* **Card Panels**: Renders bordered card containers with embedded titles (`draw_panel`) and automated text wrapping to fit within terminal width.
* **Terminal Markdown Rendering Engine (`render_markdown`)**: Parses and renders Markdown syntax (headers, bold, italic, code, bullet/numbered lists with hanging indents, and wrapped Unicode comparison tables) into rich, beautifully formatted terminal output without third-party dependencies. Features ANSI-aware full text justification (`wrap_text`, `justify_line`) that aligns paragraphs and multi-line bullet lists flush with both margins while preserving left-aligned concluding lines.
* **Justified Email Typography**: Formats email HTML bodies with editorial full justification (`text-align: justify; text-justify: inter-word; hyphens: auto;`) across all prompt templates while keeping headings, lists, and tables cleanly left-aligned.
* **Status Badges & Bullets**: Minimalist bullet indicators matching modern TUIs (`● Active`, `○ Disabled`, `● Yes`, `○ No`, `● COMPLETED`, `⏳ PENDING_AI`, `⏳ PEND_EMAIL`, `○ NO_SUBS`).
* **ANSI Color Support & Safe Fallback**: Uses standard ANSI escape codes for colors, automatically disabling them when output is piped, redirected to a file, or when `NO_COLOR` is set, with opt-in support for `CLICOLOR_FORCE=1` / `FORCE_COLOR=1` when piping to pagers (`less -R`).
* **Clean Logging Integration**: Automatically strips all ANSI escape codes before writing output to `logs/tubedigest.log`.

---

### 4.7. Internationalization & Localization (`core/i18n.py`)

The internationalization architecture follows strict Object-Oriented and DDD (Domain-Driven Design) principles, avoiding loose global dictionaries:

* **`EmailLocalization` (`@dataclass(frozen=True)`)**: Immutable value object defining localized email UI elements (`heading`, `duration_label`, `watch_action`).
* **`Locale` (`@dataclass(frozen=True)`)**: Immutable value object encapsulating language metadata: ISO language code (`code`), human-readable display name (`display_name`), and email localization model (`email`).
* **`I18nManager`**: Centralized localization registry and service providing:
  * `DEFAULT_LANGUAGE`: Default fallback locale (`"en"`).
  * `_LOCALES`: Type-safe registry supporting 14 languages (`it`, `en`, `es`, `fr`, `de`, `zh`, `ja`, `hi`, `pt`, `ru`, `ar`, `ko`, `nl`, `pl`).
  * `get_locale(lang_code)`: Resolves a code to a `Locale` object, safely falling back to the default locale.
  * `get_display_name(lang_code)`: Returns descriptive language names (e.g., `"Italian (italiana)"`, `"Japanese (日本語)"`) for dynamic prompt injection.
  * `get_mandatory_instruction(lang_code)`: Generates strict LLM system prompts enforcing section header translation (`##`) matching the target output language.
  * `localize_email(template, target_lang)`: Pure method replacing dynamic template placeholders (`{email_heading}`, `{label_duration}`, `{label_watch}`) and adapting legacy static HTML templates without altering external files.
  * `list_supported_languages()`: Returns supported locale codes for validation.

---

## 5. Constraints & External Dependencies (Tech Stack)

### 5.1. Python Runtime & Compatibility Matrix

TubeDigest is engineered and validated for execution across modern Linux distributions (Debian Bookworm, Raspberry Pi OS, Ubuntu LTS, Fedora, Arch Linux).

| Python Version | Compatibility Status | Technical Constraints & Runtime Requirements |
| :--- | :---: | :--- |
| **Python $\le$ 3.10** | ❌ **Incompatible** | Hard dependency blockers: `google-genai` and `markdown` enforce `Requires-Python: >=3.11`. Standard library `tomllib` and `enum.StrEnum` are not present natively in Python $\le$ 3.10. |
| **Python 3.11.x** |  **Fully Supported** | Default interpreter on **Debian 12 Bookworm** and **Raspberry Pi OS**. Source code strictly conforms to pre-Python 3.12 syntax rules (no backslashes or nested quotes inside f-string `{...}` expression blocks). |
| **Python 3.12.x** |  **Fully Supported** | Default on **Ubuntu 24.04 LTS**. Full PEP 701 f-string formalization and performance optimizations. |
| **Python 3.13.x** |  **Fully Supported** | Primary development runtime. Validated with zero deprecation warnings. |
| **Python 3.14 - 3.15** | ⚠️ **Forward-Compatible** | Application code contains no deprecated constructs; operational availability depends on upstream C-extension wheel builds upon release. |
| **Python $\ge$ 3.16** | ❌ **Upper Limit** | Upstream constraint declared in `youtube-transcript-api` package metadata (`Requires-Python: <3.16`). |

### 5.2. Syntax Compatibility Safeguards

* **f-string PEP 701 Conformance**: In Python 3.11, expression segments inside `{...}` cannot contain backslashes (`\`). TubeDigest avoids nested f-strings with backslash escapes (e.g., `f"{tag} {UI.success(f'Video \'{title}\'')}"`), composing styled message fragments in separate variables to guarantee flawless execution on Python 3.11.2 (Raspberry Pi).
* **Typing Standards**: Uses standard `from typing import List, Optional, Dict, Any, Union` ensuring backward-compatibility across all supported Python versions without relying on Python 3.12+ exclusive typing statements.

### 5.3. Required Third-Party Dependencies

* `feedparser` (`>=3.10`): YouTube RSS feed parsing and metadata extraction.
* `youtube-transcript-api` (`>=3.8, <3.16`): YouTube transcript and subtitle extraction.
* `google-genai` (`>=3.11`): Official Google GenAI SDK for Gemini AI summarization models.
* `markdown` (`>=3.11`): Markdown to HTML email conversion.
* `tomli` (optional fallback): TOML parser fallback if `tomllib` is unavailable.

### 5.4. Automated Execution (Cron)

The script is designed to run in headless Linux environments via `cron`, with proper working directory configuration (e.g., `cd /path/to/project && /path/to/venv/bin/python tubedigest`).

### 5.5. Open-Source Licensing

TubeDigest is released as free, open-source software under the terms of the **GNU General Public License v3.0** (GPLv3). See [LICENSE](LICENSE) for terms and conditions.

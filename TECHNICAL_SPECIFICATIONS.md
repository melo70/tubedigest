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
├── tubedigest.py            # Main entry point & CLI channel manager
├── prompts/                 # Externalized prompt templates
│   └── default_summary.txt  # Default Gemini summarization prompt template
├── data/                    # Local SQLite database directory (ignored by Git)
│   └── .gitkeep
├── /core                    # Python package for internal application modules
│   ├── __init__.py          # Package initializer
│   ├── queries.py           # DatabaseQueries class (centralized SQL store)
│   ├── database.py          # DatabaseManager module (SQLite channels, authors, and archive)
│   ├── state_manager.py     # StateManager module (filesystem I/O and logging)
│   └── tube_digest.py       # TubeDigest module (RSS, Gemini API, SMTP email)
├── /transcripts             # Output directory for saving raw downloaded transcripts
└── /logs                    # Output directory for execution logs
```

---

## 4. Detailed Component Specifications

### 4.1. Configuration File (`config.toml`)

The configuration file must contain the following sections and keys:

* `[youtube]`: `feed_url_template` (RSS feed URL template containing the `{channel_id}` placeholder).
* `[gemini]`: `api_key` (Google Gemini API key), `model` (e.g., `gemini-2.5-flash`), and `prompt_file` (path to prompt template file, e.g. `prompts/default_summary.txt`).
* `[email]`: SMTP parameters (`sender`, `password`, `receiver`, `smtp_server`, `smtp_port`).
* `[storage]`: File and directory paths (`db_path`, `logs_dir`, `transcripts_dir`, `log_file`).

---

### 4.2. Database & SQL Architecture (`core/queries.py` & `core/database.py`)

Database logic is split between a dedicated SQL query repository and an operational manager:

* **`DatabaseQueries` (`core/queries.py`)**: Centralized repository containing all DDL and DML statements, isolating raw SQL from Python logic.
* **`DatabaseManager` (`core/database.py`)**: Executes queries, handles connections, transactions, and foreign keys.
* **Schema Tables**:
  * `channels`: `channel_id` (PK), `channel_name`, `prompt_file`, `is_active`, `last_checked_at`, `created_at`.
  * `channel_authors`: `channel_id` (PK, FK -> channels), `author_name`, `author_url`, `channel_title`, `custom_url`, `updated_at`.
  * `processed_videos`: `video_id` (PK), `channel_id` (FK -> channels), `video_title`, `video_url`, `transcript`, `summary_markdown`, `status`, `email_sent_at`, `created_at`.
* **Key Methods**:
  * `add_channel(...)`: Adds or reactivates a channel in SQLite.
  * `remove_channel(...)`: Cascading delete of a channel and associated records.
  * `list_channels()`: Returns all channels joined with author metadata.
  * `upsert_channel_author(...)`: Automatically updates author biographical information when detected from RSS feeds.
  * `get_active_channels()`: Returns active channels for batch processing.
  * `is_video_processed(video_id)`: Instant index lookup preventing duplicate processing.
  * `save_processed_video(...)`: Archives the video, transcript, and generated summary.

---

### 4.3. State and Logging Module (`core/state_manager.py` -> `StateManager`)

The `StateManager` class handles filesystem I/O, state persistence, and logging exclusively:

* **Initialization (`__init__`)**: Reads storage configuration, resolves paths, and ensures automatic directory creation (`logs_dir`, `transcripts_dir`) if they do not already exist via `os.makedirs(..., exist_ok=True)`.
* **`load_last_id()`**: Reads the ID of the last processed video from the state file. Returns `None` if the file does not exist.
* **`save_last_id(video_id)`**: Writes and persists the ID of the last processed video to the state file.
* **`save_transcript(video_id, transcript_text)`**: Saves the raw transcript as a `.txt` file inside the configured transcripts directory, named `{video_id}.txt`.
* **`log_message(message)`**: Prints the message to stdout and appends it to the configured log file (e.g., `logs/tubedigest.log`) prefixed with a formatted timestamp (`%Y-%m-%d %H:%M:%S`).

---

### 4.3. Business Logic Module (`core/tube_digest.py` -> `TubeDigest`)

The `TubeDigest` class encapsulates all interactions with external services:

* **Initialization (`__init__`)**: Receives the complete configuration dictionary, constructs the RSS feed URL from the template and channel ID, initializes the Google GenAI client (`genai.Client(api_key=...)`), sets the target Gemini model, SMTP credentials, and summarization prompt template.
* **`get_latest_video()`**: Parses the YouTube RSS feed using `feedparser`. Extracts the latest published video by retrieving its unique ID from the Atom ID string (`latest.id.split(":")[-1]`), returning `link`, `title`, `video_id`, and `channel_title`. Gracefully catches exceptions, returning tuples of `None` on errors.
* **`get_transcript(video_id)`**: Extracts the text transcript using `youtube_transcript_api` with validated object-based syntax:

```python
ytt_api = YouTubeTranscriptApi()
fetched_data = ytt_api.fetch(video_id, languages=["it", "en"])
full_text = " ".join([snippet.text for snippet in fetched_data])
return full_text
```

Catches exceptions (`try-except`) and returns `None` if no transcript is available.

* **`summarize_transcript(video_title, transcript)`**: Formats the prompt by dynamically injecting `video_title` and `transcript` into the template configured in TOML. Submits the request to the Gemini model using the SDK client (`client.models.generate_content`) and returns the generated Markdown response text.
* **`send_email(subject, markdown_content, video_url, video_id)`**: Converts Markdown content into HTML using the `markdown` library (with `extra` and `nl2br` extensions). Builds a multipart email message (`MIMEMultipart("alternative")`) embedding the YouTube video preview thumbnail (`https://img.youtube.com/vi/{video_id}/hqdefault.jpg`), and transmits the email through the secure SMTP server using STARTTLS with custom SSL context handling.

---

### 4.4. Main Orchestrator Script (`tubedigest.py`)

The main entry point imports components from the internal package (`from core.state_manager import StateManager` and `from core.tube_digest import TubeDigest`) and coordinates the execution flow:

1. Verifies the existence of `config.toml`.
2. Loads configuration parameters (using native `tomllib` in Python 3.11+, with fallback to `tomli`).
3. Instantiates `StateManager` and `TubeDigest`.
4. Executes the pipeline step-by-step, logging every stage via `state_manager.log_message()`:
   * Checks the YouTube RSS feed for the latest video.
   * Compares the video ID against the persisted state (`load_last_id()`). Exits cleanly if IDs match (no new video to process).
   * Downloads the video transcript (`get_transcript()`).
   * Saves a local copy of the raw transcript (`save_transcript()`).
   * Generates the structured summary with Gemini (`summarize_transcript()`).
   * Sends the HTML email digest (`send_email()`).
   * Updates the persistent state file (`save_last_id()`).

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

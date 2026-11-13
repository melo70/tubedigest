# TubeDigest 📺 ✉️ 🤖

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![AI Powered](https://img.shields.io/badge/AI-Google%20Gemini-orange.svg)](https://ai.google.dev/)
[![Database](https://img.shields.io/badge/Database-SQLite3-green.svg)](https://www.sqlite.org/)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()

**TubeDigest** is a lightweight, headless Python automation pipeline designed to run seamlessly on Linux servers or Raspberry Pi devices. 

It continuously monitors multiple YouTube channels via RSS feeds, downloads new video transcripts, produces structured, high-quality Markdown summaries using the Google Gemini API, and dispatches formatted HTML email digests directly to your inbox. All channel subscriptions, transcripts, and summaries are persistently managed through a lightweight local **SQLite** database.

---

## 🚀 Key Features

* **Multi-Channel Management**: Monitor as many YouTube channels as you want, easily managed via CLI commands.
* **Quota-Free Channel Tracking**: Monitors YouTube channels via standard RSS feeds—no complex YouTube Data API credentials or quota limits required.
* **Automatic Transcript Extraction**: Pulls subtitle and caption tracks automatically using `youtube-transcript-api` (supporting language fallbacks).
* **AI-Powered Summarization**: Generates insightful, structured summaries powered by Google's Gemini models (`gemini-2.5-flash`, `gemini-3.6-flash`, etc.).
* **Database-Driven Prompt Templates**: Prompt templates reside directly in SQLite (`prompts` table), allowing custom prompts per channel with zero loose files.
* **Built-in SQLite Storage**: Saves channel authors, prompts, transcripts, generated summaries, and channel states in a local SQLite database (`data/tubedigest.db`)—avoiding re-processing and saving AI tokens.
* **Separated Query Architecture**: All SQL statements reside in a dedicated `DatabaseQueries` class for clean maintainability.
* **Rich HTML Email Digests**: Delivers clean, responsive emails with video thumbnails, key takeaways in Markdown format, and direct YouTube links.
* **Headless & Cron-Ready**: Built for automated background execution on home servers, Linux VPS, or Raspberry Pi boards.

---

## 📁 Project Structure

```text
tubedigest/
├── config.example.toml      # Configuration template with placeholder values
├── config.toml              # Your active configuration (ignored by Git)
├── tubedigest.py            # Main application entry point & CLI manager
├── requirements.txt         # Python package dependencies
├── TECHNICAL_SPECIFICATIONS.md # Detailed architecture and engineering specs
├── data/                    # Local SQLite database directory (ignored by Git)
│   └── .gitkeep
├── core/
│   ├── __init__.py
│   ├── queries.py           # Centralized DatabaseQueries SQL store
│   ├── database.py          # SQLite DatabaseManager for channels, authors, prompts, and archives
│   ├── state_manager.py     # Handles filesystem I/O and execution logs
│   └── tube_digest.py       # Core logic: RSS parsing, Gemini client, SMTP dispatch
└── logs/                    # Timestamped execution log files
```

---

## 🛠️ Prerequisites

* **Python 3.11 or higher**
* A **Google Gemini API Key** (obtainable for free at [Google AI Studio](https://aistudio.google.com/))
* An **SMTP-enabled email account** (e.g., Gmail with an [App Password](https://myaccount.google.com/apppasswords))

---

## 📦 Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/melo70/tubedigest.git
cd tubedigest
```

### 2. Create and Activate a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Application Settings

Copy the sample configuration file to `config.toml`:

```bash
cp config.example.toml config.toml
```

Edit `config.toml` with your credentials:

```toml
[youtube]
feed_url_template = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

[email]
sender = "your.email@gmail.com"
password = "your-16-char-app-password"
receiver = "destination.email@gmail.com"
smtp_server = "smtp.gmail.com"
smtp_port = 587

[storage]
db_path = "data/tubedigest.db"
logs_dir = "logs"
log_file = "tubedigest.log"

[gemini]
api_key = "YOUR_GEMINI_API_KEY"
model = "gemini-2.5-flash"
```

---

## 📺 Channel & Prompt Management (CLI)

Manage your monitored channels and prompt templates directly from the command line:

### Add a Channel
```bash
python tubedigest.py --add-channel <CHANNEL_ID> --name "Channel Name"
```
*(Optional: specify `--prompt <PROMPT_ID>` to assign a specific prompt template, defaults to `'default'`).*

### List Tracked Channels
```bash
python tubedigest.py --list-channels
```

### List Stored AI Prompts
```bash
python tubedigest.py --list-prompts
```

### Remove a Channel
```bash
python tubedigest.py --remove-channel <CHANNEL_ID>
```

---

## 🧪 Running the Pipeline

Run the pipeline manually to process all active channels:

```bash
python tubedigest.py
```

### Expected Behavior:
* For each active channel, TubeDigest checks the latest video via RSS.
* If a new video is found and has not been archived in SQLite, it downloads the transcript, requests Gemini for a Markdown summary, sends the email, and archives the video in SQLite.
* If the video has already been processed, it skips processing instantly (consuming 0 Gemini tokens and sending no duplicate emails).

---

## ⏰ Automated Scheduling (Cron)

To monitor channels automatically in the background, set up a `cron` job on your Linux system.

1. Open your crontab editor:
   ```bash
   crontab -e
   ```

2. Add a schedule (for example, running every 2 hours):
   ```cron
   0 */2 * * * cd /path/to/tubedigest && /path/to/tubedigest/.venv/bin/python tubedigest.py >> /path/to/tubedigest/logs/cron.log 2>&1
   ```
   *(Make sure to replace `/path/to/tubedigest` with the actual absolute path to your project).*

---

## 🔒 Security Best Practices

* **Never commit `config.toml` or `*.db`**: The included `.gitignore` protects your private API keys, email credentials, and local database.
* **Use App Passwords**: When using Gmail or other providers, always generate dedicated Application Passwords rather than using your main account password.

---

## 📄 License

License information will be specified soon.

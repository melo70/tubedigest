# TubeDigest 📺 ✉️ 🤖

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![AI Powered](https://img.shields.io/badge/AI-Google%20Gemini-orange.svg)](https://ai.google.dev/)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()

**TubeDigest** is a lightweight, headless Python automation pipeline designed to run seamlessly on Linux servers or Raspberry Pi devices. 

It continuously monitors your favorite YouTube channels via RSS feeds, downloads new video transcripts, produces structured, high-quality Markdown summaries using the Google Gemini API, and dispatches formatted HTML email digests directly to your inbox.

---

## 🚀 Key Features

* **Quota-Free Channel Tracking**: Monitors YouTube channels via standard RSS feeds—no complex YouTube Data API credentials or quota limits required.
* **Automatic Transcript Extraction**: Pulls subtitle and caption tracks automatically using `youtube-transcript-api` (supporting language fallbacks).
* **AI-Powered Summarization**: Generates insightful, well-structured summaries powered by Google's Gemini models (`gemini-2.5-flash`, `gemini-3.6-flash`, etc.).
* **Rich HTML Email Digests**: Delivers clean, responsive emails with video thumbnails, key takeaways in Markdown format, and direct YouTube links.
* **Smart State Persistence**: Tracks the last processed video ID to guarantee that each video is processed and emailed exactly once.
* **Headless & Cron-Ready**: Built for background execution on home servers, Linux VPS, or Raspberry Pi boards.
* **Modular Architecture & Zero Hardcoding**: Fully configurable via an external `config.toml` file with clean separation of concerns.

---

## 📁 Project Structure

```text
tubedigest/
├── config.example.toml      # Configuration template with placeholder values
├── config.toml              # Your active configuration (ignored by Git)
├── tubedigest.py            # Main application entry point & orchestrator
├── requirements.txt         # Python package dependencies
├── TECHNICAL_SPECIFICATIONS.md # Detailed architecture and engineering specs
├── core/
│   ├── __init__.py
│   ├── state_manager.py     # Handles I/O, state persistence, and logging
│   └── tube_digest.py       # Core logic: RSS parsing, Gemini client, SMTP dispatch
├── transcripts/             # Saved raw video transcript text archives
└── logs/                    # Timestamped execution log files
```

---

## 🛠️ Prerequisites

* **Python 3.11 or higher**
* A **Google Gemini API Key** (obtainable for free at [Google AI Studio](https://aistudio.google.com/))
* An **SMTP-enabled email account** (e.g., Gmail with an [App Password](https://myaccount.google.com/apppasswords))
* The **Channel ID** of the YouTube channel you want to monitor (e.g., `UC...`)

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

Edit `config.toml` with your favorite text editor (e.g., `nano config.toml`):

```toml
[youtube]
# 24-character YouTube Channel ID to monitor
channel_id = "UCxxxxxxxxxxxxxxxxxxxxxx"
feed_url_template = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

[email]
sender = "your.email@gmail.com"
password = "your-16-char-app-password"
receiver = "destination.email@gmail.com"
smtp_server = "smtp.gmail.com"
smtp_port = 587

[storage]
last_id_file = "last_video_id.txt"
logs_dir = "logs"
transcripts_dir = "transcripts"
log_file = "tubedigest.log"

[gemini]
api_key = "YOUR_GEMINI_API_KEY"
model = "gemini-2.5-flash"
prompt = """
Sei un assistente esperto nell'analisi di contenuti video. 
Analizza la trascrizione del video di YouTube dal titolo "{video_title}" fornita di seguito...
"""
```

---

## 🧪 Testing Your Setup

Run the script manually to ensure everything is configured properly:

```bash
python tubedigest.py
```

### Expected Behavior:
* If a new video is found, TubeDigest will download its transcript, call Gemini to generate the summary, send the email digest, and record the video ID in `last_video_id.txt`.
* If no new video has been published since the last run, it will exit cleanly:
  ```text
  Checking for new videos...
  No new video detected since last check.
  ```

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

* **Never commit `config.toml`**: The included `.gitignore` protects your private API keys and email passwords from being tracked.
* **Use App Passwords**: When using Gmail or other providers, always generate dedicated Application Passwords rather than using your main account password.

---

## 📄 License

License information will be specified soon.

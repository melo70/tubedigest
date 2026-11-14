import os
import smtplib
import ssl
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import feedparser
import markdown
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai

class StateManager:
  """Manages state persistence, transcripts, and execution logs."""

  def __init__(self, storage):
    self.last_id_file = storage.get(
        "last_id_file", "last_video_id.txt"
    )
    self.logs_dir = storage.get("logs_dir", "logs")
    self.transcripts_dir = storage.get("transcripts_dir", "transcripts")
    self.log_file_name = storage.get("log_file", "app.log")

    # Create directories if they do not exist
    os.makedirs(self.logs_dir, exist_ok=True)
    os.makedirs(self.transcripts_dir, exist_ok=True)

    self.log_path = os.path.join(self.logs_dir, self.log_file_name)

  def load_last_id(self):
    """Reads the ID of the last processed video from file."""
    if os.path.exists(self.last_id_file):
      with open(self.last_id_file, "r", encoding="utf-8") as f:
        return f.read().strip()
    return None

  def save_last_id(self, video_id):
    """Saves the ID of the last processed video to file."""
    with open(self.last_id_file, "w", encoding="utf-8") as f:
      f.write(video_id)

  def save_transcript(self, video_id, transcript_text):
    """Saves the transcript to a dedicated text file."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    file_path = os.path.join(self.transcripts_dir, f"{timestamp}_{video_id}.txt")
    with open(file_path, "w", encoding="utf-8") as f:
      f.write(transcript_text)

  def log_message(self, message):
    """Writes a timestamped log message to the configured log file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    print(message)  # Also print to stdout (useful for cron/terminal)
    with open(self.log_path, "a", encoding="utf-8") as f:
      f.write(log_line)

class TubeDigest:

  def __init__(self, config):
    """Initializes the client and configuration parameters."""
    yt_config = config.get("youtube", {})
    if "channel_id" in yt_config and "feed_url_template" in yt_config:
      self.rss_url = yt_config["feed_url_template"].format(
          channel_id=yt_config["channel_id"]
      )
    elif "channel_rss_url" in yt_config:
      self.rss_url = yt_config["channel_rss_url"]
    else:
      raise KeyError(
          "Missing 'youtube' configuration: specify 'channel_id' and 'feed_url_template' or 'channel_rss_url'."
      )

    self.gemini_api_key = config["gemini"]["api_key"]
    self.gemini_model = config["gemini"]["model"]
    self.gemini_prompt = config["gemini"]["prompt"]

    self.sender = config["email"]["sender"]
    self.password = config["email"]["password"]
    self.receiver = config["email"]["receiver"]
    self.smtp_server = config["email"]["smtp_server"]
    self.smtp_port = config["email"]["smtp_port"]

    self.client = genai.Client(api_key=self.gemini_api_key)

  def get_latest_video(self):
    """Checks the latest published video via RSS."""
    try:
      feed = feedparser.parse(self.rss_url)
      if feed.entries:
        latest = feed.entries[0]
        video_id = latest.id.split(":")[-1]
        channel_title = feed.feed.get("title", "YouTube")
        return latest.link, latest.title, video_id, channel_title
    except Exception as e:
      print(f"Error checking RSS feed: {e}")
    return None, None, None, None

  def get_transcript(self, video_id):
    """Downloads the video transcript using the object-based API."""
    try:
      ytt_api = YouTubeTranscriptApi()
      fetched_data = ytt_api.fetch(video_id, languages=["it", "en"])

      # Extract text by reading the .text attribute of each snippet
      full_text = " ".join([snippet.text for snippet in fetched_data])
      return full_text
    except Exception as e:
      print(f"Unable to download transcript for {video_id}: {e}")
      return None

  def summarize_transcript(self, video_title, transcript):
    """Generates a structured summary using Gemini."""
    prompt = self.gemini_prompt.format(video_title=video_title, transcript=transcript)

    try:
      response = self.client.models.generate_content(
          model=self.gemini_model,
          contents=prompt,
      )
      return response.text
    except Exception as e:
      print(f"Error generating summary with Gemini: {e}")
      return "Error generating summary."

  def send_email(self, subject, markdown_content, video_url, video_id, email_template=None):
    """Sends a formatted HTML email with thumbnail and video link."""
    try:
      html_body = markdown.markdown(
          markdown_content, extensions=["extra", "nl2br", "table", "sane_lists"]
      )
      thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

      template = email_template or """<!DOCTYPE html>
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

      email_html = (
          template.replace("{subject}", subject)
          .replace("{video_url}", video_url)
          .replace("{thumbnail_url}", thumbnail_url)
          .replace("{html_body}", html_body)
          .replace("{video_id}", video_id)
      )

      msg = MIMEMultipart("alternative")
      msg["Subject"] = subject
      msg["From"] = self.sender
      msg["To"] = self.receiver
      msg.attach(MIMEText(email_html, "html"))

      context = ssl.create_default_context()
      context.check_hostname = False
      context.verify_mode = ssl.CERT_NONE

      server = smtplib.SMTP(self.smtp_server, self.smtp_port)
      server.ehlo()
      server.starttls(context=context)
      server.ehlo()
      server.login(self.sender, self.password)
      server.sendmail(self.sender, self.receiver, msg.as_string())
      server.quit()

      print("Email sent successfully!")
    except Exception as e:
      print(f"Error sending email: {e}")

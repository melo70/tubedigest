import os
import smtplib
import ssl
from typing import Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import feedparser
import markdown
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai


class TubeDigest:

  def __init__(self, config):
    """Initializes the client and configuration parameters."""
    yt_config = config.get("youtube", {})
    self.feed_url_template = yt_config.get(
        "feed_url_template",
        "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
    )
    self.default_channel_id = yt_config.get("channel_id")
    self.rss_url = yt_config.get("channel_rss_url")
    if not self.rss_url and self.default_channel_id:
      self.rss_url = self.feed_url_template.format(
          channel_id=self.default_channel_id
      )

    gemini_cfg = config.get("gemini", {})
    self.gemini_api_key = gemini_cfg.get("api_key")
    self.gemini_model = gemini_cfg.get("model", "gemini-2.5-flash")

    # Load prompt template from file or fallback to inline/default
    self.default_prompt = self._load_prompt(
        gemini_cfg.get("prompt_file", "prompts/default_summary.txt"),
        inline_fallback=gemini_cfg.get("prompt"),
    )

    email_cfg = config.get("email", {})
    self.sender = email_cfg.get("sender")
    self.password = email_cfg.get("password")
    self.receiver = email_cfg.get("receiver")
    self.smtp_server = email_cfg.get("smtp_server")
    self.smtp_port = email_cfg.get("smtp_port", 587)

    self.client = genai.Client(api_key=self.gemini_api_key)

  def _load_prompt(self, file_path: Optional[str] = None, inline_fallback: Optional[str] = None) -> str:
    """Loads prompt template from file, or returns inline fallback."""
    if file_path and os.path.exists(file_path):
      try:
        with open(file_path, "r", encoding="utf-8") as f:
          return f.read()
      except Exception as e:
        print(f"Warning: Failed to read prompt file '{file_path}': {e}")

    if inline_fallback:
      return inline_fallback

    # Minimal default prompt if nothing else is available
    return (
        "Summarize the following YouTube transcript for the video titled"
        " '{video_title}'.\n\nTranscript:\n{transcript}"
    )

  def get_latest_video(self, channel_id: Optional[str] = None):
    """Checks the latest published video via RSS for the given channel_id."""
    target_url = None
    if channel_id:
      target_url = self.feed_url_template.format(channel_id=channel_id)
    elif self.rss_url:
      target_url = self.rss_url
    else:
      print("Error: No channel_id or RSS URL provided.")
      return None, None, None, None, None

    try:
      feed = feedparser.parse(target_url)
      channel_title = feed.feed.get("title", "YouTube")
      author_detail = feed.feed.get("author_detail", {})
      author_name = feed.feed.get("author") or author_detail.get("name") or channel_title
      author_url = author_detail.get("href") or (
          f"https://www.youtube.com/channel/{channel_id}" if channel_id else None
      )
      author_info = {
          "author_name": author_name,
          "author_url": author_url,
          "channel_title": channel_title,
      }

      if feed.entries:
        latest = feed.entries[0]
        video_id = latest.id.split(":")[-1]
        return latest.link, latest.title, video_id, channel_title, author_info
      return None, None, None, channel_title, author_info
    except Exception as e:
      print(f"Error checking RSS feed for {channel_id or target_url}: {e}")
    return None, None, None, None, None

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

  def summarize_transcript(self, video_title, transcript, prompt_file: Optional[str] = None):
    """Generates a structured summary using Gemini, with optional custom prompt file."""
    prompt_template = self._load_prompt(prompt_file) if prompt_file else self.default_prompt
    prompt = prompt_template.format(video_title=video_title, transcript=transcript)

    try:
      response = self.client.models.generate_content(
          model=self.gemini_model,
          contents=prompt,
      )
      return response.text
    except Exception as e:
      print(f"Error generating summary with Gemini: {e}")
      return "Error generating summary."

  def send_email(self, subject, markdown_content, video_url, video_id):
    """Sends a formatted HTML email with thumbnail and video link."""
    try:
      html_body = markdown.markdown(
          markdown_content, extensions=["extra", "nl2br"]
      )
      thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

      email_html = f"""
            <html>
              <head>
                <style>
                  body {{ font-family: Arial, sans-serif; color: #333; line-height: 1.6; }}
                  h1 {{ color: #1a73e8; font-size: 22px; border-bottom: 2px solid #1a73e8; padding-bottom: 5px; }}
                  h2, h3, h4 {{ color: #444; margin-top: 20px; }}
                  ul {{ padding-left: 20px; }}
                  strong {{ color: #000; }}
                  .video-box {{ text-align: center; margin-bottom: 20px; }}
                  .thumbnail {{ max-width: 100%; height: auto; border-radius: 6px; border: 1px solid #ccc; display: block; margin: 0 auto; }}
                  .container {{ background-color: #f9f9f9; padding: 20px; border-radius: 8px; border: 1px solid #ddd; }}
                  .footer-link {{ margin-top: 25px; padding-top: 15px; border-top: 1px solid #ddd; font-size: 14px; }}
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
            </html>
            """

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

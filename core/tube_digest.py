import json
import re
import smtplib
import ssl
import sys
import urllib.request
from typing import Optional, Dict, Any, Tuple
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import feedparser
import markdown
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from core.ui import UI


class TubeDigest:

  def __init__(self, config: Dict[str, Any], state_manager=None):
    """Initializes the client and configuration parameters."""
    self.state_manager = state_manager

    yt_config = config.get("youtube", {})
    self.feed_url_template = yt_config.get(
        "feed_url_template",
        "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
    )

    gemini_cfg = config.get("gemini", {})
    self.gemini_api_key = gemini_cfg.get("api_key")
    self.gemini_model = gemini_cfg.get("model", "gemini-2.5-flash")

    email_cfg = config.get("email", {})
    self.sender = email_cfg.get("sender")
    self.password = email_cfg.get("password")
    self.receiver = email_cfg.get("receiver")
    self.smtp_server = email_cfg.get("smtp_server")
    self.smtp_port = email_cfg.get("smtp_port", 587)

    self.client = genai.Client(api_key=self.gemini_api_key)

  def _report_error(self, message: str, exc: Optional[BaseException] = None):
    """Dispatches human-friendly message to stderr and full exception/traceback to the log file."""
    if self.state_manager:
      self.state_manager.log_error(message, exc=exc)
    else:
      print(f"⚠ {message}", file=sys.stderr)

  def fetch_channel_metadata(
      self, channel_id: str
  ) -> Optional[Dict[str, str]]:
    """Fetches channel title and author profile information via RSS feed."""
    if not channel_id:
      return None

    target_url = self.feed_url_template.format(channel_id=channel_id)
    try:
      feed = feedparser.parse(target_url)
      if getattr(feed, "bozo", 0) and getattr(feed, "bozo_exception", None) and not feed.entries:
        return None

      channel_title = feed.feed.get("title")
      author_detail = feed.feed.get("author_detail", {})
      author_name = feed.feed.get("author") or author_detail.get("name") or channel_title
      author_url = author_detail.get("href") or f"https://www.youtube.com/channel/{channel_id}"

      if not channel_title and not author_name:
        return None

      return {
          "channel_title": channel_title,
          "author_name": author_name,
          "author_url": author_url,
      }
    except Exception as e:
      self._report_error(
          f"Could not retrieve channel metadata for '{channel_id}'.",
          exc=e,
      )
      return None

  def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves metadata (channel_id, title, author_name) for a specific YouTube video."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
    }

    title = None
    channel_id = None
    author_name = None
    author_url = None

    # 1. Query standard public oEmbed endpoint for title and author info
    oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"
    try:
      req = urllib.request.Request(oembed_url, headers=headers)
      with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        title = data.get("title")
        author_name = data.get("author_name")
        author_url = data.get("author_url", "")
        if "/channel/" in author_url:
          channel_id = author_url.split("/channel/")[-1].split("/")[0].split("?")[0]
    except Exception as e:
      self._report_error(f"oEmbed metadata lookup failed for video '{video_id}'.", exc=e)

    # 2. If channel_id is not yet resolved, inspect watch page HTML headers
    if not channel_id:
      try:
        req = urllib.request.Request(video_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
          html_chunk = resp.read(262144).decode("utf-8", errors="replace")

          ch_match = re.search(r'itemprop=["\']channelId["\']\s+content=["\']([^"\']+)["\']', html_chunk)
          if not ch_match:
            ch_match = re.search(r'content=["\']([^"\']+)["\']\s+itemprop=["\']channelId["\']', html_chunk)
          if not ch_match:
            ch_match = re.search(r'"channelId"\s*:\s*["\'](UC[a-zA-Z0-9_-]{22})["\']', html_chunk)
          if ch_match:
            channel_id = ch_match.group(1)

          if not title:
            t_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_chunk)
            if t_match:
              title = t_match.group(1)

          if not author_name:
            a_match = re.search(r'<link\s+itemprop=["\']name["\']\s+content=["\']([^"\']+)["\']', html_chunk)
            if a_match:
              author_name = a_match.group(1)
      except Exception as e:
        self._report_error(f"Watch page lookup failed for video '{video_id}'.", exc=e)

    if not title:
      title = f"YouTube Video ({video_id})"

    return {
        "video_id": video_id,
        "video_url": video_url,
        "video_title": title,
        "channel_id": channel_id,
        "author_name": author_name,
        "author_url": author_url or (f"https://www.youtube.com/channel/{channel_id}" if channel_id else None),
    }

  def get_latest_video(
      self, channel_id: Optional[str] = None
  ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[Dict[str, str]]]:
    """Checks the latest published video via RSS for the given channel_id."""
    if not channel_id:
      self._report_error("No channel ID provided for checking RSS feed.")
      return None, None, None, None, None

    target_url = self.feed_url_template.format(channel_id=channel_id)

    try:
      feed = feedparser.parse(target_url)

      # Catch network errors or XML parsing failures detected by feedparser
      if getattr(feed, "bozo", 0) and getattr(feed, "bozo_exception", None) and not feed.entries:
        self._report_error(
            f"Could not retrieve RSS feed for channel '{channel_id}'. Check network connection or channel ID.",
            exc=feed.bozo_exception,
        )
        return None, None, None, None, None

      channel_title = feed.feed.get("title", "YouTube")
      author_detail = feed.feed.get("author_detail", {})
      author_name = feed.feed.get("author") or author_detail.get("name") or channel_title
      author_url = author_detail.get("href") or f"https://www.youtube.com/channel/{channel_id}"
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
      self._report_error(
          f"Could not retrieve RSS feed for channel '{channel_id}'. Check network connection or channel ID.",
          exc=e,
      )
    return None, None, None, None, None

  def get_transcript(self, video_id: str) -> Optional[str]:
    """Downloads the video transcript using the object-based API."""
    try:
      ytt_api = YouTubeTranscriptApi()
      fetched_data = ytt_api.fetch(video_id, languages=["it", "en"])

      # Extract text by reading the .text attribute of each snippet
      full_text = " ".join([snippet.text for snippet in fetched_data])
      return full_text
    except Exception as e:
      self._report_error(
          f"Could not retrieve transcript for video '{video_id}'. The video may lack captions or subtitles.",
          exc=e,
      )
      return None

  def summarize_transcript(
      self, video_title: str, transcript: str, prompt_template: Optional[str] = None
  ) -> Optional[str]:
    """Generates a structured summary using Gemini, with prompt template from database."""
    template = prompt_template or (
        "Summarize the following YouTube transcript for the video titled"
        " '{video_title}'.\n\nTranscript:\n{transcript}"
    )
    prompt = template.format(video_title=video_title, transcript=transcript)

    try:
      response = self.client.models.generate_content(
          model=self.gemini_model,
          contents=prompt,
      )
      return response.text
    except Exception as e:
      self._report_error(
          f"Gemini AI summarization failed for '{video_title}'. Please check API key, model, or quota.",
          exc=e,
      )
      return None

  def send_email(
      self,
      subject: str,
      markdown_content: str,
      video_url: str,
      video_id: str,
      email_template: Optional[str] = None,
      channel_label: Optional[str] = None,
  ) -> bool:
    """Sends a formatted HTML email with thumbnail and video link using the specified template."""
    try:
      if not email_template or not email_template.strip():
        raise ValueError(
            f"Email HTML template is missing, None, or blank for video '{video_id}'."
        )

      template = email_template

      html_body = markdown.markdown(
          markdown_content, extensions=["extra", "nl2br"]
      )
      thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

      # Clean token substitution that never collides with CSS braces
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

      success_msg = (
          f"{UI.tag(channel_label)} {UI.success('Email digest sent successfully.')}"
          if channel_label
          else UI.success(f"Email digest sent successfully for '{subject}'.")
      )

      if self.state_manager:
        self.state_manager.log_message(success_msg)
      else:
        print(success_msg)
      return True

    except Exception as e:
      err_prefix = f"[{channel_label}] " if channel_label else ""
      self._report_error(
          f"{err_prefix}Failed to send email digest for '{subject}'. Check SMTP credentials and network connection.",
          exc=e,
      )
      return False

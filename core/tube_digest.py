import json
import re
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from typing import Optional, Dict, Any, Tuple
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import feedparser
import markdown
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from core.ui import UI

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

RSS_REQUEST_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept": "application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_iso8601_duration(duration_str: str) -> Optional[int]:
  """Parses ISO 8601 duration format (e.g. PT1H23M45S, PT15M33S, PT45S) into total seconds."""
  if not duration_str:
    return None
  match = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", duration_str.strip())
  if not match:
    return None
  hours = int(match.group(1) or 0)
  minutes = int(match.group(2) or 0)
  seconds = int(match.group(3) or 0)
  return hours * 3600 + minutes * 60 + seconds


def extract_video_id(video_input: str) -> Optional[str]:
  """Extracts an 11-character YouTube video ID from a raw ID or full YouTube URL."""
  if not video_input or not isinstance(video_input, str):
    return None
  val = video_input.strip()
  if re.match(r"^[a-zA-Z0-9_-]{11}$", val):
    return val
  patterns = [
      r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})",
  ]
  for p in patterns:
    m = re.search(p, val)
    if m:
      return m.group(1)
  return None


LANGUAGE_MAP = {
    "it": "Italian (italiana)",
    "en": "English",
    "es": "Spanish (español)",
    "fr": "French (français)",
    "de": "German (Deutsch)",
    "zh": "Chinese (中文)",
    "ja": "Japanese (日本語)",
    "hi": "Hindi",
    "pt": "Portuguese (português)",
    "ru": "Russian",
    "ar": "Arabic",
    "ko": "Korean",
    "nl": "Dutch (Nederlands)",
    "pl": "Polish",
}


def format_language_name(lang: Optional[str]) -> str:
  """Formats an ISO language code (e.g. 'it', 'en') or language name into a descriptive string."""
  if not lang or not isinstance(lang, str):
    return "English"
  code = lang.strip().lower()
  return LANGUAGE_MAP.get(code, lang.strip())


class TubeDigest:
  extract_video_id = staticmethod(extract_video_id)

  def __init__(self, config: Dict[str, Any], state_manager=None):
    """Initializes the client and configuration parameters."""
    self.state_manager = state_manager

    general_cfg = config.get("general", {})
    self.default_language = general_cfg.get("language", "en")

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
    self._last_transcript_duration: Optional[int] = None

  def _report_error(self, message: str, exc: Optional[BaseException] = None):
    """Dispatches human-friendly message to stderr and full exception/traceback to the log file."""
    if self.state_manager:
      self.state_manager.log_error(message, exc=exc)
    else:
      print(f"⚠ {message}", file=sys.stderr)

  def _fetch_rss_feed(
      self, target_url: str, channel_id: str
  ) -> Optional[Any]:
    """Fetches and parses a YouTube RSS feed using browser headers to prevent bot/consent interception."""
    req = urllib.request.Request(target_url, headers=RSS_REQUEST_HEADERS)
    try:
      with urllib.request.urlopen(req, timeout=15) as resp:
        final_url = resp.geturl()
        content_type = resp.headers.get("Content-Type", "")
        data = resp.read()

        # Check for Google/YouTube consent redirect
        if "consent.youtube.com" in final_url or "consent.google.com" in final_url:
          self._report_error(
              f"YouTube redirected RSS request for channel '{channel_id}' to consent/verification page: {final_url}"
          )
          return None

        # Check if HTML was returned instead of XML
        if "text/html" in content_type.lower() and not data.lstrip().startswith(b"<?xml"):
          html_sample = data[:300].decode("utf-8", errors="replace").strip().replace("\n", " ")
          self._report_error(
              f"YouTube returned HTML instead of XML for channel '{channel_id}' (Status {resp.status}). Sample: {html_sample[:120]}"
          )
          return None

        feed = feedparser.parse(data)
        if getattr(feed, "bozo", 0) and getattr(feed, "bozo_exception", None) and not feed.entries:
          self._report_error(
              f"Could not parse RSS XML for channel '{channel_id}'.",
              exc=feed.bozo_exception,
          )
          return None

        return feed
    except urllib.error.HTTPError as e:
      self._report_error(
          f"HTTP error {e.code} ({e.reason}) while retrieving RSS feed for channel '{channel_id}'.",
          exc=e,
      )
      return None
    except Exception as e:
      self._report_error(
          f"Network error while retrieving RSS feed for channel '{channel_id}'.",
          exc=e,
      )
      return None

  def fetch_channel_metadata(
      self, channel_id: str
  ) -> Optional[Dict[str, str]]:
    """Fetches channel title and author profile information via RSS feed."""
    if not channel_id:
      return None

    target_url = self.feed_url_template.format(channel_id=channel_id)
    feed = self._fetch_rss_feed(target_url, channel_id)
    if not feed:
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

  def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves metadata (channel_id, title, author_name) for a specific YouTube video."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
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

    # 2. Inspect watch page HTML for channel_id, title, author, and duration
    duration_seconds = None
    try:
      req = urllib.request.Request(video_url, headers=headers)
      with urllib.request.urlopen(req, timeout=10) as resp:
        # Read up to 1.5MB to ensure script tags with player metadata (offset ~830KB) are covered
        html_chunk = resp.read(1572864).decode("utf-8", errors="replace")

        if not channel_id:
          ch_match = re.search(r'itemprop=["\']channelId["\']\s+content=["\']([^"\']+)["\']', html_chunk)
          if not ch_match:
            ch_match = re.search(r'content=["\']([^"\']+)["\']\s+itemprop=["\']channelId["\']', html_chunk)
          if not ch_match:
            ch_match = re.search(r'["\'](?:externalChannelId|channelId)["\']\s*:\s*["\'](UC[a-zA-Z0-9_-]{22})["\']', html_chunk)
          if not ch_match:
            ch_match = re.search(r'["\']browseId["\']\s*:\s*["\'](UC[a-zA-Z0-9_-]{22})["\']', html_chunk)
          if not ch_match:
            ch_match = re.search(r'/channel/(UC[a-zA-Z0-9_-]{22})', html_chunk)
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

        m_len = re.search(r'["\']lengthSeconds["\']\s*:\s*["\']?(\d+)["\']?', html_chunk)
        if m_len:
          duration_seconds = int(m_len.group(1))
        else:
          m_ms = re.search(r'["\']approxDurationMs["\']\s*:\s*["\']?(\d+)["\']?', html_chunk)
          if m_ms:
            duration_seconds = int(m_ms.group(1)) // 1000
          else:
            m_iso = re.search(r'itemprop=["\']duration["\']\s+content=["\']([^"\']+)["\']', html_chunk)
            if not m_iso:
              m_iso = re.search(r'content=["\']([^"\']+)["\']\s+itemprop=["\']duration["\']', html_chunk)
            if not m_iso:
              m_iso = re.search(r'["\']duration["\']\s*:\s*["\'](PT[^"\']+)["\']', html_chunk)
            if m_iso:
              duration_seconds = parse_iso8601_duration(m_iso.group(1))
    except Exception as e:
      self._report_error(f"Watch page lookup failed for video '{video_id}'.", exc=e)

    # 3. If channel_id was not in watch page HTML, try resolving author_url handle if available
    if not channel_id and author_url and ("/@" in author_url or "/c/" in author_url or "/user/" in author_url):
      resolved_page = self._resolve_channel_from_page(author_url)
      if resolved_page and resolved_page.get("channel_id"):
        channel_id = resolved_page["channel_id"]

    if not title:
      title = f"YouTube Video ({video_id})"

    return {
        "video_id": video_id,
        "video_url": video_url,
        "video_title": title,
        "channel_id": channel_id,
        "author_name": author_name,
        "author_url": author_url or (f"https://www.youtube.com/channel/{channel_id}" if channel_id else None),
        "duration_seconds": duration_seconds,
    }

  def _resolve_channel_from_page(self, page_url: str) -> Optional[Dict[str, str]]:
    """Fetches a YouTube channel page (handle, custom URL, etc.) and extracts channel ID and title."""
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
      req = urllib.request.Request(page_url, headers=headers)
      with urllib.request.urlopen(req, timeout=15) as resp:
        final_url = resp.geturl()
        if "consent.youtube.com" in final_url or "consent.google.com" in final_url:
          self._report_error(f"YouTube redirected channel request to consent page: {final_url}")
          return None

        # Read enough HTML to capture embedded initial data
        html_chunk = resp.read(1572864).decode("utf-8", errors="replace")

        # 1. Search for channel ID
        ch_id = None
        patterns = [
            r'itemprop=["\']channelId["\']\s+content=["\'](UC[a-zA-Z0-9_-]{22})["\']',
            r'content=["\'](UC[a-zA-Z0-9_-]{22})["\']\s+itemprop=["\']channelId["\']',
            r'["\'](?:externalId|channelId|browseId)["\']\s*:\s*["\'](UC[a-zA-Z0-9_-]{22})["\']',
            r'<link\s+rel=["\']canonical["\']\s+href=["\']https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})["\']',
            r'<meta\s+property=["\']og:url["\']\s+content=["\']https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})["\']',
            r'/channel/(UC[a-zA-Z0-9_-]{22})',
        ]
        for p in patterns:
          m = re.search(p, html_chunk)
          if m:
            ch_id = m.group(1)
            break

        if not ch_id:
          return None

        # 2. Search for channel title
        ch_title = None
        t_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_chunk)
        if t_match:
          ch_title = t_match.group(1)
        else:
          t_match = re.search(r'<title>([^<]+?)(?:\s*-\s*YouTube)?</title>', html_chunk)
          if t_match:
            ch_title = t_match.group(1).strip()

        return {
            "channel_id": ch_id,
            "channel_title": ch_title,
            "author_name": ch_title,
            "author_url": f"https://www.youtube.com/channel/{ch_id}",
        }
    except Exception as e:
      self._report_error(f"Failed to resolve channel page '{page_url}'.", exc=e)
      return None

  def resolve_channel_target(self, target: str) -> Optional[Dict[str, str]]:
    """Resolves any YouTube target (channel ID, channel URL, handle, or video URL/ID) into channel metadata.

    Accepts:
      - Canonical Channel ID (e.g. 'UCBOtZaVafz_5OmUrqJAVStQ')
      - Channel URL (e.g. 'https://www.youtube.com/channel/UC...' or 'https://www.youtube.com/@handle')
      - Channel Handle (e.g. '@MrRIP' or '@antirez')
      - Video URL or Video ID (e.g. 'https://www.youtube.com/watch?v=mUw27wG7uFA' or 'mUw27wG7uFA')

    Returns:
      A dictionary containing 'channel_id', 'channel_title', 'author_name', 'author_url', and 'resolved_from',
      or None if resolution failed.
    """
    if not target or not isinstance(target, str):
      return None

    val = target.strip()

    # 1. Direct canonical 24-char YouTube Channel ID (starts with UC)
    if re.match(r"^UC[a-zA-Z0-9_-]{22}$", val):
      meta = self.fetch_channel_metadata(val)
      return {
          "channel_id": val,
          "channel_title": meta.get("channel_title") if meta else None,
          "author_name": meta.get("author_name") if meta else None,
          "author_url": meta.get("author_url") if meta else f"https://www.youtube.com/channel/{val}",
          "resolved_from": "channel_id",
      }

    # 2. YouTube Channel URL containing /channel/UC...
    ch_match = re.search(r"/channel/(UC[a-zA-Z0-9_-]{22})", val)
    if ch_match:
      ch_id = ch_match.group(1)
      meta = self.fetch_channel_metadata(ch_id)
      return {
          "channel_id": ch_id,
          "channel_title": meta.get("channel_title") if meta else None,
          "author_name": meta.get("author_name") if meta else None,
          "author_url": meta.get("author_url") if meta else f"https://www.youtube.com/channel/{ch_id}",
          "resolved_from": "channel_url",
      }

    # 3. Video URL or 11-char Video ID
    video_id = extract_video_id(val)
    if video_id:
      v_details = self.get_video_details(video_id)
      if v_details and v_details.get("channel_id"):
        ch_id = v_details["channel_id"]
        meta = self.fetch_channel_metadata(ch_id)
        ch_title = (meta.get("channel_title") if meta else None) or v_details.get("author_name")
        a_name = (meta.get("author_name") if meta else None) or v_details.get("author_name")
        return {
            "channel_id": ch_id,
            "channel_title": ch_title,
            "author_name": a_name,
            "author_url": (meta.get("author_url") if meta else None) or v_details.get("author_url") or f"https://www.youtube.com/channel/{ch_id}",
            "resolved_from": "video",
        }
      elif v_details and v_details.get("author_url"):
        page_res = self._resolve_channel_from_page(v_details["author_url"])
        if page_res and page_res.get("channel_id"):
          ch_id = page_res["channel_id"]
          meta = self.fetch_channel_metadata(ch_id)
          return {
              "channel_id": ch_id,
              "channel_title": (meta.get("channel_title") if meta else None) or page_res.get("channel_title") or v_details.get("author_name"),
              "author_name": (meta.get("author_name") if meta else None) or page_res.get("author_name") or v_details.get("author_name"),
              "author_url": (meta.get("author_url") if meta else None) or f"https://www.youtube.com/channel/{ch_id}",
              "resolved_from": "video",
          }

    # 4. Handle (@...) or channel custom/vanity URL
    if val.startswith("@"):
      page_url = f"https://www.youtube.com/{val}"
    elif "youtube.com/@" in val or "youtube.com/c/" in val or "youtube.com/user/" in val:
      page_url = val if val.startswith(("http://", "https://")) else f"https://{val}"
    elif val.startswith(("http://", "https://")):
      page_url = val
    else:
      page_url = f"https://www.youtube.com/@{val}"

    page_res = self._resolve_channel_from_page(page_url)
    if page_res and page_res.get("channel_id"):
      ch_id = page_res["channel_id"]
      meta = self.fetch_channel_metadata(ch_id)
      return {
          "channel_id": ch_id,
          "channel_title": (meta.get("channel_title") if meta else None) or page_res.get("channel_title"),
          "author_name": (meta.get("author_name") if meta else None) or page_res.get("author_name"),
          "author_url": (meta.get("author_url") if meta else None) or f"https://www.youtube.com/channel/{ch_id}",
          "resolved_from": "handle" if ("@" in page_url) else "channel_url",
      }

    return None

  def get_video_duration(self, video_id: str) -> Optional[int]:
    """Retrieves video duration in seconds via watch page player response, meta tags, or transcript timestamps."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
    }
    try:
      req = urllib.request.Request(video_url, headers=headers)
      with urllib.request.urlopen(req, timeout=10) as resp:
        html_chunk = resp.read(1572864).decode("utf-8", errors="replace")

        m_len = re.search(r'["\']lengthSeconds["\']\s*:\s*["\']?(\d+)["\']?', html_chunk)
        if m_len:
          return int(m_len.group(1))

        m_ms = re.search(r'["\']approxDurationMs["\']\s*:\s*["\']?(\d+)["\']?', html_chunk)
        if m_ms:
          return int(m_ms.group(1)) // 1000

        m_iso = re.search(r'itemprop=["\']duration["\']\s+content=["\']([^"\']+)["\']', html_chunk)
        if not m_iso:
          m_iso = re.search(r'content=["\']([^"\']+)["\']\s+itemprop=["\']duration["\']', html_chunk)
        if not m_iso:
          m_iso = re.search(r'["\']duration["\']\s*:\s*["\'](PT[^"\']+)["\']', html_chunk)
        if m_iso:
          parsed = parse_iso8601_duration(m_iso.group(1))
          if parsed:
            return parsed
    except Exception as e:
      self._report_error(f"Duration lookup from watch page failed for video '{video_id}'.", exc=e)

    # Fallback to transcript duration if available
    if self._last_transcript_duration:
      return self._last_transcript_duration

    return None

  def get_latest_video(
      self, channel_id: Optional[str] = None
  ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[Dict[str, str]]]:
    """Checks the latest published video via RSS for the given channel_id."""
    if not channel_id:
      self._report_error("No channel ID provided for checking RSS feed.")
      return None, None, None, None, None

    target_url = self.feed_url_template.format(channel_id=channel_id)
    feed = self._fetch_rss_feed(target_url, channel_id)
    if not feed:
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

  def get_transcript(
      self,
      video_id: str,
      preferred_languages: Optional[list] = None,
  ) -> Optional[str]:
    """Downloads the video transcript prioritizing preferred languages, falling back to any available transcript."""
    priority_langs = []
    if preferred_languages:
      for lang in preferred_languages:
        if lang and isinstance(lang, str) and lang.strip():
          clean_lang = lang.strip().lower()
          if clean_lang not in priority_langs:
            priority_langs.append(clean_lang)

    if self.default_language and self.default_language.lower() not in priority_langs:
      priority_langs.append(self.default_language.lower())

    for fallback in ["en", "it", "es", "fr", "de"]:
      if fallback not in priority_langs:
        priority_langs.append(fallback)

    try:
      ytt_api = YouTubeTranscriptApi()
      transcript_list = ytt_api.list(video_id)
      transcript = None

      # 1. Try finding transcript in priority languages
      try:
        transcript = transcript_list.find_transcript(priority_langs)
      except Exception:
        pass

      # 2. Fall back to the first available transcript in ANY language (manual or generated)
      if not transcript:
        for t in transcript_list:
          transcript = t
          break

      if not transcript:
        return None

      fetched_data = transcript.fetch()
      full_text = " ".join([snippet.text for snippet in fetched_data])
      if fetched_data:
        try:
          last = fetched_data[-1]
          start = getattr(last, "start", 0) if hasattr(last, "start") else last.get("start", 0)
          dur = getattr(last, "duration", 0) if hasattr(last, "duration") else last.get("duration", 0)
          self._last_transcript_duration = int(float(start) + float(dur))
        except Exception:
          self._last_transcript_duration = None
      return full_text
    except Exception as e:
      self._report_error(
          f"Could not retrieve transcript for video '{video_id}'. The video may lack captions or subtitles.",
          exc=e,
      )
      return None

  def summarize_transcript(
      self,
      video_title: str,
      transcript: str,
      prompt_template: Optional[str] = None,
      output_language: Optional[str] = None,
  ) -> Optional[str]:
    """Generates a structured summary using Gemini, supporting dynamic output language and prompt templates."""
    target_lang = output_language or self.default_language or "en"
    lang_display = format_language_name(target_lang)

    template = prompt_template or (
        "Summarize the following YouTube transcript for the video titled"
        " '{video_title}'.\n\nGenerate the summary in {output_language}.\n\nTranscript:\n{transcript}"
    )

    if "{output_language}" in template:
      prompt = template.format(
          video_title=video_title,
          transcript=transcript,
          output_language=lang_display,
      )
    else:
      prompt = template.format(video_title=video_title, transcript=transcript)
      prompt += f"\n\n[Important Output Requirement: Generate the entire summary strictly in {lang_display}.]"

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
      duration_str: Optional[str] = None,
  ) -> bool:
    """Sends a formatted HTML email with thumbnail, duration, and video link using the specified template."""
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
      duration_display = duration_str or "-"

      # Clean token substitution that never collides with CSS braces
      email_html = (
          template.replace("{subject}", subject)
          .replace("{video_url}", video_url)
          .replace("{thumbnail_url}", thumbnail_url)
          .replace("{html_body}", html_body)
          .replace("{video_id}", video_id)
          .replace("{duration}", duration_display)
          .replace("{video_duration}", duration_display)
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

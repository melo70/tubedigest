"""UI styling and ASCII / TUI presentation module for TubeDigest.

Provides retro-futuristic ASCII art banners, Unicode box-drawing tables,
panel cards, bullet status badges, and 24-bit/ANSI color styling inspired
by modern terminal CLI tools.
"""

import os
import re
import shutil
import sys
import textwrap
import unicodedata
from typing import Any, List, Optional, Tuple

from core.models import VideoStatus

ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
  """Removes ANSI escape sequences from text for accurate length calculations and plain logging."""
  if not text:
    return ""
  return ANSI_REGEX.sub("", text)


def char_cell_width(c: str) -> int:
  """Calculates the display width in terminal cells of a single character."""
  code = ord(c)
  # Variation selectors (U+FE0E, U+FE0F) and zero-width combining characters occupy 0 terminal cells
  if code in (0xFE0E, 0xFE0F) or unicodedata.combining(c):
    return 0
  # East Asian Wide (W) and Fullwidth (F) characters (such as emojis) occupy 2 terminal cells
  if unicodedata.east_asian_width(c) in ("W", "F"):
    return 2
  return 1


def visible_len(text: str) -> int:
  """Calculates visible character width in terminal cells, ignoring ANSI color escapes."""
  if not text:
    return 0
  clean = strip_ansi(text)
  return sum(char_cell_width(c) for c in clean)


def supports_color() -> bool:
  """Detects whether standard output supports ANSI color codes."""
  if os.environ.get("NO_COLOR"):
    return False
  if os.environ.get("CLICOLOR_FORCE") == "1" or os.environ.get("FORCE_COLOR") == "1":
    return True
  if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
    return False
  # Support Windows 10+ or standard UNIX/Linux terminals
  term = os.environ.get("TERM", "")
  if term == "dumb":
    return False
  return True


class UI:
  """Centralized UI and color formatting helper."""

  # Standard ANSI codes
  RESET = "\033[0m"
  BOLD = "\033[1m"
  DIM = "\033[2m"
  GRAY = "\033[90m"
  RED = "\033[91m"
  GREEN = "\033[92m"
  YELLOW = "\033[93m"
  BLUE = "\033[94m"
  MAGENTA = "\033[95m"
  CYAN = "\033[96m"
  WHITE = "\033[97m"

  @classmethod
  def _wrap(cls, code: str, text: str) -> str:
    if not supports_color() or not text:
      return text
    return f"{code}{text}{cls.RESET}"

  @classmethod
  def bold(cls, text: str) -> str:
    return cls._wrap(cls.BOLD, text)

  @classmethod
  def dim(cls, text: str) -> str:
    return cls._wrap(cls.DIM, text)

  @classmethod
  def gray(cls, text: str) -> str:
    return cls._wrap(cls.GRAY, text)

  @classmethod
  def cyan(cls, text: str) -> str:
    return cls._wrap(cls.CYAN, text)

  @classmethod
  def green(cls, text: str) -> str:
    return cls._wrap(cls.GREEN, text)

  @classmethod
  def yellow(cls, text: str) -> str:
    return cls._wrap(cls.YELLOW, text)

  @classmethod
  def red(cls, text: str) -> str:
    return cls._wrap(cls.RED, text)

  @classmethod
  def magenta(cls, text: str) -> str:
    return cls._wrap(cls.MAGENTA, text)

  @classmethod
  def blue(cls, text: str) -> str:
    return cls._wrap(cls.BLUE, text)

  @classmethod
  def white(cls, text: str) -> str:
    return cls._wrap(cls.WHITE, text)

  @classmethod
  def gradient_line(
      cls,
      line: str,
      start_rgb: Tuple[int, int, int] = (69, 183, 209),    # Cyan
      mid_rgb: Tuple[int, int, int] = (217, 70, 239),      # Magenta
      end_rgb: Tuple[int, int, int] = (249, 115, 22),      # Coral
      max_width: Optional[int] = None,
  ) -> str:
    """Applies a smooth horizontal 3-stop RGB gradient to a single line of text."""
    if not supports_color() or not line:
      return line

    clean = strip_ansi(line)
    n = max_width or max(len(clean), 1)
    if n <= 1:
      return line

    out = []
    ci = 0
    in_escape = False
    escape_buf = ""

    for ch in line:
      if ch == "\x1b":
        in_escape = True
        escape_buf = ch
        continue
      if in_escape:
        escape_buf += ch
        if ch.isalpha():
          in_escape = False
          out.append(escape_buf)
        continue

      ratio = ci / max(n - 1, 1)
      if ratio < 0.5:
        sub_ratio = ratio * 2
        r = int(start_rgb[0] + sub_ratio * (mid_rgb[0] - start_rgb[0]))
        g = int(start_rgb[1] + sub_ratio * (mid_rgb[1] - start_rgb[1]))
        b = int(start_rgb[2] + sub_ratio * (mid_rgb[2] - start_rgb[2]))
      else:
        sub_ratio = (ratio - 0.5) * 2
        r = int(mid_rgb[0] + sub_ratio * (end_rgb[0] - mid_rgb[0]))
        g = int(mid_rgb[1] + sub_ratio * (end_rgb[1] - mid_rgb[1]))
        b = int(mid_rgb[2] + sub_ratio * (end_rgb[2] - mid_rgb[2]))

      out.append(f"\033[38;2;{r};{g};{b}m{ch}{cls.RESET}")
      ci += 1

    return "".join(out)

  @classmethod
  def banner(cls) -> str:
    """Returns the stylized high-tech ASCII art header for TubeDigest."""
    # 73-character wide stylized raster font with chevron prompt '>'
    raw_lines = [
        "  ▄",
        "   █  ▄▄▄▄▄▄▄ ▄   ▄ ▄▄▄▄  ▄▄▄▄▄   ▄▄▄▄   ▄▄▄▄▄ ▄▄▄▄▄ ▄▄▄▄▄ ▄▄▄▄▄ ▄▄▄▄▄▄▄",
        "  ██     █    █   █ █   █ █       █   █    █   █     █     █        █   ",
        " █       █    █   █ █▄▄▄█ █▄▄▄    █   █    █   █ ▄▄▄ █▄▄▄  █▄▄▄▄    █   ",
        "  ▀      █    █   █ █   █ █       █   █    █   █   █ █         █    █   ",
        "         █    ▀▄▄▄▀ █▄▄▄▀ █▄▄▄▄   █▄▄▄▀  ▄▄█▄▄ ▀▄▄▄█ █▄▄▄▄ ▄▄▄▄▀    █   ",
    ]
    max_w = max(len(l) for l in raw_lines)
    styled_lines = [cls.gradient_line(l, max_width=max_w) for l in raw_lines]

    subtitle = (
        f"  {cls.gray('>')} {cls.bold(cls.white('Automated YouTube Monitor & Gemini AI Digest Pipeline'))}"
    )
    return "\n" + "\n".join(styled_lines) + "\n" + subtitle + "\n"

  @classmethod
  def badge_active(cls, is_active: bool) -> str:
    """Returns a filled green bullet for active, or an empty gray circle for disabled."""
    if is_active:
      return f"{cls.green('● Active  ')}"
    return f"{cls.gray('○ Disabled')}"

  @classmethod
  def badge_yes_no(cls, val: bool) -> str:
    """Returns a filled green bullet for Yes, or empty gray circle for No."""
    if val:
      return f"{cls.green('● Yes')}"
    return f"{cls.gray('○ No ')}"

  @classmethod
  def badge_status(cls, status: str) -> str:
    """Returns a color-coded status indicator."""
    st = (str(status) if status else "").upper()
    if st == VideoStatus.COMPLETED:
      return f"{cls.green('● COMPLETED')}"
    elif st == VideoStatus.PENDING_EMAIL:
      return f"{cls.yellow('⏳ PEND_EMAIL')}"
    elif st == VideoStatus.PENDING_SUMMARY:
      return f"{cls.yellow('⏳ PENDING_AI')}"
    elif st == "PENDING":
      return f"{cls.yellow('⏳ PENDING  ')}"
    elif st == VideoStatus.NO_TRANSCRIPT:
      return f"{cls.gray('○ NO_SUBS  ')}"
    return f"{cls.magenta(st[:12])}"

  @classmethod
  def format_duration(cls, seconds: Optional[int]) -> str:
    """Formats duration in seconds to standard timestamp string (e.g. '15:33' or '1:12:45')."""
    if not isinstance(seconds, int) or seconds <= 0:
      return "-"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
      return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

  @classmethod
  def tag(cls, channel_label: str) -> str:
    """Formats channel tag prefix for terminal pipeline logs: [channel_name]."""
    return f"{cls.gray('[')}{cls.bold(cls.cyan(channel_label))}{cls.gray(']')}"

  @classmethod
  def success(cls, text: str) -> str:
    return f"{cls.green('✓')} {text}"

  @classmethod
  def error(cls, text: str) -> str:
    return f"{cls.red('⚠')} {text}"

  @classmethod
  def warning(cls, text: str) -> str:
    return f"{cls.yellow('⚠')} {text}"

  @classmethod
  def tip(cls, text: str) -> str:
    return f"  {cls.gray('Tip:')} {cls.dim(text)}"

  @classmethod
  def draw_table(
      cls,
      title: str,
      headers: List[str],
      rows: List[List[str]],
      min_width: int = 78,
  ) -> str:
    """Draws a modern rounded-corner Unicode table with aligned columns."""
    cols = len(headers)
    if cols == 0:
      return ""

    # Calculate optimal column widths based on visible content length
    col_widths = [visible_len(h) for h in headers]
    for row in rows:
      for i, cell in enumerate(row):
        if i < cols:
          col_widths[i] = max(col_widths[i], visible_len(str(cell)))

    # Add padding to each column
    col_widths = [w + 2 for w in col_widths]

    # Adjust table width if title requires more space
    total_inner_width = sum(col_widths) + (cols - 1)
    title_visible = visible_len(title)
    if total_inner_width < min_width:
      extra = min_width - total_inner_width
      col_widths[-1] += extra
      total_inner_width = sum(col_widths) + (cols - 1)
    elif title_visible + 6 > total_inner_width:
      extra = (title_visible + 6) - total_inner_width
      col_widths[-1] += extra
      total_inner_width = sum(col_widths) + (cols - 1)

    dash = "─"
    lines = []

    # Top border with embedded title: ╭─ Title ───────╮
    dash_count = total_inner_width - title_visible - 3
    lines.append(
        cls.gray("╭─ ")
        + cls.bold(cls.cyan(title))
        + " "
        + cls.gray(dash * max(0, dash_count) + "╮")
    )

    # Header row
    h_cells = []
    for h, w in zip(headers, col_widths):
      pad = w - visible_len(h) - 1
      h_cells.append(" " + cls.bold(cls.white(h)) + (" " * max(0, pad)))
    lines.append(
        cls.gray("│") + cls.gray("│").join(h_cells) + cls.gray("│")
    )

    # Separator after header: ├──────┼──────┤
    sep_cells = [dash * w for w in col_widths]
    lines.append(cls.gray("├" + "┼".join(sep_cells) + "┤"))

    # Content rows
    for row in rows:
      r_cells = []
      for i, w in enumerate(col_widths):
        val = str(row[i]) if i < len(row) else ""
        pad = w - visible_len(val) - 1
        r_cells.append(" " + val + (" " * max(0, pad)))
      lines.append(
          cls.gray("│") + cls.gray("│").join(r_cells) + cls.gray("│")
      )

    # Bottom border: ╰──────┴──────╯
    bot_cells = [dash * w for w in col_widths]
    lines.append(cls.gray("╰" + "┴".join(bot_cells) + "╯"))

    return "\n".join(lines)

  @classmethod
  def draw_key_value_table(
      cls,
      title: str,
      items: List[Tuple[str, Any]],
      headers: Tuple[str, str] = ("Property", "Value"),
      min_width: int = 78,
  ) -> str:
    """Draws a rounded-corner Unicode table with aligned key-value columns separated by a vertical bar."""
    if not items:
      return ""

    term_cols = shutil.get_terminal_size((80, 24)).columns
    target_width = min(max(term_cols, min_width), 110)

    # Calculate key column width
    max_key_len = max(visible_len(h) for h in [headers[0]] + [k for k, _ in items])
    key_width = max_key_len + 2

    val_width = max(target_width - 3 - key_width, 20)
    val_content_width = val_width - 2
    actual_width = key_width + val_width + 3

    dash = "─"
    title_vis = visible_len(title)
    dash_count = (actual_width - 2) - title_vis - 3

    lines = [
        cls.gray("╭─ ")
        + cls.bold(cls.cyan(title))
        + " "
        + cls.gray(dash * max(0, dash_count) + "╮"),
        cls.gray("│")
        + " "
        + cls.bold(cls.white(headers[0]))
        + (" " * max(0, key_width - visible_len(headers[0]) - 1))
        + cls.gray("│")
        + " "
        + cls.bold(cls.white(headers[1]))
        + (" " * max(0, val_width - visible_len(headers[1]) - 1))
        + cls.gray("│"),
        cls.gray("├" + (dash * key_width) + "┼" + (dash * val_width) + "┤"),
    ]

    for key, val in items:
      raw_val = str(val) if val is not None else "-"
      val_lines = []
      for segment in raw_val.splitlines() or [""]:
        if not segment.strip():
          val_lines.append("")
          continue
        wrapped = cls.wrap_text(segment, width=val_content_width, justify=False)
        val_lines.extend(wrapped or [segment])

      if not val_lines:
        val_lines = ["-"]

      for i, vl in enumerate(val_lines):
        k_text = key if i == 0 else ""
        kp = key_width - visible_len(k_text) - 1
        vp = val_width - visible_len(vl) - 1
        lines.append(
            cls.gray("│")
            + " "
            + k_text
            + (" " * max(0, kp))
            + cls.gray("│")
            + " "
            + vl
            + (" " * max(0, vp))
            + cls.gray("│")
        )

    lines.append(
        cls.gray("╰" + (dash * key_width) + "┴" + (dash * val_width) + "╯")
    )
    return "\n".join(lines)

  @classmethod
  def draw_panel(
      cls,
      title: str,
      content: str,
      width: Optional[int] = None,
  ) -> str:
    """Draws a rounded-corner Unicode card panel with wrapped content fitting terminal width."""
    term_cols = shutil.get_terminal_size((80, 24)).columns
    target_width = width or min(max(term_cols, 78), 110)
    inner_width = target_width - 2
    content_width = inner_width - 2  # 1 space padding left & right
    dash = "─"

    # Wrap content lines if they exceed content_width
    raw_lines = (content or "").splitlines() or [""]
    wrapped_lines = []
    for raw_l in raw_lines:
      if not raw_l.strip():
        wrapped_lines.append("")
        continue
      if visible_len(raw_l) <= content_width:
        wrapped_lines.append(raw_l)
      else:
        # Wrap long text cleanly
        sub = textwrap.wrap(
            raw_l,
            width=content_width,
            break_long_words=False,
            break_on_hyphens=False,
        )
        wrapped_lines.extend(sub or [raw_l])

    title_len = visible_len(title)
    dash_count = inner_width - title_len - 3
    res = [
        cls.gray("╭─ ")
        + cls.bold(cls.cyan(title))
        + " "
        + cls.gray(dash * max(0, dash_count) + "╮")
    ]

    for line in wrapped_lines:
      pad = inner_width - visible_len(line) - 1
      res.append(cls.gray("│") + " " + line + (" " * max(0, pad)) + cls.gray("│"))

    res.append(cls.gray("╰" + (dash * inner_width) + "╯"))
    return "\n".join(res)

  @classmethod
  def supports_color(cls) -> bool:
    return supports_color()

  @classmethod
  def render_inline(cls, s: str) -> str:
    """Renders inline Markdown formatting (bold, italic, code, links) to terminal styles."""
    if not s:
      return ""

    if not supports_color():
      # Cleanly strip markdown formatting markers when colors are disabled
      s = re.sub(r"\*\*\*(.*?)\*\*\*", r"\1", s)
      s = re.sub(r"___(.*?)___", r"\1", s)
      s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
      s = re.sub(r"__(.*?)__", r"\1", s)
      s = re.sub(r"\*(.*?)\*", r"\1", s)
      s = re.sub(r"_(.*?)_", r"\1", s)
      s = re.sub(r"`(.*?)`", r"\1", s)
      s = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", s)
      return s

    # 1. Inline code: `code`
    s = re.sub(r"`(.*?)`", lambda m: f"{cls.CYAN}{m.group(1)}{cls.RESET}", s)
    # 2. Bold italic: ***text*** or ___text___
    s = re.sub(r"\*\*\*(.*?)\*\*\*", lambda m: f"{cls.BOLD}\033[3m{m.group(1)}{cls.RESET}", s)
    s = re.sub(r"___(.*?)___", lambda m: f"{cls.BOLD}\033[3m{m.group(1)}{cls.RESET}", s)
    # 3. Bold: **text** or __text__
    s = re.sub(r"\*\*(.*?)\*\*", lambda m: f"{cls.BOLD}{cls.WHITE}{m.group(1)}{cls.RESET}", s)
    s = re.sub(r"__(.*?)__", lambda m: f"{cls.BOLD}{cls.WHITE}{m.group(1)}{cls.RESET}", s)
    # 4. Italic: *text* or _text_
    s = re.sub(r"\*(.*?)\*", lambda m: f"\033[3m{m.group(1)}{cls.RESET}", s)
    s = re.sub(r"(?<!\w)_(.*?)_(?!\w)", lambda m: f"\033[3m{m.group(1)}{cls.RESET}", s)
    # 5. Markdown links: [text](url)
    s = re.sub(r"\[(.*?)\]\((.*?)\)", lambda m: f"\033[4m{m.group(1)}{cls.RESET} ({cls.BLUE}{m.group(2)}{cls.RESET})", s)
    return s

  @classmethod
  def draw_wrapped_table(
      cls,
      title: str,
      headers: List[str],
      rows: List[List[str]],
      max_width: int = 80,
  ) -> str:
    """Draws a responsive Unicode table wrapping cell text to fit max_width."""
    cols = len(headers)
    if cols == 0:
      return ""

    total_inner = max_width - 2
    usable_width = total_inner - (cols - 1)

    raw_col_lens = [max(visible_len(h), 6) for h in headers]
    for row in rows:
      for i, c in enumerate(row):
        if i < cols:
          raw_col_lens[i] = max(raw_col_lens[i], min(visible_len(c), 45))
    total_raw = sum(raw_col_lens) or 1

    col_widths = [max(8, int(usable_width * (l / total_raw))) for l in raw_col_lens]
    delta = usable_width - sum(col_widths)
    col_widths[-1] += delta
    dash = "─"

    lines = []
    title_visible = visible_len(title)
    if title:
      dash_count = total_inner - title_visible - 3
      lines.append(
          cls.gray("╭─ ") + cls.bold(cls.cyan(title)) + " " + cls.gray(dash * max(0, dash_count) + "╮")
      )
    else:
      top_cells = [dash * w for w in col_widths]
      lines.append(cls.gray("╭" + "┬".join(top_cells) + "╮"))

    # Wrapped headers
    wrapped_headers = [
        textwrap.wrap(h, width=max(4, col_widths[i] - 2)) or [""]
        for i, h in enumerate(headers)
    ]
    max_h_sub = max(len(c) for c in wrapped_headers)
    for line_idx in range(max_h_sub):
      parts = []
      for i, c_lines in enumerate(wrapped_headers):
        w = col_widths[i]
        text_part = c_lines[line_idx] if line_idx < len(c_lines) else ""
        pad = w - visible_len(text_part) - 1
        parts.append(" " + cls.bold(cls.white(text_part)) + (" " * max(0, pad)))
      lines.append(cls.gray("│") + cls.gray("│").join(parts) + cls.gray("│"))

    sep_cells = [dash * w for w in col_widths]
    lines.append(cls.gray("├" + "┼".join(sep_cells) + "┤"))

    # Rows
    for row in rows:
      wrapped_cells = []
      for i, val in enumerate(row):
        w = col_widths[i] if i < len(col_widths) else 10
        content_w = max(4, w - 2)
        sub = textwrap.wrap(val, width=content_w) or [""]
        wrapped_cells.append(sub)

      max_sub = max(len(c) for c in wrapped_cells)
      for line_idx in range(max_sub):
        line_parts = []
        for i, c_lines in enumerate(wrapped_cells):
          w = col_widths[i]
          text_part = c_lines[line_idx] if line_idx < len(c_lines) else ""
          pad = w - visible_len(text_part) - 1
          line_parts.append(" " + text_part + (" " * max(0, pad)))
        lines.append(cls.gray("│") + cls.gray("│").join(line_parts) + cls.gray("│"))

      lines.append(cls.gray("├" + "┼".join(sep_cells) + "┤"))

    lines[-1] = cls.gray("╰" + "┴".join(sep_cells) + "╯")
    return "\n".join(lines)

  @classmethod
  def justify_line(cls, line: str, width: int, rtl: bool = False) -> str:
    """Justifies a single line of terminal text to target width by distributing spaces."""
    stripped = line.strip()
    words = stripped.split()
    if len(words) <= 1:
      return line
    vis_len = sum(visible_len(w) for w in words)
    spaces_needed = width - vis_len
    gaps = len(words) - 1
    if gaps <= 0 or spaces_needed < gaps or spaces_needed > gaps * 3.5:
      return line
    base = spaces_needed // gaps
    extra = spaces_needed % gaps
    parts = []
    for idx, w in enumerate(words):
      parts.append(w)
      if idx < gaps:
        has_extra = 1 if (idx >= (gaps - extra) if rtl else idx < extra) else 0
        parts.append(" " * (base + has_extra))
    return "".join(parts)

  @classmethod
  def wrap_text(cls, text: str, width: int, justify: bool = True) -> List[str]:
    """Wraps text respecting ANSI codes, optionally justifying lines."""
    if not text:
      return []
    words = text.split(" ")
    lines = []
    current_line = []
    current_vis_len = 0
    for w in words:
      if not w:
        continue
      w_len = visible_len(w)
      if current_line and (current_vis_len + 1 + w_len > width):
        lines.append(" ".join(current_line))
        current_line = [w]
        current_vis_len = w_len
      else:
        if current_line:
          current_vis_len += 1 + w_len
        else:
          current_vis_len = w_len
        current_line.append(w)
    if current_line:
      lines.append(" ".join(current_line))

    if not justify or len(lines) <= 1:
      return lines

    justified = []
    for idx, l in enumerate(lines):
      if idx == len(lines) - 1:
        justified.append(l)
      else:
        justified.append(cls.justify_line(l, width, rtl=(idx % 2 == 1)))
    return justified

  @classmethod
  def render_markdown(
      cls, md_text: str, width: Optional[int] = None, justify: bool = True
  ) -> str:
    """Renders a Markdown document into beautiful, colorized terminal text."""
    if not md_text:
      return ""

    term_cols = shutil.get_terminal_size((80, 24)).columns
    target_width = width or min(max(term_cols, 78), 100)

    lines = md_text.splitlines()
    out = []
    i = 0
    n = len(lines)

    while i < n:
      line = lines[i]
      stripped = line.strip()

      # 1. Blank line
      if not stripped:
        out.append("")
        i += 1
        continue

      # 2. Code Block ```
      if stripped.startswith("```"):
        code_lines = []
        i += 1
        while i < n and not lines[i].strip().startswith("```"):
          code_lines.append("  " + lines[i])
          i += 1
        if i < n:
          i += 1
        out.append(cls.draw_panel("Code", "\n".join(code_lines), width=target_width))
        continue

      # 3. Table (| Col 1 | Col 2 |)
      if (
          stripped.startswith("|")
          and stripped.endswith("|")
          and i + 1 < n
          and ("---" in lines[i + 1] or ":--" in lines[i + 1])
      ):
        table_lines = []
        while (
            i < n
            and lines[i].strip().startswith("|")
            and lines[i].strip().endswith("|")
        ):
          table_lines.append(lines[i].strip())
          i += 1
        raw_headers = [c.strip() for c in table_lines[0].strip("|").split("|")]
        headers = [cls.render_inline(h) for h in raw_headers]
        rows = []
        for r in table_lines[2:]:
          cells = [cls.render_inline(c.strip()) for c in r.strip("|").split("|")]
          rows.append(cells)
        out.append("\n" + cls.draw_wrapped_table("", headers, rows, max_width=target_width) + "\n")
        continue

      # 4. Headings
      if stripped.startswith("# "):
        title = cls.render_inline(stripped[2:].strip())
        out.append("\n" + cls.bold(cls.white(title)))
        out.append(cls.cyan("═" * min(visible_len(title), target_width)))
        i += 1
        continue

      if stripped.startswith("## "):
        h2 = cls.render_inline(stripped[3:].strip())
        out.append("\n" + cls.bold(cls.cyan(f"▸ {h2}")))
        out.append(cls.gray("─" * target_width))
        i += 1
        continue

      if stripped.startswith("### "):
        h3 = cls.render_inline(stripped[4:].strip())
        out.append("\n" + cls.bold(cls.yellow(f"  ▪ {h3}")))
        i += 1
        continue

      if stripped.startswith("#### "):
        h4 = cls.render_inline(stripped[5:].strip())
        out.append("\n" + cls.bold(cls.white(f"    ▫ {h4}")))
        i += 1
        continue

      # 5. Horizontal rule (--- or ***)
      if stripped in ("---", "***", "___", "- - -", "* * *"):
        out.append(cls.gray("─" * target_width))
        i += 1
        continue

      # 6. Blockquote (> Quote)
      if stripped.startswith(">"):
        quote_lines = [stripped.lstrip("> ").strip()]
        i += 1
        while i < n and lines[i].strip().startswith(">"):
          quote_lines.append(lines[i].strip().lstrip("> ").strip())
          i += 1
        full_q = " ".join(quote_lines)
        rendered_q = cls.render_inline(full_q)
        wrapped_q = cls.wrap_text(rendered_q, width=target_width - 6, justify=justify)
        for ql in wrapped_q:
          out.append(f"  {cls.gray('│')} {cls.dim(ql)}")
        continue

      # 7. Unordered List (- , * , + )
      m_list = re.match(r"^(\s*)([-*+])\s+(.*)$", line)
      if m_list:
        indent_spaces = len(m_list.group(1))
        bullet_char = cls.cyan("•") if indent_spaces == 0 else cls.gray("◦")
        item_text = cls.render_inline(m_list.group(3))
        prefix_len = 2 + indent_spaces + 2
        sub_indent = " " * prefix_len
        avail_width = target_width - prefix_len
        wrapped = cls.wrap_text(item_text, width=avail_width, justify=justify)
        if wrapped:
          out.append(" " * indent_spaces + f"  {bullet_char} " + wrapped[0])
          for extra_l in wrapped[1:]:
            out.append(sub_indent + extra_l)
        else:
          out.append(" " * indent_spaces + f"  {bullet_char}")
        i += 1
        continue

      # 8. Numbered List (1. , 2. )
      m_num = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
      if m_num:
        indent_spaces = len(m_num.group(1))
        num_str = m_num.group(2)
        item_text = cls.render_inline(m_num.group(3))
        prefix = " " * indent_spaces + f"  {cls.bold(num_str + '.')} "
        prefix_len = 2 + indent_spaces + len(num_str) + 2
        sub_indent = " " * prefix_len
        avail_width = target_width - prefix_len
        wrapped = cls.wrap_text(item_text, width=avail_width, justify=justify)
        if wrapped:
          out.append(prefix + wrapped[0])
          for extra_l in wrapped[1:]:
            out.append(sub_indent + extra_l)
        else:
          out.append(prefix)
        i += 1
        continue

      # 9. Standard Paragraph
      p_lines = [stripped]
      i += 1
      while i < n:
        next_line = lines[i]
        next_stripped = next_line.strip()
        if (
            not next_stripped
            or next_stripped.startswith("```")
            or next_stripped.startswith("|")
            or next_stripped.startswith("#")
            or next_stripped in ("---", "***", "___", "- - -", "* * *")
            or next_stripped.startswith(">")
            or re.match(r"^(\s*)([-*+])\s+", next_line)
            or re.match(r"^(\s*)(\d+)\.\s+", next_line)
        ):
          break
        p_lines.append(next_stripped)
        i += 1

      full_p = " ".join(p_lines)
      rendered_p = cls.render_inline(full_p)
      wrapped_p = cls.wrap_text(rendered_p, width=target_width, justify=justify)
      for pl in wrapped_p:
        out.append(pl)

    return "\n".join(out)

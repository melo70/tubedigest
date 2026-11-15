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
from typing import List, Optional, Tuple

ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
  """Removes ANSI escape sequences from text for accurate length calculations and plain logging."""
  if not text:
    return ""
  return ANSI_REGEX.sub("", text)


def visible_len(text: str) -> int:
  """Calculates visible character width in terminal, ignoring ANSI color escapes."""
  return len(strip_ansi(text))


def supports_color() -> bool:
  """Detects whether standard output supports ANSI color codes."""
  if os.environ.get("NO_COLOR"):
    return False
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
    st = (status or "").upper()
    if st == "COMPLETED":
      return f"{cls.green('● COMPLETED')}"
    elif st == "PENDING_EMAIL":
      return f"{cls.yellow('⏳ PENDING  ')}"
    elif st == "NO_TRANSCRIPT":
      return f"{cls.gray('○ NO_SUBS  ')}"
    return f"{cls.magenta(st[:11])}"

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

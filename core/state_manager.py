import os
import sys
import datetime
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional

ASCII_BANNER = r"""================================================================================
 _____      _            ____  _                 _   
|_   _|   _| |__   ___  |  _ \(_) __ _  ___  ___| |_ 
  | | | | | '_ \ / _ \ | | | | |/ _` |/ _ \/ __| __|
  | | | |_| | |_) |  __/ | |_| | | (_| |  __/\__ \ |_ 
  |_|  \__,_|_.__/ \___| |____/|_|\__, |\___||___/\__|
                                  |___/               
 TubeDigest - Automated YouTube Channel Monitor & AI Summarizer
 Log initialized at: {timestamp}
================================================================================"""


class BannerRotatingFileHandler(RotatingFileHandler):
  """Rotating file handler that prepends an ASCII art banner upon rollover."""

  def doRollover(self):
    super().doRollover()
    self._write_banner()

  def _write_banner(self):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = ASCII_BANNER.format(timestamp=timestamp) + "\n\n"
    with open(self.baseFilename, "w", encoding="utf-8") as f:
      f.write(header)


class StateManager:
  """Manages application logging with automatic rotation and ASCII art headers."""

  def __init__(self, storage: Dict[str, Any]):
    self.logs_dir = storage.get("logs_dir", "logs")
    self.log_file_name = storage.get("log_file", "tubedigest.log")
    self.max_bytes = storage.get("log_max_bytes", 1024 * 1024)  # 1 MB default
    self.backup_count = storage.get("log_backup_count", 5)       # 5 backups default

    # Create logs directory if it does not exist
    os.makedirs(self.logs_dir, exist_ok=True)
    self.log_path = os.path.join(self.logs_dir, self.log_file_name)

    # Initialize file with ASCII banner if empty or newly created
    if not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0:
      self._create_initial_log()

    # Configure dedicated logger
    self.logger = logging.getLogger("tubedigest")
    self.logger.setLevel(logging.INFO)
    self.logger.propagate = False

    # Avoid adding duplicate handlers if instantiated multiple times
    if not self.logger.handlers:
      file_handler = BannerRotatingFileHandler(
          self.log_path,
          maxBytes=self.max_bytes,
          backupCount=self.backup_count,
          encoding="utf-8",
      )
      formatter = logging.Formatter(
          "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
      )
      file_handler.setFormatter(formatter)
      self.logger.addHandler(file_handler)

  def _create_initial_log(self):
    """Writes the initial ASCII art banner to a new log file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = ASCII_BANNER.format(timestamp=timestamp) + "\n\n"
    with open(self.log_path, "w", encoding="utf-8") as f:
      f.write(header)

  def log_message(self, message: str):
    """Writes an informational message to stdout and appends each line to the rotated log file."""
    print(message)
    if "\n" in message:
      for line in message.splitlines():
        self.logger.info(line)
    else:
      self.logger.info(message)

  def log_error(self, message: str, exc: Optional[BaseException] = None):
    """Prints a friendly error message to stderr and logs technical details with traceback to file."""
    print(f"⚠ {message}", file=sys.stderr)
    lines = message.splitlines() if "\n" in message else [message]
    if exc:
      self.logger.error(f"{lines[0]} - Exception: {exc}", exc_info=exc)
      for line in lines[1:]:
        self.logger.error(line)
    else:
      for line in lines:
        self.logger.error(line)

import os
import datetime


class StateManager:
  """Manages application logging and filesystem outputs."""

  def __init__(self, storage):
    self.logs_dir = storage.get("logs_dir", "logs")
    self.log_file_name = storage.get("log_file", "tubedigest.log")

    # Create logs directory if it does not exist
    os.makedirs(self.logs_dir, exist_ok=True)

    self.log_path = os.path.join(self.logs_dir, self.log_file_name)

  def log_message(self, message: str):
    """Writes a timestamped log message to stdout and the configured log file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    print(message)
    with open(self.log_path, "a", encoding="utf-8") as f:
      f.write(log_line)

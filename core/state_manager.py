import os
import datetime


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

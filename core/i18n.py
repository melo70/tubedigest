"""Internationalization and localization module for TubeDigest."""

from dataclasses import dataclass
from typing import Dict, Optional, List


@dataclass(frozen=True)
class EmailLocalization:
  """Strongly typed container for email layout text elements."""
  heading: str
  duration_label: str
  watch_action: str


@dataclass(frozen=True)
class Locale:
  """Represents a supported language locale with display names and email templates."""
  code: str
  display_name: str
  email: EmailLocalization


class I18nManager:
  """Centralized internationalization registry and localization service."""

  DEFAULT_LANGUAGE = "en"

  _LOCALES: Dict[str, Locale] = {
      "it": Locale(
          code="it",
          display_name="Italian (italiana)",
          email=EmailLocalization(
              heading="Nuovo video pubblicato!",
              duration_label="Durata:",
              watch_action="Guarda il video su YouTube",
          ),
      ),
      "en": Locale(
          code="en",
          display_name="English",
          email=EmailLocalization(
              heading="New video published!",
              duration_label="Duration:",
              watch_action="Watch video on YouTube",
          ),
      ),
      "es": Locale(
          code="es",
          display_name="Spanish (español)",
          email=EmailLocalization(
              heading="¡Nuevo video publicado!",
              duration_label="Duración:",
              watch_action="Ver video en YouTube",
          ),
      ),
      "fr": Locale(
          code="fr",
          display_name="French (français)",
          email=EmailLocalization(
              heading="Nouvelle vidéo publiée !",
              duration_label="Durée :",
              watch_action="Regarder la vidéo sur YouTube",
          ),
      ),
      "de": Locale(
          code="de",
          display_name="German (Deutsch)",
          email=EmailLocalization(
              heading="Neues Video veröffentlicht!",
              duration_label="Dauer:",
              watch_action="Video auf YouTube ansehen",
          ),
      ),
      "zh": Locale(
          code="zh",
          display_name="Chinese (中文)",
          email=EmailLocalization(
              heading="新视频已发布！",
              duration_label="时长：",
              watch_action="在 YouTube 上观看视频",
          ),
      ),
      "ja": Locale(
          code="ja",
          display_name="Japanese (日本語)",
          email=EmailLocalization(
              heading="新しい動画が公開されました！",
              duration_label="再生時間：",
              watch_action="YouTubeで動画を視聴する",
          ),
      ),
      "hi": Locale(
          code="hi",
          display_name="Hindi",
          email=EmailLocalization(
              heading="नया वीडियो प्रकाशित हुआ!",
              duration_label="अवधि:",
              watch_action="YouTube पर वीडियो देखें",
          ),
      ),
      "pt": Locale(
          code="pt",
          display_name="Portuguese (português)",
          email=EmailLocalization(
              heading="Novo vídeo publicado!",
              duration_label="Duração:",
              watch_action="Assistir ao vídeo no YouTube",
          ),
      ),
      "ru": Locale(
          code="ru",
          display_name="Russian",
          email=EmailLocalization(
              heading="Опубликовано новое видео!",
              duration_label="Длительность:",
              watch_action="Смотреть видео на YouTube",
          ),
      ),
      "ar": Locale(
          code="ar",
          display_name="Arabic",
          email=EmailLocalization(
              heading="تم نشر فيديو جديد!",
              duration_label="المدة:",
              watch_action="مشاهدة الفيديو على YouTube",
          ),
      ),
      "ko": Locale(
          code="ko",
          display_name="Korean",
          email=EmailLocalization(
              heading="새 동영상이 게시되었습니다!",
              duration_label="재생 시간:",
              watch_action="YouTube에서 동영상 보기",
          ),
      ),
      "nl": Locale(
          code="nl",
          display_name="Dutch (Nederlands)",
          email=EmailLocalization(
              heading="Nieuwe video gepubliceerd!",
              duration_label="Duur:",
              watch_action="Bekijk video op YouTube",
          ),
      ),
      "pl": Locale(
          code="pl",
          display_name="Polish",
          email=EmailLocalization(
              heading="Opublikowano nowy film!",
              duration_label="Czas trwania:",
              watch_action="Obejrzyj film na YouTube",
          ),
      ),
  }

  @classmethod
  def get_locale(cls, lang_code: Optional[str]) -> Locale:
    """Returns the Locale for the given code, falling back to DEFAULT_LANGUAGE."""
    if not lang_code or not isinstance(lang_code, str):
      return cls._LOCALES[cls.DEFAULT_LANGUAGE]
    code = lang_code.strip().lower()
    return cls._LOCALES.get(code, cls._LOCALES[cls.DEFAULT_LANGUAGE])

  @classmethod
  def get_display_name(cls, lang_code: Optional[str]) -> str:
    """Returns human-friendly language name for Gemini prompt injection."""
    if not lang_code or not isinstance(lang_code, str):
      return cls._LOCALES[cls.DEFAULT_LANGUAGE].display_name
    code = lang_code.strip().lower()
    locale = cls._LOCALES.get(code)
    return locale.display_name if locale else lang_code.strip()

  @classmethod
  def get_mandatory_instruction(cls, lang_code: Optional[str]) -> str:
    """Generates mandatory instruction string enforcing section heading translation."""
    lang_display = cls.get_display_name(lang_code)
    return (
        f"[MANDATORY LANGUAGE INSTRUCTION: The ENTIRE summary, including ALL section headings (##), "
        f"bullet points, and conclusions, must be written strictly in {lang_display}. "
        f"Do not output headings in Italian or any other language unless the target language is Italian.]"
    )

  @classmethod
  def localize_email(cls, template: str, target_lang: Optional[str]) -> str:
    """Replaces localized tokens in email HTML template, handling both dynamic tokens and legacy templates."""
    locale = cls.get_locale(target_lang)
    localized = (
        template.replace("{email_heading}", locale.email.heading)
        .replace("{label_duration}", locale.email.duration_label)
        .replace("{label_watch}", locale.email.watch_action)
    )

    # Also adapt hardcoded boilerplates from older or custom database templates
    for other_code, other_loc in cls._LOCALES.items():
      if other_code != locale.code:
        localized = localized.replace(
            f"<h2>{other_loc.email.heading}</h2>",
            f"<h2>{locale.email.heading}</h2>",
        )
        localized = localized.replace(
            f"<strong>{other_loc.email.duration_label}</strong>",
            f"<strong>{locale.email.duration_label}</strong>",
        )
        localized = localized.replace(
            f">{other_loc.email.watch_action}</a>",
            f">{locale.email.watch_action}</a>",
        )

    return localized

  @classmethod
  def list_supported_languages(cls) -> List[str]:
    """Returns a list of all registered language codes."""
    return list(cls._LOCALES.keys())

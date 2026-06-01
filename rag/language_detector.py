"""
rag/language_detector.py
------------------------
Detects the language of a user query before embedding.

Used by retriever.py to:
- Log which language was detected
- Fall back to English if confidence is too low
- Pass language metadata through to context_builder.py

Relies on the `langdetect` library (lightweight, no API call needed).

Usage:
    from rag.language_detector import detect_language, is_english

    lang = detect_language("राजस्व के अनुसार शीर्ष ग्राहक")
    # → DetectionResult(language='hi', confidence=0.99, is_reliable=True)
"""

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from langdetect import detect_langs, LangDetectException
from langdetect.lang_detect_exception import LangDetectException

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

# Minimum confidence to trust the detected language.
# Queries below this fall back to "en".
LANG_DETECT_CONFIDENCE = float(os.getenv("LANG_DETECT_CONFIDENCE", "0.8"))

# Human-readable language names for logging / UI display
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "ar": "Arabic",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "nb": "Norwegian",
    "cs": "Czech",
    "hu": "Hungarian",
    "bn": "Bengali",
    "he": "Hebrew",
    "fa": "Persian",
}


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class DetectionResult:
    """
    Result of a language detection call.

    Attributes:
        language:    ISO 639-1 language code (e.g. 'en', 'hi', 'fr').
        confidence:  Detection confidence 0.0–1.0.
        is_reliable: True if confidence >= LANG_DETECT_CONFIDENCE threshold.
        language_name: Human-readable name (e.g. 'Hindi').
    """
    language:      str
    confidence:    float
    is_reliable:   bool
    language_name: str

    def __str__(self) -> str:
        status = "✅" if self.is_reliable else "⚠️ low confidence"
        return (
            f"{status} Detected: {self.language_name} "
            f"({self.language}) @ {self.confidence:.0%}"
        )


# ── Core detection ─────────────────────────────────────────────────────────────

def detect_language(text: str) -> DetectionResult:
    """
    Detect the language of a text string.

    Falls back to English if:
    - Text is too short (< 3 words) — unreliable for detection
    - langdetect raises an exception
    - Confidence is below LANG_DETECT_CONFIDENCE threshold

    Args:
        text: Input string (user query, any language).

    Returns:
        DetectionResult with language code, confidence, and reliability flag.
    """
    if not text or not text.strip():
        logger.warning("detect_language received empty string, defaulting to English.")
        return DetectionResult(
            language="en",
            confidence=0.0,
            is_reliable=False,
            language_name="English",
        )

    # Very short inputs are unreliable — skip detection
    if len(text.split()) < 3:
        logger.debug("Query too short for reliable detection, defaulting to English.")
        return DetectionResult(
            language="en",
            confidence=1.0,
            is_reliable=True,
            language_name="English",
        )

    try:
        # detect_langs returns a list of candidates sorted by probability
        candidates = detect_langs(text)

        if not candidates:
            raise LangDetectException(0, "No candidates returned")

        top = candidates[0]
        lang_code   = top.lang
        confidence  = round(top.prob, 4)
        is_reliable = confidence >= LANG_DETECT_CONFIDENCE

        # If not reliable enough, fall back to English
        if not is_reliable:
            logger.warning(
                "Low confidence detection (%.0f%%) for '%s'. Falling back to English.",
                confidence * 100, text[:50],
            )
            return DetectionResult(
                language="en",
                confidence=confidence,
                is_reliable=False,
                language_name="English",
            )

        language_name = LANGUAGE_NAMES.get(lang_code, lang_code.upper())

        result = DetectionResult(
            language=lang_code,
            confidence=confidence,
            is_reliable=is_reliable,
            language_name=language_name,
        )

        logger.debug("Language detection: %s", result)
        return result

    except LangDetectException as exc:
        logger.warning("langdetect failed: %s. Defaulting to English.", exc)
        return DetectionResult(
            language="en",
            confidence=0.0,
            is_reliable=False,
            language_name="English",
        )


# ── Convenience helpers ────────────────────────────────────────────────────────

def is_english(text: str) -> bool:
    """Return True if the query is detected as English."""
    return detect_language(text).language == "en"


def get_language_name(text: str) -> str:
    """Return the human-readable language name for a query string."""
    return detect_language(text).language_name


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_queries = [
        ("English",  "Show top 10 customers by revenue"),
        ("Hindi",    "राजस्व के अनुसार शीर्ष 10 ग्राहक दिखाओ"),
        ("French",   "Montrez les 10 meilleurs clients par revenus"),
        ("Spanish",  "Mostrar los 10 principales clientes por ingresos"),
        ("German",   "Zeige die 10 umsatzstärksten Kunden"),
        ("Japanese", "収益別トップ10顧客を表示"),
        ("Arabic",   "أظهر أفضل 10 عملاء حسب الإيرادات"),
        ("Short",    "top customers"),   # too short → defaults to English
        ("Empty",    ""),                # empty → defaults to English
    ]

    print(f"Confidence threshold : {LANG_DETECT_CONFIDENCE:.0%}\n")
    print(f"{'Label':<12} {'Query':<48} {'Result'}")
    print("-" * 90)

    for label, query in test_queries:
        result = detect_language(query)
        display_query = (query[:45] + "...") if len(query) > 45 else query
        print(f"{label:<12} {display_query:<48} {result}")
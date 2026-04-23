"""
tools/language_detector.py
Détection de langue légère et rapide.

Stratégie :
    1. langdetect (pip install langdetect) — wrapper Google language-detection.
    2. Fallback heuristique sur stopwords EN/FR/ES/DE/AR si langdetect absent.
    3. Ne lève jamais d'exception — retourne toujours un résultat safe.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import optionnel de langdetect
# ---------------------------------------------------------------------------
try:
    from langdetect import detect, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException
    DetectorFactory.seed = 42
    _LANGDETECT_AVAILABLE = True
    logger.info("langdetect disponible — détection de langue activée.")
except ImportError:
    _LANGDETECT_AVAILABLE = False
    logger.warning("langdetect non installé. Fallback heuristique activé. pip install langdetect")

# ---------------------------------------------------------------------------
# Stopwords heuristiques (fallback sans dépendance)
# ---------------------------------------------------------------------------
_STOPWORDS: dict[str, set[str]] = {
    "en": {
        "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "must",
        "that", "this", "these", "those", "with", "from", "they",
        "their", "there", "here", "what", "which", "who", "how",
        "when", "where", "why", "not", "but", "and", "for", "its",
        "it", "he", "she", "we", "you", "i", "my", "your", "our",
        "an", "a", "of", "in", "on", "at", "by", "as", "or", "if",
    },
    "fr": {
        "le", "la", "les", "un", "une", "des", "du", "de", "et",
        "est", "sont", "était", "ont", "avec", "pour", "dans", "sur",
        "par", "que", "qui", "ce", "se", "ne", "pas", "plus", "aussi",
        "mais", "ou", "donc", "car", "leur", "leurs", "cette", "ces",
        "au", "aux", "il", "elle", "ils", "elles", "nous", "vous",
        "je", "tu", "mon", "ton", "son", "notre", "votre",
    },
    "es": {
        "el", "la", "los", "las", "un", "una", "de", "del", "al",
        "es", "son", "está", "están", "con", "para", "en", "por",
        "que", "se", "no", "lo", "le", "les", "me", "mi", "tu",
        "su", "nos", "ellos", "como", "más", "pero", "sino",
    },
    "de": {
        "der", "die", "das", "ein", "eine", "und", "ist", "sind",
        "war", "waren", "mit", "von", "zu", "in", "auf", "für",
        "nicht", "auch", "als", "an", "nach", "bei", "wie", "aber",
        "oder", "wenn", "dass", "sich", "ich", "du", "er", "sie",
        "wir", "ihr", "mein", "sein", "unser",
    },
    "ar": {
        "في", "من", "على", "إلى", "عن", "مع", "هذا", "هذه",
        "التي", "الذي", "كان", "كانت", "هو", "هي", "هم", "لا",
        "ما", "أن", "إن", "قد", "أو", "لم", "لن", "كل",
    },
    "zh-cn": {
        "的", "了", "在", "是", "我", "有", "和", "就", "不",
        "人", "都", "一", "一个", "上", "也", "很", "到",
        "说", "要", "去", "你", "会", "着", "没有",
    },
    "pt": {
        "o", "a", "os", "as", "um", "uma", "de", "do", "da",
        "e", "é", "são", "com", "para", "em", "por", "que",
        "se", "não", "eles", "como", "mais", "mas",
    },
    "it": {
        "il", "la", "i", "le", "un", "una", "e", "è", "sono",
        "con", "per", "in", "da", "che", "se", "non", "lo",
        "mi", "tu", "su", "noi", "loro", "come", "più", "ma",
    },
    "ru": {
        "и", "в", "не", "на", "я", "что", "с", "по", "он",
        "она", "они", "мы", "вы", "к", "из", "за", "у",
        "для", "как", "но", "или", "если", "когда", "где", "почему",
    },
    "ja": {
        "の", "に", "は", "を", "た", "が", "で", "て", "と",
        "し", "れ", "さ", "ある", "いる", "も", "する", "から",
        "な", "こと", "として", "い", "や", "など", "なぜ",
        "どうして", "しかし", "または", "もし", "いつ", "どこ",
    },
    "ko": {
        "의", "에", "는", "을", "이", "가", "으로", "하다",
        "에서", "과", "도", "로", "와", "한", "하지만", "또는",
        "만약", "언제", "어디",
    },
}

_MIN_WORDS = 15  # Seuil minimum pour une analyse fiable


def _heuristic_detect(text: str) -> str:
    """Détection par comptage de stopwords — fallback sans dépendance."""
    words = set(re.findall(r"\b[a-zA-ZÀ-ÿ\u0600-\u06FF]+\b", text.lower()))
    scores = {lang: len(words & sw) for lang, sw in _STOPWORDS.items()}
    if not any(scores.values()):
        return "unknown"
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] >= 3 else "unknown"


def detect_language(text: str) -> str:
    """
    Détecte la langue principale d'un texte.
    Returns: Code ISO 639-1 (ex: "en", "fr", "es") ou "unknown".
    """
    if not text or not text.strip():
        return "unknown"
    sample = text.strip()[:2000]
    if _LANGDETECT_AVAILABLE:
        try:
            return detect(sample)
        except LangDetectException:
            logger.debug("langdetect a échoué — fallback heuristique.")
    return _heuristic_detect(sample)


def is_english(text: str) -> bool:
    """
    Retourne True uniquement si le texte est en anglais.

    Règles :
      - Texte trop court (< _MIN_WORDS mots) → True  (bénéfice du doute)
      - Langue détectée == "en"              → True
      - Langue == "unknown"                  → True  (code, texte très technique…)
      - Toute autre langue                   → False
    """
    if not text or not text.strip():
        return False

    word_count = len(text.strip().split())
    if word_count < _MIN_WORDS:
        logger.debug("Texte court (%d mots) — langue non vérifiée, laissé passer.", word_count)
        return True

    lang = detect_language(text)
    logger.info("Langue détectée : '%s' (%d mots)", lang, word_count)

    if lang == "en":
        return True
    if lang == "unknown":
        return _heuristic_detect(text[:2000]) in ("en", "unknown")
    return False


# ---------------------------------------------------------------------------
# Rejection messages — localized, displayed in the user's detected language
# ---------------------------------------------------------------------------

_LANGUAGE_NAMES: dict[str, str] = {
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "ar": "Arabic",
    "zh-cn": "Chinese",
    "pt": "Portuguese",
    "it": "Italian",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
}

_REJECTION_TEMPLATE = (
    "**Unsupported Language — {language} detected**\n\n"
    "SummAI is currently limited to English-language content.\n"
    "Please submit your text in English to receive a summary.\n\n"
    "Note: Q&A mode is unavailable for non-English submissions."
)

_DEFAULT_REJECTION = (
    "**Unsupported Language**\n\n"
    "SummAI is currently limited to English-language content.\n"
    "Please submit your text in English to receive a summary.\n\n"
    "Note: Q&A mode is unavailable for non-English submissions."
)


def get_rejection_message(text: str) -> str:
    """Return a localized rejection message based on the detected language."""
    lang = detect_language(text)
    language_name = _LANGUAGE_NAMES.get(lang)

    if language_name is None:
        return _DEFAULT_REJECTION

    return _REJECTION_TEMPLATE.format(language=language_name)
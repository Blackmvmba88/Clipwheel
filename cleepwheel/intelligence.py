from __future__ import annotations

import json
import re

from .domain import ClipboardClassification


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>()]+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
SONG_FILE_RE = re.compile(r"\b[\w .,'@()&+-]+\.(?:mp3|wav|aiff?|flac|m4a|aac|ogg)\b", re.IGNORECASE)
MUSIC_LINK_RE = re.compile(
    r"\b(?:open\.spotify\.com|music\.apple\.com|soundcloud\.com|bandcamp\.com|youtu\.be|youtube\.com/watch)",
    re.IGNORECASE,
)
MUSIC_METADATA_RE = re.compile(
    r"\b(?:bpm|key|lyrics?|letra|canci[oó]n|tema|track|artist|artista|album|[aá]lbum|verse|verso|estrofa|chorus|coro|hook|puente|bridge|intro|outro|feat\.?|ft\.|remix|master|mixdown|stems?)\b",
    re.IGNORECASE,
)
METACOMMAND_RE = re.compile(
    r"\b(?:clasifica|clasificar|categoriza|etiqueta|resume|resumir|analiza|analizar|explica|explicar|genera|generar|crea|crear|traduce|traducir|corrige|corregir|prompt|system prompt|metacomando|meta comando|instrucci[oó]n|act[uú]a como)\b",
    re.IGNORECASE,
)
SECRET_RE = re.compile(
    r"(api[_-]?key|access[_-]?token|secret|password|passwd|private[_ -]?key|bearer\s+[a-z0-9._~+/=-]{12,})",
    re.IGNORECASE,
)
CODE_RE = re.compile(
    r"(^|\n)\s*(def |class |function |import |from |const |let |var |return |if __name__|#include|SELECT |CREATE TABLE )",
    re.IGNORECASE,
)
COMMAND_RE = re.compile(
    r"^\s*(?:git|python3?|pip|npm|pnpm|yarn|curl|ssh|docker|brew|launchctl|sqlite3)\b",
    re.IGNORECASE,
)
TODO_RE = re.compile(r"(^|\n)\s*(?:[-*]\s*\[[ xX]\]|TODO\b|FIXME\b|#\s)", re.IGNORECASE)


def _snippet(text: str, width: int = 90) -> str:
    cleaned = " ".join(text.strip().split())
    if len(cleaned) <= width:
        return cleaned
    return cleaned[: width - 3] + "..."


def _looks_like_json(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return False
    try:
        json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return True


def _looks_like_lyrics(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    short_lines = sum(1 for line in lines if len(line) <= 72)
    repeated_lines = len(lines) - len({line.lower() for line in lines})
    section_markers = sum(
        1
        for line in lines
        if re.fullmatch(r"\[?(intro|outro|verse|verso|coro|chorus|hook|puente|bridge|estrofa)(\s+\d+)?\]?", line, re.IGNORECASE)
    )
    return section_markers > 0 or repeated_lines > 0 or short_lines / len(lines) >= 0.8


def _language_tags(text: str) -> list[str]:
    tags: list[str] = []
    lower = text.lower()
    if re.search(r"(^|\n)\s*(def |import |from .+ import )", text):
        tags.append("python")
    if any(token in lower for token in ("function ", "const ", "let ", "=>", "document.")):
        tags.append("javascript")
    if any(token in lower for token in ("select ", "insert into ", "create table", "pragma ")):
        tags.append("sql")
    if COMMAND_RE.search(text):
        tags.append("shell")
    return tags


def classify_text(content: str, entry_id: int | None = None) -> ClipboardClassification:
    text = content.strip()
    tags: list[str] = []
    reasons: list[str] = []
    category = "general"
    sensitivity = "normal"
    confidence = 0.45

    if not text:
        return ClipboardClassification(
            entry_id=entry_id,
            category="empty",
            tags=(),
            summary="Empty clipboard content",
            confidence=1.0,
            sensitivity="normal",
            reasons=("content is blank after trimming",),
        )

    if SECRET_RE.search(text):
        category = "credential"
        sensitivity = "sensitive"
        confidence = 0.95
        tags.append("secret")
        reasons.append("contains credential-like keywords or bearer token")
    elif METACOMMAND_RE.search(text):
        category = "metacommand"
        confidence = 0.87
        tags.append("instruction")
        tags.append("ai-command")
        reasons.append("contains instruction or prompt-like language")
    elif (
        SONG_FILE_RE.search(text)
        or MUSIC_LINK_RE.search(text)
        or MUSIC_METADATA_RE.search(text)
        or _looks_like_lyrics(text)
    ):
        category = "song"
        confidence = 0.88
        tags.append("music")
        if _looks_like_lyrics(text):
            tags.append("lyrics")
        if SONG_FILE_RE.search(text):
            tags.append("audio-file")
        if MUSIC_LINK_RE.search(text):
            tags.append("music-link")
        if MUSIC_METADATA_RE.search(text):
            tags.append("song-metadata")
        reasons.append("matches music, song, audio file, lyrics, or track metadata")
    elif _looks_like_json(text):
        category = "structured-data"
        confidence = 0.9
        tags.append("json")
        reasons.append("valid JSON payload")
    elif URL_RE.search(text):
        category = "link"
        confidence = 0.86
        tags.append("url")
        reasons.append("contains web URL")
    elif EMAIL_RE.search(text) or PHONE_RE.search(text):
        category = "contact"
        sensitivity = "personal"
        confidence = 0.84
        if EMAIL_RE.search(text):
            tags.append("email")
        if PHONE_RE.search(text):
            tags.append("phone")
        reasons.append("contains contact information")
    elif CODE_RE.search(text) or "```" in text:
        category = "code"
        confidence = 0.8
        tags.append("code")
        reasons.append("matches source-code structure")
    elif COMMAND_RE.search(text):
        category = "command"
        confidence = 0.78
        tags.append("command")
        reasons.append("starts with a common terminal command")
    elif TODO_RE.search(text):
        category = "task-note"
        confidence = 0.72
        tags.append("todo")
        reasons.append("contains task or note markers")
    elif len(text.split()) >= 25:
        category = "document"
        confidence = 0.62
        tags.append("long-form")
        reasons.append("long-form text")
    else:
        reasons.append("no specialized pattern matched")

    for tag in _language_tags(text):
        if tag not in tags:
            tags.append(tag)
    if len(text) > 5000 and "large" not in tags:
        tags.append("large")

    return ClipboardClassification(
        entry_id=entry_id,
        category=category,
        tags=tuple(tags),
        summary=_snippet(text),
        confidence=confidence,
        sensitivity=sensitivity,
        reasons=tuple(reasons),
    )

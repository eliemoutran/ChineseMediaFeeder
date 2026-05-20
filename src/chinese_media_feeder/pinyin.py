from __future__ import annotations

from pypinyin import Style, pinyin


PUNCTUATION_MAP = {
    "，": ",",
    "。": ".",
    "！": "!",
    "？": "?",
    "：": ":",
    "；": ";",
}


def chinese_to_pinyin(text: str) -> str:
    syllables: list[str] = []
    for item in pinyin(text, style=Style.TONE, neutral_tone_with_five=False, errors=_handle_non_chinese):
        syllables.append(item[0])
    return _clean_spacing(" ".join(syllables))


def _handle_non_chinese(chars: str) -> list[str]:
    tokens: list[str] = []
    ascii_run: list[str] = []
    for char in chars:
        if char.isascii() and char.isalnum():
            ascii_run.append(char)
            continue

        if ascii_run:
            tokens.append("".join(ascii_run))
            ascii_run = []
        tokens.append(PUNCTUATION_MAP.get(char, char))

    if ascii_run:
        tokens.append("".join(ascii_run))
    return tokens


def _clean_spacing(text: str) -> str:
    for mark in [",", ".", "!", "?", ":", ";"]:
        text = text.replace(f" {mark}", mark)
    return " ".join(text.split())

from __future__ import annotations

import logging

import jieba
from pypinyin import Style, pinyin


jieba.setLogLevel(logging.WARNING)

PUNCTUATION_MAP = {
    "\uff0c": ",",
    "\u3002": ".",
    "\uff01": "!",
    "\uff1f": "?",
    "\uff1a": ":",
    "\uff1b": ";",
}


def chinese_to_pinyin(text: str) -> str:
    tokens = []
    for word in jieba.cut(text):
        token = _word_to_pinyin(word)
        if token:
            tokens.append(token)
    return _clean_spacing(" ".join(tokens))


def _word_to_pinyin(word: str) -> str:
    if not word or word.isspace():
        return ""

    pieces = pinyin(
        word,
        style=Style.TONE,
        neutral_tone_with_five=False,
        v_to_u=True,
        errors=_handle_non_chinese,
    )
    return "".join(item[0] for item in pieces)


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

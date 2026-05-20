from chinese_media_feeder.pinyin import chinese_to_pinyin


def test_chinese_to_pinyin_uses_tone_marks():
    assert chinese_to_pinyin("你好，佩奇。") == "nǐ hǎo, pèi qí."


def test_chinese_to_pinyin_preserves_contiguous_latin_text():
    assert chinese_to_pinyin("今天OK吗？") == "jīn tiān OK ma?"


def test_chinese_to_pinyin_preserves_contiguous_digits():
    assert chinese_to_pinyin("第12集") == "dì 12 jí"

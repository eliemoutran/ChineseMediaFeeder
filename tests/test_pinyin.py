from chinese_media_feeder.pinyin import chinese_to_pinyin


def test_chinese_to_pinyin_uses_tone_marks():
    assert chinese_to_pinyin("你好，佩奇。") == "nǐ hǎo, pèi qí."

from chinese_media_feeder.pinyin import chinese_to_pinyin


def test_chinese_to_pinyin_uses_tone_marks():
    assert chinese_to_pinyin("\u4f60\u597d\uff0c\u4f69\u5947\u3002") == "n\u01d0h\u01ceo, p\u00e8iq\u00ed."


def test_chinese_to_pinyin_uses_jieba_phrase_spacing():
    result = chinese_to_pinyin("\u6211\u5bb6\u79bb\u5065\u8eab\u623f\u53ea\u6709\u4e94\u5206\u949f")

    assert "ji\u00e0nsh\u0113nf\u00e1ng" in result
    assert "ji\u00e0n sh\u0113n f\u00e1ng" not in result


def test_chinese_to_pinyin_uses_u_umlaut_for_vowel_u():
    assert chinese_to_pinyin("\u5973") == "n\u01da"


def test_chinese_to_pinyin_preserves_contiguous_latin_text():
    assert chinese_to_pinyin("\u4eca\u5929OK\u5417\uff1f") == "j\u012bnti\u0101n OK ma?"


def test_chinese_to_pinyin_preserves_contiguous_digits():
    assert chinese_to_pinyin("\u7b2c12\u96c6") == "d\u00ec 12 j\u00ed"

from vap.normalize import strip_accent


def test_strips_tone_marks():
    assert strip_accent("Tôi yêu Việt Nam") == "toi yeu viet nam"


def test_strips_d_stroke():
    assert strip_accent("Đồng") == "dong"
    assert strip_accent("đồng") == "dong"


def test_lowercases():
    assert strip_accent("HÀ NỘI") == "ha noi"


def test_handles_nfd_input():
    import unicodedata

    nfd = unicodedata.normalize("NFD", "Việt")
    assert strip_accent(nfd) == "viet"


def test_plain_ascii_unchanged():
    assert strip_accent("hello") == "hello"


def test_empty():
    assert strip_accent("") == ""

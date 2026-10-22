from vap.eval import score

# 3 tokens + 3 tokens = 6
GOLD = ["Tôi yêu em", "Hà Nội đẹp"]


def test_perfect_when_lowercased():
    pred = ["tôi yêu em", "hà nội đẹp"]
    r = score(GOLD, pred)
    assert r.accuracy == 1.0
    assert r.total == 6
    assert r.correct == 6


def test_counts_partial():
    pred = ["tôi yêu anh", "hà nội đẹp"]
    r = score(GOLD, pred)
    assert r.total == 6
    assert r.correct == 5
    assert round(r.accuracy, 4) == 0.8333


def test_skip_counted_not_dropped():
    pred = ["tôi yêu em", "hà nội"]
    r = score(GOLD, pred)
    assert r.skipped == 1
    assert r.total == 3


def test_skip_all_reports_zero_accuracy_not_crash():
    r = score(GOLD, ["x"])
    assert r.skipped == 2
    assert r.accuracy == 0.0

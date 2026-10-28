from app.core.fmt import format_clock


def test_format_clock_centis():
    assert format_clock(3725.4, centis=True) == "01:02:05.40"


def test_format_clock_negative():
    assert format_clock(-12) == "-00:00:12"


def test_format_clock_truncates_not_rounds():
    # 59.99秒を 01:00 と表示すると、まだ終わっていないのに 0 を飛ばして見える
    assert format_clock(59.99) == "00:00:59"


def test_format_clock_countdown_rounds_up():
    # カウントダウンは 0.4 秒残りを 00:00:01 と見せ、00:00:00 は終了時だけ
    assert format_clock(0.4, ceil=True) == "00:00:01"
    assert format_clock(0, ceil=True) == "00:00:00"

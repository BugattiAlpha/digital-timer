from app.core.geometry import clamp_rect

SCREEN = (0, 0, 1920, 1080)


def test_clamp_rect_offscreen_moves_inside():
    assert clamp_rect((5000, 5000, 300, 100), [SCREEN]) == (1620, 980, 300, 100)


def test_clamp_rect_onscreen_unchanged():
    assert clamp_rect((100, 100, 300, 100), [SCREEN]) == (100, 100, 300, 100)


def test_clamp_rect_negative_moves_inside():
    assert clamp_rect((-500, -50, 300, 100), [SCREEN]) == (0, 0, 300, 100)


def test_clamp_rect_keeps_position_on_second_monitor():
    second = (1920, 0, 2560, 1440)
    assert clamp_rect((3000, 500, 300, 100), [SCREEN, second]) == (3000, 500, 300, 100)


def test_clamp_rect_too_big_shrinks_to_screen():
    assert clamp_rect((0, 0, 4000, 3000), [SCREEN]) == (0, 0, 1920, 1080)


def test_clamp_rect_snaps_to_nearest_screen():
    second = (1920, 0, 1920, 1080)
    # 2台目の右側に外れた → 2台目の右端に戻る
    assert clamp_rect((5000, 100, 300, 100), [SCREEN, second]) == (3540, 100, 300, 100)

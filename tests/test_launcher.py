from pathlib import Path

BAT = Path(__file__).resolve().parents[1] / "Digital_Timer_start.bat"


def test_bat_is_cp932_crlf():
    raw = BAT.read_bytes()
    raw.decode("cp932")  # Shift-JIS で読めること（UTF-8 だと cmd が誤解析する）
    assert b"\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")  # LF 単独の行が無い


def test_bat_contents():
    text = BAT.read_bytes().decode("cp932")
    assert 'cd /d "%~dp0"' in text
    assert r".venv\Scripts\pythonw.exe" in text
    assert "-m app.main" in text
    assert "if errorlevel 1" in text
    assert "chcp" not in text.lower()

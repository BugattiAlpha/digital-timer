@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo [Digital Timer] 仮想環境 .venv が見つかりません。
    echo このフォルダで次を実行してセットアップしてください:
    echo   python -m venv .venv
    echo   .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)

rem コンソールを残さないよう pythonw で別プロセスとして起動する（既に起動中なら前面に出るだけ）
start "" ".venv\Scripts\pythonw.exe" -m app.main
if errorlevel 1 (
    echo [Digital Timer] 起動に失敗しました。
    pause
    exit /b 1
)
exit /b 0

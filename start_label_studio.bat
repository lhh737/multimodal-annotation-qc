@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动 Label Studio: http://localhost:8080
echo 关闭此窗口即停止服务。
".venv\Scripts\label-studio.exe" start --port 8080 --data-dir "%~dp0ls_data" --enable-legacy-api-token
pause

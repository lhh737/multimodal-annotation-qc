@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动数据服务: http://localhost:8000 (CORS enabled)
echo 关闭此窗口即停止服务。
".venv\Scripts\python.exe" scripts\serve_data.py 8000 "%~dp0data"
pause

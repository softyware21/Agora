@echo off
chcp 65001 >nul
cd /d "%~dp0"
python agora.py --login-claude
pause

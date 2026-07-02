@echo off
rem  =========================================================
rem    KODARI CAD SaaS MVP LOCAL LAUNCHER (BAT Wrapper)
rem          - 코다리 부장 로컬 기동기 (BAT 바이패스) - 
rem  =========================================================

cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0run_local.ps1"
pause

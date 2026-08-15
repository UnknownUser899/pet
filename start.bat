@echo off
cd /d %~dp0
set MODEL=
for %%f in (models\*.gguf) do set MODEL=%%f
if "%MODEL%"=="" (
  echo No .gguf model found in models\ — see README.md
  pause
  exit /b 1
)
if not exist bin\llama-server.exe (
  echo llama-server.exe not found in bin\ — see README.md
  pause
  exit /b 1
)
echo starting model server: %MODEL%
start "llama-server" /min bin\llama-server.exe -m "%MODEL%" -c 8192 --port 8080
timeout /t 2 >nul
python server.py

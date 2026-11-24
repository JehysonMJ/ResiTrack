@echo off
chcp 65001 >nul
cd /d "%~dp0"
title ResiTrack
where python >nul 2>nul
if errorlevel 1 (
  echo No encontre Python. Instalalo desde https://www.python.org/downloads/
  echo y marca la casilla "Add python.exe to PATH" durante la instalacion.
  pause
  exit /b
)
if not exist .venv (
  echo Creando entorno virtual...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
echo Instalando dependencias (solo tarda la primera vez)...
pip install -q -r requirements.txt
echo.
echo Abriendo ResiTrack en http://localhost:5000  (cierra esta ventana para detenerlo)
start "" cmd /c "timeout /t 3 >nul & start http://localhost:5000"
python app.py
pause

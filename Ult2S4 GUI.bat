@echo off
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw ult2s4_gui.py & exit /b)
where pythonw >nul 2>nul && (start "" pythonw ult2s4_gui.py & exit /b)
echo Python was not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH"),
echo then run install_numpy.bat and this file again.
pause

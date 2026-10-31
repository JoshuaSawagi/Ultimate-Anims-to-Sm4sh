@echo off
echo Installing numpy for ult2s4.py...
where py >nul 2>nul && (py -m pip install --upgrade numpy & goto check)
where python >nul 2>nul && (python -m pip install --upgrade numpy & goto check)
echo.
echo Python was not found. Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" in the installer), then run this file again.
goto end
:check
echo.
where py >nul 2>nul && (py -c "import numpy; print('numpy', numpy.__version__, 'is installed - ult2s4.py is ready')") || (python -c "import numpy; print('numpy', numpy.__version__, 'is installed - ult2s4.py is ready')")
:end
echo.
pause

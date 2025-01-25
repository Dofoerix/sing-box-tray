.\venv\scripts\activate
pyinstaller --noconsole --onefile --icon=icon.ico --add-data "icon_base.png:." sing-box-tray.py
Read-Host -Prompt 'Press Enter to continue'
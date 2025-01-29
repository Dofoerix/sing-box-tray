.\venv\scripts\activate
pyinstaller --noconsole --onefile --icon=icon.ico --add-data "icon_base.png:." --add-data "sb_tray_config.dist.json:." sing-box-tray.py
Read-Host -Prompt 'Press Enter to continue'
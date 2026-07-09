python -m PyInstaller --onefile -n=DRC91Cdaemon --icon=.\DRC91C.ico --add-data "DRC91C.ico;." --paths=..\..\common --hidden-import=FuncLogger --hidden-import=paths .\DRC91Cdaemon.py

python -m PyInstaller --onefile -n=Lakeshore330 --icon=.\Lakeshore330.ico --add-data "Lakeshore330.ico;." --paths=..\..\common --hidden-import=FuncLogger --hidden-import=paths .\Lakeshore330.py

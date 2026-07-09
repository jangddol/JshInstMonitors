python -m PyInstaller --onefile -n=ArduinoADCReceiver --icon=.\guage.ico --add-data "guage.ico;." --paths=..\..\common --hidden-import=FuncLogger --hidden-import=paths .\ArduinoADCReceiver.py

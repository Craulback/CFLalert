pip install -r requirements.txt
pyinstaller --clean --distpath . --add-data=".\cfl.ico;." --onefile --icon=cfl.ico CFLalert.pyw
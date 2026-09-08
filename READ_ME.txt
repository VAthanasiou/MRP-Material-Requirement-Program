### ΓΙΑ INSTALLER ###
py -m PyInstaller --noconfirm --onedir --noconsole --icon="app_icon.ico" --collect-all streamlit --copy-metadata plotly --copy-metadata pandas --hidden-import openpyxl --hidden-import webview run_mrp.py

### ΓΙΑ DATABASE ### (στο C:\MRP)
python init_db.py
py -m streamlit migrate_excel_to_db.py
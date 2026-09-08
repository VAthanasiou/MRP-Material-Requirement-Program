import os
import sys
import time
import urllib.request
import webview
import multiprocessing
import streamlit.web.cli as stcli

def run_streamlit(script_path):
    # Κρύβουμε τα μηνύματα μέσα στο νέο process για να μην κρασάρει αόρατα
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
    sys.argv = ["streamlit", "run", script_path, "--global.developmentMode=false", "--server.headless=true", "--server.port=8501"]
    sys.exit(stcli.main())

if __name__ == "__main__":
    # ΠΟΛΥ ΣΗΜΑΝΤΙΚΟ: Απαραίτητο για να δουλέψει το multiprocessing σε .exe στα Windows
    multiprocessing.freeze_support()
    
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
        
    os.chdir(application_path)
    main_script = os.path.join(application_path, "appV.py")

    # Αντί για threading, φτιάχνουμε μια εντελώς νέα διεργασία!
    p = multiprocessing.Process(target=run_streamlit, args=(main_script,))
    p.daemon = True
    p.start()

    # Έξυπνη αναμονή
    for _ in range(30):
        try:
            urllib.request.urlopen("http://localhost:8501", timeout=1)
            break 
        except Exception:
            time.sleep(1)

    # Ανοίγουμε το παράθυρο
    webview.create_window('MRP by V', 'http://localhost:8501')
    webview.start()

    # Όταν ο χρήστης κλείσει το παράθυρο, σκοτώνουμε τη διεργασία του Streamlit
    p.terminate()
    os._exit(0)
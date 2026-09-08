import streamlit as st

st.set_page_config(page_title="MRP Material Requirement Programm", layout="wide")

mrp_page = st.Page("pages/1_MRP.py", title="MRP Πρόγραμμα", icon="⚛️", default=True)
db_page = st.Page("pages/2_Database.py", title="Database", icon="🗄️")

pg = st.navigation([mrp_page, db_page])
pg.run()

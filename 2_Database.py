import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

import data_utils as du

st.title("🗄️ Διαχείριση Database")
st.caption(f"Αρχείο βάσης: `{du.DB_PATH}`")

categories = du.get_categories()
if not categories:
    st.error("Δεν βρέθηκαν δεδομένα στη βάση. Τρέξε πρώτα το migrate_excel_to_db.py.")
    st.stop()

if "PP" in categories:
    categories.remove("PP")
    categories.insert(0, "PP")

# --- ΕΝΙΑΙΑ ΕΠΙΛΟΓΗ ΚΑΤΗΓΟΡΙΑΣ ---
category = st.pills("Επιλέξτε κατηγορία υλικού:", categories, default=categories[0])

sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs(
    ["🧪 Υλικά (Materials)", "🧬 Μηχανικές Ιδιότητες", "♻️ Erema Materials", "📋 Συνταγές (προβολή)"]
)

# =========================================================================
with sub_tab1:
    st.subheader(f"Λίστα Υλικών: {category}")

    with du.get_connection() as conn:
        mat_df = pd.read_sql(
            "SELECT id, code AS Code, material AS Material, stock_kg AS 'Stock (kg)' "
            "FROM materials WHERE category = ? ORDER BY material",
            conn, params=(category,)
        )

    st.caption("Πρόσθεσε γραμμές με **'+ Add row'**, ή σβήσε επιλέγοντας τη γραμμή και πατώντας το εικονίδιο διαγραφής.")
    edited_mat = st.data_editor(
        mat_df, num_rows="dynamic", width='stretch', key=f"mat_editor_{category}",
        column_config={"id": None},  # κρυφή στήλη, μόνο για εσωτερική χρήση
    )

    if st.button("💾 Αποθήκευση Υλικών", key=f"save_materials_{category}"):
        # --- 1ος Έλεγχος: Εύρεση Διπλοτύπων ---
        is_valid = True
        seen_materials = set()
        seen_codes = set()
        
        for _, row in edited_mat.iterrows():
            material = du.clean_text(row.get("Material", ""))
            code = du.clean_text(row.get("Code", ""))
            
            if not material:  # Αν η γραμμή είναι άδεια, την αγνοούμε
                continue
                
            # Ελέγχουμε το υλικό (αγνοώντας κεφαλαία/μικρά)
            mat_key = du.normalize_material_name(material)
            if mat_key in seen_materials:
                st.error(f"❗ Το υλικό '{material}' υπάρχει παραπάνω από μία φορά. Παρακαλώ διαγράψτε ή αλλάξτε το διπλότυπο.")
                is_valid = False
            seen_materials.add(mat_key)
            
            # Ελέγχουμε τον κωδικό (αγνοώντας κενά/κεφαλαία)
            if code:
                code_key = code.lower()
                if code_key in seen_codes:
                    st.error(f"❗ Ο κωδικός '{code}' χρησιμοποιείται ήδη σε άλλο υλικό.")
                    is_valid = False
                seen_codes.add(code_key)

        # --- 2ος Έλεγχος: Αποθήκευση μόνο αν όλα είναι σωστά ---
        if is_valid:
            with du.get_connection() as conn:
                conn.execute("DELETE FROM materials WHERE category = ?", (category,))
                for _, row in edited_mat.iterrows():
                    material = du.clean_text(row.get("Material", ""))
                    if not material:
                        continue
                    conn.execute(
                        "INSERT INTO materials (category, code, material, stock_kg) VALUES (?,?,?,?)",
                        (category, du.clean_text(row.get("Code", "")), material, row.get("Stock (kg)") or None)
                    )
            st.success("✅ Αποθηκεύτηκε.")
            # 2. Προσθήκη μικρής παύσης για να προλάβει ο χρήστης να το διαβάσει
            import time
            time.sleep(1.5)
            st.rerun()

# =========================================================================
with sub_tab2:
    st.subheader(f"Μηχανικές Ιδιότητες: {category}")

    with du.get_connection() as conn:
        mech_df = pd.read_sql("SELECT * FROM mech_properties WHERE category = ? ORDER BY title", conn, params=(category,))

    edited_mech = st.data_editor(
        mech_df, num_rows="dynamic", width='stretch', key=f"mech_editor_{category}",
        column_config={
            "id": None,         
            "category": None,   
            "code": "Κωδικός (KY)",
            "title": "Περιγραφή / Υλικό",
            "mfi": "MFI (g/10min)",
            "density": "Density (g/cm^3)",
            "hardness_rockwell_r": "Hardness Rockwell R",
            "hardness_shore_d": "Hardness Shore D",
            "tensile_modulus": "Tensile Modulus (MPa)",
            "flexural_mod": "Flexural Mod (MPa)",
            "impact": "Impact (kJ/m^2)",
            "tensile_strain_yield": "Tensile Strain Yield (%)",
            "tensile_strain_break": "Tensile Strain Break (%)",
            "tensile_break_strength": "Tensile Break Strength (MPa)",
            "tensile_yield_strength": "Tensile Yield Strength (MPa)",
            "hdt": "HDT (.45 MPa)",
            "vicat": "Vicat"
        },
    )

    if st.button("💾 Αποθήκευση Μηχανικών Ιδιοτήτων", key=f"save_mech_{category}"):
        with du.get_connection() as conn:
            conn.execute("DELETE FROM mech_properties WHERE category = ?", (category,))
            for _, row in edited_mech.iterrows():
                title = du.clean_text(row.get("title", ""))
                if not title:
                    continue
                conn.execute(
                    """INSERT INTO mech_properties
                       (category, code, title, mfi, density, hardness_rockwell_r, hardness_shore_d,
                        tensile_modulus, flexural_mod, impact, tensile_strain_yield, tensile_strain_break,
                        tensile_break_strength, tensile_yield_strength, hdt, vicat)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (category, 
                     row.get("code"), 
                     title, 
                     du.clean_numeric(row.get("mfi")), 
                     du.clean_numeric(row.get("density")),
                     du.clean_numeric(row.get("hardness_rockwell_r")), 
                     du.clean_numeric(row.get("hardness_shore_d")), 
                     du.clean_numeric(row.get("tensile_modulus")),
                     du.clean_numeric(row.get("flexural_mod")), 
                     du.clean_numeric(row.get("impact")), 
                     du.clean_numeric(row.get("tensile_strain_yield")),
                     du.clean_numeric(row.get("tensile_strain_break")), 
                     du.clean_numeric(row.get("tensile_break_strength")),
                     du.clean_numeric(row.get("tensile_yield_strength")), 
                     du.clean_numeric(row.get("hdt")), 
                     du.clean_numeric(row.get("vicat")))
                )
        st.success("✅ Αποθηκεύτηκε.")
        # 2. Προσθήκη μικρής παύσης για να προλάβει ο χρήστης να το διαβάσει
        import time
        time.sleep(1.5)
        st.rerun()

# =========================================================================
with sub_tab3:
    st.subheader("Erema Materials (κοινό για όλες τις κατηγορίες)")
    st.caption("Αυτός ο πίνακας δεν επηρεάζεται από την παραπάνω επιλογή κατηγορίας.")

    with du.get_connection() as conn:
        erema_df = pd.read_sql("SELECT id, code AS Κωδικός, description AS Περιγραφή FROM erema_materials", conn)

    edited_erema = st.data_editor(
        erema_df, num_rows="dynamic", width='stretch', key="erema_editor",
        column_config={"id": None},
    )

    if st.button("💾 Αποθήκευση Erema Materials", key="save_erema"):
        # --- 1ος Έλεγχος: Εύρεση Διπλοτύπων ---
        is_valid = True
        seen_desc = set()
        seen_codes = set()
        
        for _, row in edited_erema.iterrows():
            desc = du.clean_text(row.get("Περιγραφή", ""))
            code = du.clean_text(row.get("Κωδικός", ""))
            
            if not desc:
                continue
                
            desc_key = du.normalize_material_name(desc)
            if desc_key in seen_desc:
                st.error(f"❗ Η περιγραφή '{desc}' υπάρχει παραπάνω από μία φορά. Παρακαλώ διαγράψτε ή αλλάξτε το διπλότυπο.")
                is_valid = False
            seen_desc.add(desc_key)
            
            if code:
                code_key = code.lower()
                if code_key in seen_codes:
                    st.error(f"❗ Ο κωδικός '{code}' χρησιμοποιείται ήδη σε άλλη εγγραφή Erema.")
                    is_valid = False
                seen_codes.add(code_key)

        # --- 2ος Έλεγχος: Αποθήκευση μόνο αν όλα είναι σωστά ---
        if is_valid:
            with du.get_connection() as conn:
                conn.execute("DELETE FROM erema_materials")
                for _, row in edited_erema.iterrows():
                    desc = du.clean_text(row.get("Περιγραφή", ""))
                    if not desc:
                        continue
                    conn.execute(
                        "INSERT INTO erema_materials (code, description) VALUES (?, ?)",
                        (du.clean_text(row.get("Κωδικός", "")), desc)
                    )
            st.success("✅ Αποθηκεύτηκε.")
            # 2. Προσθήκη μικρής παύσης για να προλάβει ο χρήστης να το διαβάσει
            import time
            time.sleep(1.5)
            st.rerun()

# =========================================================================
with sub_tab4:
    st.subheader(f"Συνταγές: {category}")
    st.caption("Εδώ μπορείτε να δείτε και να επεξεργαστείτε τα βασικά στοιχεία των συνταγών (Ετήσια Κατανάλωση, Erema κλπ).")

    # Διακόπτης Επεξεργασίας
    edit_mode = st.toggle("✏️ Επεξεργασία Δεδομένων", key=f"toggle_edit_recipes_{category}")

    with du.get_connection() as conn:
        # Φέρνουμε ΚΑΙ το κρυφό 'id' από τη βάση, είναι ζωτικής σημασίας για την ασφαλή επεξεργασία!
        rec_df = pd.read_sql(
            "SELECT id, title AS Τίτλος, annual_consumption_kg AS 'Ετήσια Κατανάλωση (kg)', "
            "total_return_pct AS 'Ποσοστό Επιστροφής (%)', erema_category AS 'Erema Category' "
            "FROM recipes WHERE category = ? ORDER BY title",
            conn, params=(category,)
        )

    if not edit_mode:
        # --- ΛΕΙΤΟΥΡΓΙΑ: ΜΟΝΟ ΠΡΟΒΟΛΗ (Read-Only) ---
        view_df = rec_df.drop(columns=["id"]).copy() # Πετάμε το id για να μην το βλέπει ο χρήστης
        
        view_df["Ετήσια Κατανάλωση (kg)"] = pd.to_numeric(view_df["Ετήσια Κατανάλωση (kg)"], errors="coerce").fillna(0)
        view_df["Ποσοστό Επιστροφής (%)"] = pd.to_numeric(view_df["Ποσοστό Επιστροφής (%)"], errors="coerce").fillna(0)

        st.dataframe(
            du.with_one_based_index(view_df), 
            width='stretch',
            column_config={
                "Ετήσια Κατανάλωση (kg)": st.column_config.NumberColumn("Ετήσια Κατανάλωση (kg)", format="%,.0f"),
                "Ποσοστό Επιστροφής (%)": st.column_config.NumberColumn("Ποσοστό Επιστροφής (%)", format="%.1f")
            }
        )
    else:
        # --- ΛΕΙΤΟΥΡΓΙΑ: ΕΠΕΞΕΡΓΑΣΙΑ (Edit Mode) ---
        st.warning("⚠️ **ΠΡΟΣΟΧΗ:** Αλλαγές εδώ αποθηκεύονται απευθείας στη βάση. Αν διαγράψετε μια συνταγή από εδώ, θα διαγραφούν οριστικά και όλα τα υλικά/ποσοστά που της είχατε ορίσει!")
        
        edited_rec = st.data_editor(
            rec_df, 
            num_rows="dynamic", 
            width='stretch', 
            key=f"rec_editor_{category}",
            column_config={
                "id": None, # Κρύβουμε το ID
                "Τίτλος": st.column_config.TextColumn("Τίτλος", required=True),
                "Ετήσια Κατανάλωση (kg)": st.column_config.NumberColumn("Ετήσια Κατανάλωση (kg)", format="%,.0f", min_value=0.0),
                "Ποσοστό Επιστροφής (%)": st.column_config.NumberColumn("Ποσοστό Επιστροφής (%)", format="%.2f", min_value=0.0, max_value=100.0),
                "Erema Category": st.column_config.TextColumn("Erema Category")
            }
        )

        if st.button("💾 Αποθήκευση Συνταγών", key=f"save_recipes_{category}"):
            
            # -- 1ος Έλεγχος: Εύρεση Διπλότυπων τίτλων --
            is_valid = True
            seen_titles = set()
            
            for _, row in edited_rec.iterrows():
                title = du.clean_text(row.get("Τίτλος", ""))
                if not title:
                    continue
                
                title_key = du.normalize_material_name(title)
                if title_key in seen_titles:
                    st.error(f"❗ Η συνταγή με τίτλο '{title}' υπάρχει παραπάνω από μία φορά. Παρακαλώ διορθώστε το.")
                    is_valid = False
                seen_titles.add(title_key)

            # -- 2ος Έλεγχος: Ασφαλής Αποθήκευση (UPDATE / INSERT / DELETE) --
            if is_valid:
                with du.get_connection() as conn:
                    # Α. Εντοπισμός Διαγραμμένων Συνταγών
                    old_ids = set(rec_df["id"].dropna().tolist())
                    current_ids = set(edited_rec["id"].dropna().tolist())
                    
                    deleted_ids = old_ids - current_ids
                    for d_id in deleted_ids:
                        conn.execute("DELETE FROM recipes WHERE id = ?", (d_id,))
                    
                    # Β. Ενημέρωση (Update) ή Προσθήκη (Insert)
                    for _, row in edited_rec.iterrows():
                        title = du.clean_text(row.get("Τίτλος", ""))
                        if not title:
                            continue
                            
                        r_id = row.get("id")
                        annual_kg = du.clean_numeric(row.get("Ετήσια Κατανάλωση (kg)"))
                        return_pct = du.clean_numeric(row.get("Ποσοστό Επιστροφής (%)"))
                        erema_cat = du.clean_text(row.get("Erema Category", ""))
                        
                        if pd.notna(r_id) and r_id in old_ids:
                            # Υπάρχουσα συνταγή -> ΜΟΝΟ UPDATE για να μην χαθούν τα υλικά της (KY1, Y1 κλπ)
                            conn.execute(
                                """UPDATE recipes 
                                   SET title = ?, annual_consumption_kg = ?, total_return_pct = ?, erema_category = ? 
                                   WHERE id = ?""",
                                (title, annual_kg, return_pct, erema_cat, r_id)
                            )
                        else:
                            # Νέα συνταγή (προστέθηκε γραμμή) -> INSERT (με κενά υλικά αρχικά)
                            conn.execute(
                                """INSERT INTO recipes 
                                   (category, title, annual_consumption_kg, total_return_pct, erema_category) 
                                   VALUES (?, ?, ?, ?, ?)""",
                                (category, title, annual_kg, return_pct, erema_cat)
                            )
                
                st.success("✅ Οι αλλαγές στις συνταγές αποθηκεύτηκαν επιτυχώς!")
                import time
                time.sleep(1.5)
                st.rerun()
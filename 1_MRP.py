import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px

import data_utils as du

st.title("⚛️ MRP Material Requirement Programm")


ANNUAL_COL = "Κατανάλωση συνταγής / year"  # κλειδωμένο, πάντα το ίδιο πεδίο

categories = du.get_categories()
if not categories:
    st.error("Δεν βρέθηκαν δεδομένα στη βάση. Τρέξε πρώτα το migrate_excel_to_db.py.")
    st.stop()

if "PP" in categories:
    categories.remove("PP")
    categories.insert(0, "PP")

category = st.pills("Επιλέξτε κατηγορία υλικού:", categories, default=categories[0])

# --- ΒΗΜΑ 1: Υλοποίηση "What-If" Μνήμης ---
state_df_key = f"df_recipes_{category}"
if state_df_key not in st.session_state:
    st.session_state[state_df_key] = du.load_recipes(category)

df = st.session_state[state_df_key]
mat_df = du.load_materials(category)

if df.empty:
    st.warning(f"Δεν βρέθηκαν συνταγές για την κατηγορία {category}.")
    st.stop()

code_cols = [f"KY{i}" for i in range(1, 8)]
material_cols = [f"Y{i}" for i in range(1, 8)]
percent_cols = [f"PRC{i}" for i in range(1, 8)]

mats_from_list = mat_df["Material"].apply(du.clean_text).unique()
mats_from_recipes = (
    df[material_cols].stack().dropna().apply(du.clean_material_name).unique()
)
all_materials = sorted([m for m in set(mats_from_list) | set(mats_from_recipes) if du.clean_text(m).lower() not in ["", "none"]])
material_to_code = dict(zip(mat_df["Material"].apply(du.normalize_material_name), mat_df["Code"].astype(str).str.strip()))
for _, row in df.iterrows():
    for m, k in zip(material_cols, code_cols):
        mat_key = du.normalize_material_name(row.get(m, ""))
        code = du.clean_text(row.get(k, ""))
        if mat_key and code:
            material_to_code.setdefault(mat_key, code)

total_material_consumption = {}
for _, row in df.iterrows():
    aq = du.clean_numeric(row[ANNUAL_COL])
    for m, p in zip(material_cols, percent_cols):
        mat = du.clean_material_name(row.get(m, ""))
        if mat:
            total_material_consumption[mat] = total_material_consumption.get(mat, 0) + (aq * du.clean_numeric(row.get(p, 0)) / 100)

consumption_by_material = {du.normalize_material_name(m): c for m, c in total_material_consumption.items()}
code_to_consumption = {}
for _, row in mat_df.iterrows():
    code = du.clean_text(str(row.get("Code", "")))
    material = du.clean_text(str(row.get("Material", "")))
    if code and material:
        code_to_consumption[code] = consumption_by_material.get(du.normalize_material_name(material), 0)

all_categories_consumption = {}
all_categories_material_to_code = {}
# --- ΒΗΜΑ 2: Διάβασμα προσωρινής μνήμης για ALL categories (ώστε να λειτουργεί το What-If) ---
for cat in categories:
    try:
        cat_df = st.session_state.get(f"df_recipes_{cat}", du.load_recipes(cat))
        cat_mat_df = du.load_materials(cat)
        for _, row in cat_mat_df.iterrows():
            mat_key = du.normalize_material_name(du.clean_text(str(row.get("Material", ""))))
            code = du.clean_text(str(row.get("Code", "")))
            if mat_key and code:
                all_categories_material_to_code.setdefault(mat_key, code)
        for _, row in cat_df.iterrows():
            aq = du.clean_numeric(row[ANNUAL_COL])
            for m, p in zip(material_cols, percent_cols):
                mat = du.clean_material_name(row.get(m, ""))
                if mat:
                    all_categories_consumption[mat] = all_categories_consumption.get(mat, 0) + (aq * du.clean_numeric(row.get(p, 0)) / 100)
    except Exception:
        continue

all_categories_by_name = {du.normalize_material_name(m): c for m, c in all_categories_consumption.items()}
all_code_to_consumption = {code: all_categories_by_name.get(mat_norm, 0) for mat_norm, code in all_categories_material_to_code.items()}

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🛠️ Επεξεργασία Συνταγής", "📊 Αναλύσεις", "🕵🏻 Αναζήτηση/Αντικατάσταση Υλικού", "♻️ Εκτιμήσεις Αναγεννημένων Erema", "🧬 Μηχανικές Ιδιότητες"])

# =========================================================================
with tab1:
    st.subheader("Επεξεργασία Συνταγής")
    selected_recipe = st.selectbox("Επιλέξτε συνταγή:", sorted(df["Title"].dropna().unique()), placeholder="Πληκτρολογήστε για αναζήτηση...")

    recipe_row = df[df["Title"] == selected_recipe].iloc[0] if selected_recipe and not df[df["Title"] == selected_recipe].empty else None
    if recipe_row is None:
        st.stop()

    recipe_id = int(recipe_row["id"])
    recipe_annual_kg = du.clean_numeric(recipe_row.get(ANNUAL_COL, 0))
    recipe_return_pct = du.clean_numeric(recipe_row.get("Συνολικό ποσοστό επιστροφής %", 0))

    # Εμφάνιση Ετήσιας Κατανάλωσης ΚΑΙ Ποσοστού Επιστροφής σε 2 στήλες
    met_col1, met_col2 = st.columns(2)
    with met_col1:
        st.metric("📊 Ετήσια Κατανάλωση Επιλεγμένης Συνταγής", f"{recipe_annual_kg:,.0f} kg/year")
    with met_col2:
        st.metric("♻️ Συνολικό Ποσοστό Επιστροφής", f"{recipe_return_pct:.1f} %")
        
    # ── ΠΙΝΑΚΑΣ 1: Αρχική Συνταγή (από τη βάση δεδομένων, πάντα read-only) ──────────
    st.markdown("#### 📋 Αρχική Συνταγή (από τη βάση)")
    
    df_from_db = du.load_recipes(category)
    db_recipe_row = df_from_db[df_from_db["Title"] == selected_recipe].iloc[0] if not df_from_db[df_from_db["Title"] == selected_recipe].empty else None
    
    original_list = []
    if db_recipe_row is not None:
        for m, p, k in zip(material_cols, percent_cols, code_cols):
            mat_name = du.clean_material_name(db_recipe_row.get(m, ""))
            if mat_name and mat_name.lower() not in ['nan', 'none', '']:
                pct = du.clean_numeric(db_recipe_row.get(p, 0))
                original_list.append({
                    "Κωδικός": str(db_recipe_row.get(k, "")),
                    "Υλικό": mat_name,
                    "Ποσοστό (%)": pct,
                    "Κιλά (kg)": recipe_annual_kg * pct / 100
                })
    original_df = du.with_one_based_index(pd.DataFrame(original_list))
    original_total = original_df["Ποσοστό (%)"].sum() if not original_df.empty else 0

    if abs(original_total - 100) > 0.01:
        st.error(f"❗ Άθροισμα (Αρχικής): {original_total:.1f}%")
    else:
        st.success(f"✅ Άθροισμα (Αρχικής): {original_total:.1f}%")

    st.dataframe(
        original_df.style.format({"Ποσοστό (%)": "{:,.1f}", "Κιλά (kg)": "{:,.0f}"}),
        width='stretch'
    )

    st.divider()

# ── ΠΙΝΑΚΑΣ 2: Επεξεργασία Συνταγής ──────────
    st.markdown("#### ✏️ Επεξεργασία Συνταγής")

    # Χτίζουμε το τρέχον state από τη μνήμη (που ίσως έχει ήδη τροποποιηθεί)
    current_list = []
    for m, p, k in zip(material_cols, percent_cols, code_cols):
        mat_name = du.clean_material_name(recipe_row.get(m, ""))
        if mat_name and mat_name.lower() not in ['nan', 'none', '']:
            pct = du.clean_numeric(recipe_row.get(p, 0))
            current_list.append({
                "Κωδικός": str(recipe_row.get(k, "")),
                "Υλικό": mat_name,
                "Ποσοστό (%)": pct,
                "Κιλά (kg)": recipe_annual_kg * pct / 100
            })
    
    current_df = du.with_one_based_index(pd.DataFrame(current_list))

    draft_key = f"draft_{category}_{recipe_id}"
    editable_cols = ["Κωδικός", "Υλικό", "Ποσοστό (%)", "Κιλά (kg)"]
    
    if current_df.empty:
        empty_df = pd.DataFrame({
            "Κωδικός": pd.Series(dtype='str'),
            "Υλικό": pd.Series(dtype='str'),
            "Ποσοστό (%)": pd.Series(dtype='float'),
            "Κιλά (kg)": pd.Series(dtype='float')
        })
        editor_df = st.session_state.get(draft_key, empty_df)
    else:
        editor_df = st.session_state.get(draft_key, current_df[editable_cols].copy())

    # Καθαρισμός του index για να μην μπερδεύεται το Streamlit
    editor_df = editor_df.reset_index(drop=True)
    editor_widget_key = f"editor_{category}_{recipe_id}"

    edited_materials = st.data_editor(
        editor_df, num_rows="dynamic", width='stretch',
        disabled=["Κωδικός", "Κιλά (kg)"],
        column_config={
            "Κωδικός": st.column_config.TextColumn("Κωδικός", disabled=True),
            "Υλικό": st.column_config.SelectboxColumn("Υλικό", options=all_materials, required=True),
            "Ποσοστό (%)": st.column_config.NumberColumn("Ποσοστό (%)", format="%,.1f", min_value=0.0, max_value=100.0),
            "Κιλά (kg)": st.column_config.NumberColumn("Κιλά (kg)", format="%,.0f", disabled=True)
        },
        key=editor_widget_key
    )

    # ── Κουμπιά Ενεργειών ──
    st.caption("💡 **Tip:** Χρησιμοποιήστε την Προσωρινή Αποθήκευση για να δείτε τις αλλαγές στα άλλα Tabs πριν αποθηκεύσετε οριστικά!")
    
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    
    with btn_col1:
        temp_save_clicked = st.button(
            "💾 Προσωρινή Αποθήκευση", 
            use_container_width=True,
            help="Υπολογίζει αυτόματα Κωδικούς & Κιλά και ενημερώνει τα υπόλοιπα Tabs."
        )

    with btn_col2:
        reset_clicked = st.button(
            "🔄 Ακύρωση / Επαναφορά", 
            use_container_width=True,
            help="Αναιρεί όλες τις προσωρινές δοκιμές σας και επαναφέρει την αρχική συνταγή από τη βάση."
        )
        
    with btn_col3:
        # Η μαγική λέξη type="primary" δίνει το κύριο χρώμα (π.χ. κόκκινο)
        replace_clicked = st.button(
            "✅ Αποθήκευση στο DataBase", 
            type="primary", 
            use_container_width=True,
            help="Μόνιμη αποθήκευση των αλλαγών στη βάση δεδομένων."
        )

    def _validate(df_to_check):
        duplicated_materials = df_to_check[df_to_check.duplicated(subset=["Υλικό"], keep=False)]
        if not duplicated_materials.empty:
            for mat in duplicated_materials["Υλικό"].unique():
                st.error(f"❗ Το υλικό '{mat}' έχει εισαχθεί πάνω από μία φορά στη συνταγή. Παρακαλώ διορθώστε το!")
            return False
        new_total = df_to_check["Ποσοστό (%)"].apply(du.clean_numeric).sum()
        if abs(new_total - 100) > 0.01:
            st.error(f"❗ Δεν μπορεί να αποθηκευτεί. Το άθροισμα είναι {new_total:.1f}% και όχι 100.0%")
            return False
        return True

    # ==========================================
    # 1. ΛΟΓΙΚΗ ΠΡΟΣΩΡΙΝΗΣ ΑΠΟΘΗΚΕΥΣΗΣ
    # ==========================================
    if temp_save_clicked:
        # Υπολογισμός Κωδικών και Κιλών στον πίνακα
        for idx in edited_materials.index:
            mat_raw = edited_materials.at[idx, "Υλικό"]
            mat_name = du.clean_text(mat_raw) if pd.notna(mat_raw) else ""
            if not mat_name:
                continue
            
            expected_code = str(material_to_code.get(du.normalize_material_name(mat_name), ""))
            pct_raw = edited_materials.at[idx, "Ποσοστό (%)"]
            pct = du.clean_numeric(pct_raw) if pd.notna(pct_raw) else 0.0
            expected_kg = recipe_annual_kg * pct / 100
            
            edited_materials.at[idx, "Κωδικός"] = expected_code
            edited_materials.at[idx, "Κιλά (kg)"] = expected_kg
            
        # Αποθήκευση του πίνακα στο προσχέδιο για να φαίνονται οι αριθμοί στο Tab 1
        st.session_state[draft_key] = edited_materials
        if editor_widget_key in st.session_state:
            del st.session_state[editor_widget_key]

        # Ενημέρωση της κεντρικής μνήμης (state_df_key) ώστε να δουν την αλλαγή τα TABS 2, 3, 4, 5
        valid_materials = edited_materials[edited_materials["Υλικό"].astype(str).str.strip() != ""]
        temp_main_df = st.session_state[state_df_key].copy()
        
        row_idx = temp_main_df.index[temp_main_df["id"] == recipe_id].tolist()
        if row_idx:
            r_idx = row_idx[0]
            # Καθαρισμός παλιών υλικών (από 1 έως 7)
            for i in range(1, 8):
                temp_main_df.at[r_idx, f"Y{i}"] = ""
                temp_main_df.at[r_idx, f"PRC{i}"] = 0.0
                temp_main_df.at[r_idx, f"KY{i}"] = ""
            
            # Πέρασμα των νέων υλικών
            slot = 1
            for _, r in valid_materials.iterrows():
                if slot > 7: break
                temp_main_df.at[r_idx, f"Y{slot}"] = r["Υλικό"]
                temp_main_df.at[r_idx, f"PRC{slot}"] = r["Ποσοστό (%)"]
                temp_main_df.at[r_idx, f"KY{slot}"] = r["Κωδικός"]
                slot += 1
                
        st.session_state[state_df_key] = temp_main_df
        
        st.toast("Έγινε προσωρινή αποθήκευση! Υπολογίστηκαν Κιλά & Κωδικοί.", icon="💾")
        import time
        time.sleep(1.5)
        st.rerun()

    # ==========================================
    # 2. ΛΟΓΙΚΗ ΑΚΥΡΩΣΗΣ / ΕΠΑΝΑΦΟΡΑΣ
    # ==========================================
    if reset_clicked:
        # Διαγραφή όλων των προσωρινών καταχωρήσεων από τη μνήμη
        st.session_state.pop(draft_key, None)
        st.session_state.pop(state_df_key, None)
        st.session_state.pop(editor_widget_key, None)
        
        st.toast("🔄 Έγινε πλήρης επαναφορά της συνταγής από τη βάση δεδομένων.")
        import time
        time.sleep(1)
        st.rerun()

    # ==========================================
    # 3. ΛΟΓΙΚΗ ΑΠΟΘΗΚΕΥΣΗΣ ΣΤΗ ΒΑΣΗ (DB)
    # ==========================================
    if replace_clicked:
        # 1. Για ασφάλεια, ξανακάνουμε τους υπολογισμούς (σε περίπτωση που ξέχασε να πατήσει το "Προσωρινή Αποθήκευση")
        for idx in edited_materials.index:
            mat_raw = edited_materials.at[idx, "Υλικό"]
            mat_name = du.clean_text(mat_raw) if pd.notna(mat_raw) else ""
            if not mat_name: continue
            
            expected_code = str(material_to_code.get(du.normalize_material_name(mat_name), ""))
            pct_raw = edited_materials.at[idx, "Ποσοστό (%)"]
            pct = du.clean_numeric(pct_raw) if pd.notna(pct_raw) else 0.0
            
            edited_materials.at[idx, "Κωδικός"] = expected_code
            edited_materials.at[idx, "Κιλά (kg)"] = recipe_annual_kg * pct / 100

        # 2. Έλεγχος λαθών και αποθήκευση
        if _validate(edited_materials):
            du.save_recipe(recipe_id, edited_materials)
            # Καθαρισμός μνήμης για να φορτώσει η φρέσκια συνταγή από τη βάση
            st.session_state.pop(draft_key, None)
            st.session_state.pop(state_df_key, None)
            st.session_state.pop(editor_widget_key, None)
            
            st.toast("Επιτυχής οριστική αποθήκευση στο Database!", icon="✅")
            import time
            time.sleep(1.5)
            st.rerun()

# =========================================================================
with tab2:
    valid_recipe_mask = df["Title"].apply(lambda x: du.clean_text(x).lower() not in ["", "none"])
    n_recipes = valid_recipe_mask.sum()
    n_materials = sum(1 for v in total_material_consumption.values() if v > 0)
    total_consumption_kg = sum(total_material_consumption.values())

    c1, c2, c3 = st.columns(3)
    c1.metric("📋 Συνταγές", f"{n_recipes}")
    c2.metric("🧪 Ενεργά Υλικά", f"{n_materials}")
    c3.metric("⚖️ Συνολική Ετήσια Κατανάλωση", f"{total_consumption_kg:,.0f} kg/year")
    st.divider()

    # --- 1. Αναλύσεις Συνταγών ---
    st.subheader("1. Ετήσια Κατανάλωση & Ποσοστά Επιστροφής")
    recipe_results = df.loc[valid_recipe_mask, ["Title", ANNUAL_COL]].copy()
    recipe_results.columns = ["Συνταγή", "Ετήσια Κατανάλωση (kg/year)"]
    recipe_results["Ετήσια Κατανάλωση (kg/year)"] = recipe_results["Ετήσια Κατανάλωση (kg/year)"].apply(du.clean_numeric)
    recipe_results["Ποσοστό Επιστροφής (%)"] = df.loc[valid_recipe_mask, "Συνολικό ποσοστό επιστροφής %"].apply(du.clean_numeric)
    recipe_results["Κατηγορία EREMA"] = df.loc[valid_recipe_mask, "Erema Category"].apply(du.clean_text)
    
    # Ταξινόμηση του πίνακα για να εμφανίζονται πρώτες οι συνταγές με τη μεγαλύτερη κατανάλωση
    recipe_results = recipe_results.sort_values("Ετήσια Κατανάλωση (kg/year)", ascending=False)
    recipe_results = du.with_one_based_index(recipe_results)

    st.dataframe(
        recipe_results.style.format({"Ετήσια Κατανάλωση (kg/year)": "{:,.0f}", "Ποσοστό Επιστροφής (%)": "{:.1f} %"}),
        width='stretch'
    )

    # ΝΕΟ ΓΡΑΦΗΜΑ: Top 10 Συνταγές
    st.subheader("📈 Top 10 Συνταγές ανά Κατανάλωση")
    recipe_chart_df = recipe_results[recipe_results["Ετήσια Κατανάλωση (kg/year)"] > 0].head(10).reset_index(drop=True)
    if not recipe_chart_df.empty:
        fig1 = px.bar(
            recipe_chart_df, 
            y="Συνταγή", 
            x="Ετήσια Κατανάλωση (kg/year)", 
            orientation='h',  # Οριζόντιες μπάρες
            color="Ετήσια Κατανάλωση (kg/year)",  # Διαβάθμιση χρώματος
            color_continuous_scale="Oranges",     # Μοντέρνα πορτοκαλί παλέτα
            text_auto=".2s",  # Κομψή μορφοποίηση (π.χ. 1.2M, 50k)
            height=400
        )
        # Εμφάνιση κειμένου έξω από την μπάρα και καθαρό tooltip
        fig1.update_traces(textposition="outside", hovertemplate="<b>%{y}</b><br>%{x:,.0f} kg/year<extra></extra>")
        fig1.update_layout(
            yaxis={'categoryorder':'total ascending'}, # Η μεγαλύτερη μπάρα πάνω-πάνω
            xaxis_title="", yaxis_title="",
            coloraxis_showscale=False, # Κρύβουμε την πλαϊνή μπάρα χρωμάτων για καθαρότητα
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(showgrid=False, showticklabels=False) # Κρύβουμε εντελώς τον άξονα Χ
        )
        st.plotly_chart(fig1, width='stretch')

    st.divider()

    # --- 2. Αναλύσεις Υλικών ---
    st.subheader("2. Συνολική Κατανάλωση ανά Υλικό")
    material_df = mat_df[["Code", "Material"]].copy()
    material_df.columns = ["Κωδικός", "Υλικό"]
    material_df["Κωδικός"] = material_df["Κωδικός"].apply(du.clean_text)
    material_df["Υλικό"] = material_df["Υλικό"].apply(du.clean_text)
    material_df = material_df[material_df["Υλικό"].apply(lambda x: du.clean_text(x).lower() not in ["", "none"])]
    material_df["Συνολική Κατανάλωση (kg/year)"] = material_df["Υλικό"].map(
        lambda x: consumption_by_material.get(du.normalize_material_name(x), 0)
    )

    existing_material_keys = set(material_df["Υλικό"].map(du.normalize_material_name))
    missing_recipe_materials = [m for m in total_material_consumption if du.normalize_material_name(m) not in existing_material_keys]
    if missing_recipe_materials:
        missing_material_df = pd.DataFrame({
            "Κωδικός": [material_to_code.get(du.normalize_material_name(m), "") for m in missing_recipe_materials],
            "Υλικό": missing_recipe_materials,
            "Συνολική Κατανάλωση (kg/year)": [total_material_consumption[m] for m in missing_recipe_materials]
        })
        material_df = pd.concat([material_df, missing_material_df], ignore_index=True)

    material_df = du.with_one_based_index(material_df.sort_values("Συνολική Κατανάλωση (kg/year)", ascending=False))
    st.dataframe(material_df.style.format({"Συνολική Κατανάλωση (kg/year)": "{:,.0f}"}), width='stretch')

    st.subheader("📊 Top 10 Υλικά ανά Κατανάλωση")
    chart_df = material_df[material_df["Συνολική Κατανάλωση (kg/year)"] > 0].head(10).reset_index(drop=True)
    if not chart_df.empty:
        fig2 = px.bar(
            chart_df, 
            y="Υλικό", 
            x="Συνολική Κατανάλωση (kg/year)", 
            orientation='h', 
            color="Συνολική Κατανάλωση (kg/year)", 
            color_continuous_scale="Blues", # Μοντέρνα μπλε παλέτα
            text_auto=".2s", 
            height=400
        )
        fig2.update_traces(textposition="outside", hovertemplate="<b>%{y}</b><br>%{x:,.0f} kg/year<extra></extra>")
        fig2.update_layout(
            yaxis={'categoryorder':'total ascending'},
            xaxis_title="", yaxis_title="",
            coloraxis_showscale=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(showgrid=False, showticklabels=False)
        )
        st.plotly_chart(fig2, width='stretch')

# =========================================================================
with tab3:
    st.subheader("🔍 Αναζήτηση Υλικού σε Συνταγές")

    def clean_code_format(val):
        s = str(val).strip()
        if s.endswith('.0'):
            s = s[:-2]
        return s

    codes_from_list = mat_df["Code"].dropna().apply(clean_code_format).unique() if "Code" in mat_df.columns else []
    codes_from_recipes = df[code_cols].stack().dropna().apply(clean_code_format).unique()
    all_codes = sorted([c for c in set(codes_from_list) | set(codes_from_recipes) if c.lower() not in ["", "none", "nan"]])

    current_desc = st.session_state.get("search_by_description", [])
    current_code = st.session_state.get("search_by_code", [])
    disable_desc = len(current_code) > 0
    disable_code = len(current_desc) > 0

    col1, col2 = st.columns(2)
    with col1:
        selected_material_list = st.multiselect("🔍 Αναζήτηση με Περιγραφή Υλικού:", options=all_materials,
                                                  placeholder="Επιλέξτε ή πληκτρολογήστε περιγραφή...", max_selections=1,
                                                  key="search_by_description", disabled=disable_desc)
        selected_material = selected_material_list[0] if selected_material_list else None
    with col2:
        selected_code_list = st.multiselect("🔢 Αναζήτηση με Κωδικό Υλικού:", options=all_codes,
                                             placeholder="Επιλέξτε ή πληκτρολογήστε κωδικό...", max_selections=1,
                                             key="search_by_code", disabled=disable_code)
        selected_code = selected_code_list[0] if selected_code_list else None

    desc_query = selected_material.lower().strip() if selected_material else ""
    code_query = selected_code.lower().strip() if selected_code else ""

    if desc_query or code_query:
        found_recipes = []
        for _, row in df.iterrows():
            match_desc = match_code = False
            for m, k in zip(material_cols, code_cols):
                mat_val = str(row.get(m, "")).lower().strip()
                code_val = clean_code_format(row.get(k, "")).lower()
                if desc_query and desc_query in mat_val:
                    match_desc = True
                if code_query and code_query == code_val:
                    match_code = True
            if desc_query and match_desc:
                found_recipes.append(row)
            elif code_query and match_code:
                found_recipes.append(row)

        if found_recipes:
            st.success(f"Βρέθηκαν {len(found_recipes)} συνταγές:")
            for r in found_recipes:
                recipe_total = sum(du.clean_numeric(r.get(p, 0)) for p in percent_cols)
                warning_icon = " ❗" if abs(recipe_total - 100) > 0.01 else ""
                
                recipe_annual_kg = du.clean_numeric(r.get(ANNUAL_COL, 0))
                expander_title = f"Συνταγή: {r['Title']} | ⚖️ Ετήσια Κατανάλωση: {recipe_annual_kg:,.0f} kg/year (Άθροισμα: {recipe_total:.1f}%){warning_icon}"
                
                with st.expander(expander_title):
                    recipe_materials = []
                    for m, p, k in zip(material_cols, percent_cols, code_cols):
                        mat_name = str(r.get(m, "")).strip()
                        mat_code = clean_code_format(r.get(k, ""))
                        if mat_name and mat_name.lower() not in ["nan", "none", ""]:
                            pct = float(du.clean_numeric(r.get(p, 0)))
                            mat_kg = recipe_annual_kg * (pct / 100)
                            
                            recipe_materials.append({
                                "Κωδικός": mat_code if mat_code.lower() not in ["nan", "none"] else "",
                                "Υλικό": mat_name,
                                "Ποσοστό (%)": pct,
                                "Κιλά (kg)": mat_kg
                            })
                    
                    if recipe_materials:
                        df_recipe = du.with_one_based_index(pd.DataFrame(recipe_materials))
                        st.dataframe(
                            df_recipe.style.format({"Ποσοστό (%)": "{:.1f}", "Κιλά (kg)": "{:,.0f}"}),
                            width='stretch'
                        )
                    else:
                        st.write("Δεν βρέθηκαν υλικά στη συνταγή.")
            
            # --- ΝΕΟ: ΕΝΟΤΗΤΑ ΜΑΖΙΚΗΣ ΑΝΤΙΚΑΤΑΣΤΑΣΗΣ ---
            st.divider()
            st.markdown("#### 🔄 Μαζική Αντικατάσταση Υλικού")
            st.info("Επιλέξτε το νέο υλικό (με **Περιγραφή Ή Κωδικό**). Το υλικό που αναζητήσατε θα αντικατασταθεί με το νέο σε όλες τις παραπάνω συνταγές.")
            
            # Διαχείριση Disable για τα πεδία αντικατάστασης
            current_rep_desc = st.session_state.get("replace_new_desc", [])
            current_rep_code = st.session_state.get("replace_new_code", [])
            dis_rep_desc = len(current_rep_code) > 0
            dis_rep_code = len(current_rep_desc) > 0

            col_rep_desc, col_rep_code, col_rep_btn = st.columns([2, 2, 1.5])
            
            with col_rep_desc:
                selected_rep_mat_list = st.multiselect("Νέα Περιγραφή:", options=all_materials, max_selections=1, key="replace_new_desc", disabled=dis_rep_desc)
                rep_mat = selected_rep_mat_list[0] if selected_rep_mat_list else None
            
            with col_rep_code:
                selected_rep_code_list = st.multiselect("Νέος Κωδικός:", options=all_codes, max_selections=1, key="replace_new_code", disabled=dis_rep_code)
                rep_code = selected_rep_code_list[0] if selected_rep_code_list else None
                
            with col_rep_btn:
                st.write("") 
                st.write("")
                replace_btn = st.button("Αντικατάσταση & Αποθήκευση", type="primary", use_container_width=True)
                
            if replace_btn:
                if not rep_mat and not rep_code:
                    st.error("❗ Επιλέξτε το νέο υλικό (Περιγραφή ή Κωδικό) για να γίνει η αντικατάσταση.")
                else:
                    # 1. Βρίσκουμε τον σωστό κωδικό ΚΑΙ περιγραφή, ανάλογα με το τι επέλεξε ο χρήστης
                    if rep_mat:
                        new_material_to_set = rep_mat
                        new_code_to_set = str(material_to_code.get(du.normalize_material_name(rep_mat), ""))
                    else:
                        new_code_to_set = rep_code
                        # Ανάκτηση της σωστής περιγραφής από τον κωδικό
                        code_to_display_name = {}
                        for _, row_m in mat_df.iterrows():
                            c_val = clean_code_format(row_m.get("Code", ""))
                            m_val = du.clean_text(row_m.get("Material", ""))
                            if c_val and m_val: code_to_display_name[c_val] = m_val
                        for _, row_r in df.iterrows():
                            for mc, kc in zip(material_cols, code_cols):
                                m_val = du.clean_text(row_r.get(mc, ""))
                                c_val = clean_code_format(row_r.get(kc, ""))
                                if c_val and m_val and c_val not in code_to_display_name:
                                    code_to_display_name[c_val] = m_val
                        
                        new_material_to_set = code_to_display_name.get(rep_code, "")
                    
                    # 2. Ενημερώνουμε ΑΠΕΥΘΕΙΑΣ τη Βάση Δεδομένων
                    with du.get_connection() as conn:
                        for r in found_recipes:
                            recipe_id = int(r["id"])
                            # Ψάχνουμε στα 7 slots της συνταγής να βρούμε ΠΟΥ βρισκόταν το παλιό υλικό
                            for i in range(1, 8):
                                m_col = f"Y{i}"
                                k_col = f"KY{i}"
                                
                                mat_val = str(r.get(m_col, "")).lower().strip()
                                code_val = clean_code_format(r.get(k_col, "")).lower()
                                
                                should_replace = False
                                if desc_query and desc_query in mat_val:
                                    should_replace = True
                                if code_query and code_query == code_val:
                                    should_replace = True
                                    
                                if should_replace:
                                    # Αντικαθιστούμε το υλικό στο συγκεκριμένο slot
                                    conn.execute(
                                        "UPDATE recipe_materials SET material_name = ?, material_code = ? WHERE recipe_id = ? AND slot = ?",
                                        (new_material_to_set, new_code_to_set, recipe_id, i)
                                    )
                    
                    # 3. Καθαρίζουμε τις προσωρινές μνήμες 
                    st.session_state.pop(state_df_key, None)
                    st.session_state.pop("replace_new_desc", None)
                    st.session_state.pop("replace_new_code", None)
                    
                    st.success(f"✅ Η αντικατάσταση με το '{new_material_to_set}' (Κωδικός: {new_code_to_set}) ολοκληρώθηκε επιτυχώς!")
                    import time
                    time.sleep(1.5)
                    st.rerun()

        else:
            st.warning("Δεν βρέθηκε συνταγή με αυτά τα κριτήρια.")

# =========================================================================
with tab4:
    st.subheader("Εκτιμήσεις Αναγεννημένων Erema")
    erema_mat_df = du.load_erema_materials()

    if erema_mat_df is None:
        st.warning("Δεν βρέθηκαν Erema Materials στη βάση.")
    else:
        cols = erema_mat_df.columns.tolist()
        code_col, desc_col = cols[0], cols[1] if len(cols) > 1 else cols[0]

        import re as _re

        def normalize_erema_name(text):
            t = str(text).upper().strip()
            t = _re.sub(r'^\s*\(\d+\)\s*', '', t)
            for word in ["ΑΝΑΓΕΝΝΗΜΕΝΟ", "ΑΝΑΓΕΝΝΗΜΕΝΑ", "ΑΝΑΓΕΝ.", "ΑΝΑΓΕΝ", "ΑΝΑΓ.", "ΑΝΑΓ"]:
                t = t.replace(word, "")
            t = t.replace(".", "")
            return _re.sub(r'\s+', '', t).strip().casefold()

        erema_returns_dict = {}
        for cat in categories:
            try:
                # Χρησιμοποιούμε τη μνήμη για να ενημερώνεται δυναμικά (What-If)
                cat_df = st.session_state.get(f"df_recipes_{cat}", du.load_recipes(cat))
                if "Erema Category" in cat_df.columns and "Συνολικό ποσοστό επιστροφής %" in cat_df.columns and ANNUAL_COL in cat_df.columns:
                    for _, row in cat_df.iterrows():
                        erema_cat_val = row.get("Erema Category", "")
                        if pd.isna(erema_cat_val) or str(erema_cat_val).strip() == "" or str(erema_cat_val).lower() == "none":
                            continue
                        norm_cat = normalize_erema_name(erema_cat_val)
                        annual_kg = du.clean_numeric(row.get(ANNUAL_COL, 0))
                        return_pct = du.clean_numeric(row.get("Συνολικό ποσοστό επιστροφής %", 0)) / 100
                        erema_returns_dict[norm_cat] = erema_returns_dict.get(norm_cat, 0.0) + (annual_kg * return_pct)
            except Exception:
                continue

        tab4_data = []
        for _, row in erema_mat_df.iterrows():
            code = du.clean_text(str(row.get(code_col, "")))
            desc = du.clean_text(str(row.get(desc_col, "")))
            norm_desc = normalize_erema_name(desc)
            calculated_return = erema_returns_dict.get(norm_desc, 0.0)
            if code or desc:
                tab4_data.append({
                    "Κωδικός": code,
                    "Περιγραφή": desc,
                    "Εκτίμηση Ετήσιας Επιστροφής (kg/year)": calculated_return,
                    "Εκτίμηση Ετήσιας Κατανάλωσης(kg/year)": all_code_to_consumption.get(code, 0)
                })

        if tab4_data:
            tab4_df = du.with_one_based_index(pd.DataFrame(tab4_data))
            total_return_4 = tab4_df["Εκτίμηση Ετήσιας Επιστροφής (kg/year)"].sum()
            total_consumption_4 = tab4_df["Εκτίμηση Ετήσιας Κατανάλωσης(kg/year)"].sum()
            c1, c2 = st.columns(2)
            c1.metric("♻️ Συνολική Εκτιμώμενη Επιστροφή", f"{total_return_4:,.0f} kg/year")
            c2.metric("📦 Συνολική Εκτιμώμενη Κατανάλωση", f"{total_consumption_4:,.0f} kg/year")
            st.divider()
            st.dataframe(
                tab4_df.style.format({"Εκτίμηση Ετήσιας Επιστροφής (kg/year)": "{:,.0f}", "Εκτίμηση Ετήσιας Κατανάλωσης(kg/year)": "{:,.0f}"}),
                width='stretch'
            )
            st.subheader("📊 Εκτίμηση Επιστροφής ανά Erema Υλικό")
            chart4_df = tab4_df[tab4_df["Εκτίμηση Ετήσιας Επιστροφής (kg/year)"] > 0].reset_index(drop=True)
            if not chart4_df.empty:
                fig4 = px.bar(
                    chart4_df, 
                    y="Περιγραφή", 
                    x="Εκτίμηση Ετήσιας Επιστροφής (kg/year)", 
                    orientation='h', 
                    color="Εκτίμηση Ετήσιας Επιστροφής (kg/year)", 
                    color_continuous_scale="Tealgrn", # Μοντέρνα παλέτα στο χρώμα της μέντας/τιρκουάζ
                    text_auto=".2s", 
                    height=380
                )
                fig4.update_traces(textposition="outside", hovertemplate="<b>%{y}</b><br>%{x:,.0f} kg/year<extra></extra>")
                fig4.update_layout(
                    yaxis={'categoryorder':'total ascending'},
                    xaxis_title="", yaxis_title="",
                    coloraxis_showscale=False,
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0, r=0, t=20, b=0),
                    xaxis=dict(showgrid=False, showticklabels=False)
                )
                st.plotly_chart(fig4, width='stretch')

# =========================================================================
with tab5:
    st.subheader(f"🧬 Δυναμικός Υπολογισμός Μηχανικών Ιδιοτήτων: {category}")
    st.info(
        "🔬 **Επιστημονική Σημείωση Μοντελοποίησης:**\n"
        "- Το **MFI** υπολογίζεται με **Λογαριθμικό Κανόνα Ανάμειξης**.\n"
        "- Η αντοχή σε κρούση υπολογίζεται γραμμικά (θεωρητική εκτίμηση)."
    )
    # ΝΕΟ: Ειδική ενημέρωση ΜΟΝΟ για την κατηγορία POM
    if category == "POM":
        st.info(
            "📌 **Ειδική Σημείωση για POM:**\n"
            "- Το **Impact** (Αντοχή σε κρούση) μετράται με τη μέθοδο **Charpy Notched Impact Strength (23°C) ISO 179/1eA**.\n"
            "- Το **HDT** μετράται στα **1.8 MPa** (αντί για 0.45 MPa)."
        )
        
    base_mech_df = du.load_mech_properties(category)

    if base_mech_df is None:
        st.warning(f"Δεν βρέθηκαν μηχανικές ιδιότητες για την κατηγορία {category}.")
    else:
        def find_mech_col(keywords):
            for col in base_mech_df.columns:
                if any(k.lower() in col.lower() for k in keywords):
                    return col
            return None

        mech_code_col = find_mech_col(["κωδικ", "code", "ky"]) or base_mech_df.columns[0]
        mech_desc_col = find_mech_col(["περιγραφ", "desc", "material", "title"]) or base_mech_df.columns[1]

        mech_materials_options = sorted([
            du.clean_material_name(m) for m in base_mech_df[mech_desc_col].dropna().unique()
            if du.clean_text(m).lower() not in ["", "none", "nan"]
        ])

        mech_by_code, mech_by_desc, mech_material_to_code_local = {}, {}, {}
        for _, row in base_mech_df.iterrows():
            c_key = du.clean_text(row.get(mech_code_col, ""))
            m_raw = row.get(mech_desc_col, "")
            d_key = du.normalize_material_name(du.clean_text(m_raw))
            m_clean = du.clean_material_name(m_raw)
            if c_key:
                mech_by_code[c_key] = row
            if d_key:
                mech_by_desc[d_key] = row
                if m_clean:
                    mech_material_to_code_local[d_key] = c_key

        st.markdown("### 📊 Χειροκίνητη Σύνθεση Υλικών & Ποσοστών")
        st.info("💡 Πατήστε **'+ Add row'** για να εισάγετε υλικά και ποσοστά.")

        col_table_a, col_table_b = st.columns(2)
        default_structure = pd.DataFrame(columns=["Υλικό", "Ποσοστό (%)"])

        with col_table_a:
            with st.container(border=True): # <--- Η κάρτα για τον Πίνακα Α
                st.markdown("**📋 Σύνθεση Πίνακα Α**")
                edited_a = st.data_editor(default_structure, key=f"tab5_manual_editor_a_{category}", num_rows="dynamic", width='stretch',
                    column_config={
                        "Υλικό": st.column_config.SelectboxColumn("Υλικό", options=mech_materials_options, required=True),
                        "Ποσοστό (%)": st.column_config.NumberColumn("Ποσοστό (%)", format="%,.1f", min_value=0.0, max_value=100.0)
                    })
                    
        with col_table_b:
            with st.container(border=True): # <--- Η κάρτα για τον Πίνακα Β
                st.markdown("**📋 Σύνθεση Πίνακα Β**")
                edited_b = st.data_editor(default_structure, key=f"tab5_manual_editor_b_{category}", num_rows="dynamic", width='stretch',
                    column_config={
                        "Υλικό": st.column_config.SelectboxColumn("Υλικό", options=mech_materials_options, required=True),
                        "Ποσοστό (%)": st.column_config.NumberColumn("Ποσοστό (%)", format="%,.1f", min_value=0.0, max_value=100.0)
                    })

        mech_cols_map = {
            "density": (find_mech_col(["density", "πυκν"]), "Density", "g/cm^3", 3),
            "tensile_modulus": (find_mech_col(["tensile modulus", "μέτρο ελαστικότητας"]), "Tensile Modulus", "MPa", 0),
            "flexural_mod": (find_mech_col(["flexural mod", "κάμψ"]), "Flexural Modulus", "MPa", 0),
            "yield_strength": (find_mech_col(["yield strength", "διαρρο"]), "Tensile Yield Strength", "MPa", 1),
            "break_strength": (find_mech_col(["break strength", "θραύσ"]), "Tensile Break Strength", "MPa", 1),
            "impact": (find_mech_col(["impact", "κρούση"]), "Impact", "kJ/m^2", 1),
            "mfi": (find_mech_col(["mfi"]), "MFI", "g/10min", 2),
        }

        def calculate_recipe_properties(edited_df):
            import math
            calculated_values = {}
            has_active_rows = not edited_df.empty and edited_df["Υλικό"].dropna().apply(du.clean_text).str.len().sum() > 0
            if not has_active_rows:
                for prop_id in mech_cols_map.keys():
                    calculated_values[prop_id] = "-"
                return calculated_values

            for prop_id, (excel_col, _, _, _) in mech_cols_map.items():
                if not excel_col:
                    calculated_values[prop_id] = "Not Enough Data"
                    continue
                weighted_sum, has_missing_data, active_elements_count = 0.0, False, 0
                for _, row in edited_df.iterrows():
                    m_name = du.clean_text(row.get("Υλικό", ""))
                    pct = du.clean_numeric(row.get("Ποσοστό (%)", 0))
                    if pct <= 0 or not m_name:
                        continue
                    mat_properties = mech_by_desc.get(du.normalize_material_name(m_name))
                    if mat_properties is None:
                        m_code = mech_material_to_code_local.get(du.normalize_material_name(m_name), "")
                        if m_code:
                            mat_properties = mech_by_code.get(du.clean_text(m_code))
                    if mat_properties is not None:
                        raw_val = mat_properties.get(excel_col)
                        if pd.isna(raw_val) or str(raw_val).strip() == "" or du.clean_text(raw_val).lower() in ["n/a", "none", "nan", "-", "not enough data"]:
                            has_missing_data = True
                            break
                        else:
                            val_num = du.clean_numeric(raw_val)
                            active_elements_count += 1
                            if prop_id == "mfi":
                                if val_num > 0:
                                    weighted_sum += math.log10(val_num) * (pct / 100.0)
                                else:
                                    has_missing_data = True
                                    break
                            else:
                                weighted_sum += val_num * (pct / 100.0)
                    else:
                        has_missing_data = True
                        break
                if has_missing_data:
                    calculated_values[prop_id] = "Not Enough Data"
                else:
                    if prop_id == "mfi":
                        calculated_values[prop_id] = "-" if active_elements_count == 0 else 10 ** weighted_sum
                    else:
                        calculated_values[prop_id] = weighted_sum
            return calculated_values

        props_a = calculate_recipe_properties(edited_a)
        props_b = calculate_recipe_properties(edited_b)

########################-------------------------#############################
        st.markdown("### 📝 Reports Υπολογισμένων Ιδιοτήτων")
        col_rep_a, col_rep_b = st.columns(2)

        report_lines_a = ["Calculated Properties (Πίνακας Α)\n"]
        for prop_id, (_, display_label, unit, decimals) in mech_cols_map.items():
            val = props_a[prop_id]
            report_lines_a.append(f"{display_label:<26} {val}" if isinstance(val, str) else f"{display_label:<26} {val:.{decimals}f} {unit}")
        with col_rep_a:
            st.code("\n".join(report_lines_a), language=None)

        report_lines_b = ["Calculated Properties (Πίνακας Β)\n"]
        for prop_id, (_, display_label, unit, decimals) in mech_cols_map.items():
            val = props_b[prop_id]
            report_lines_b.append(f"{display_label:<26} {val}" if isinstance(val, str) else f"{display_label:<26} {val:.{decimals}f} {unit}")
        with col_rep_b:
            st.code("\n".join(report_lines_b), language=None)

########################-------------------------#############################
        st.markdown("### 📈 Ποσοστιαία Μεταβολή (Πίνακας Α → Πίνακας Β)")
        change_data = []
        for prop_id, (_, display_label, unit, decimals) in mech_cols_map.items():
            a, b = props_a[prop_id], props_b[prop_id]
            if isinstance(a, str) or isinstance(b, str) or a == "-" or b == "-":
                status_str, a_disp, b_disp = "N/A", str(a), str(b)
            else:
                a_disp, b_disp = f"{a:.2f}", f"{b:.2f}"
                if a != 0:
                    pct_change = ((b - a) / a) * 100
                    status_str = f"🟢 +{pct_change:.1f}%" if pct_change > 0 else (f"🔴 {pct_change:.1f}%" if pct_change < 0 else "⚪ 0.0%")
                else:
                    status_str = "N/A"
            change_data.append({
                "Μηχανική Ιδιότητα": f"{display_label} ({unit})" if unit else display_label,
                "Σύνθεση Α": a_disp, "Σύνθεση Β": b_disp, "Μεταβολή (%)": status_str
            })

        df_change = pd.DataFrame(change_data)
        df_change["Σύνθεση Α"] = df_change["Σύνθεση Α"].astype(str)
        df_change["Σύνθεση Β"] = df_change["Σύνθεση Β"].astype(str)
        with st.container(border=True): # <--- Η κάρτα για τον τελικό πίνακα
            st.dataframe(du.with_one_based_index(df_change), width='stretch')
"""
migrate_excel_to_db.py
-----------------------
Διαβάζει το υπάρχον Excel (με τα φύλλα *_RecipesList, *_MaterialsList,
*_MechProperties, "Erema Materials") και γεμίζει το SQLite database.

Τρέξε ΠΡΩΤΑ το init_db.py (μία φορά), μετά αυτό (κάθε φορά που θες να
ξαναφορτώσεις/ενημερώσεις τα δεδομένα από ένα Excel).

ΠΡΟΣΟΧΗ: Αυτό το script κάνει "καθαρή" φόρτωση -- σβήνει τα προηγούμενα
δεδομένα των πινάκων πριν ξαναγράψει, ώστε να μην έχεις διπλότυπα αν το
τρέξεις παραπάνω από μία φορά. Αν έχεις ήδη κάνει αλλαγές μέσα από το ίδιο
το πρόγραμμα (π.χ. από τη σελίδα Database), ΜΗΝ ξανατρέξεις αυτό το script
πάνω τους -- θα τις χάσεις. Χρησιμοποίησέ το μόνο για το αρχικό migration.
"""

import sqlite3
import pandas as pd
import re
import unicodedata
import sys

from init_db import DB_PATH, init_db

EXCEL_PATH = r"C:\MRP\Βιβλίο2tester.xlsx"  # <-- άλλαξε στο δικό σου path αν χρειάζεται


# ---------------------------------------------------------------- helpers
def clean_text(text):
    if pd.isna(text) or str(text).lower() == "nan":
        return ""
    return str(text).strip()


def clean_material_name(text):
    text = clean_text(text).replace("\xa0", " ")
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("C"))
    return re.sub(r"\s+", " ", text).strip()


def clean_numeric(val):
    clean_val = re.sub(r"[^\d.,]", "", str(val).replace(",", "."))
    try:
        return float(clean_val)
    except Exception:
        return None


def clean_code(val):
    s = clean_text(val)
    if s.endswith(".0"):
        s = s[:-2]
    return s


# ---------------------------------------------------------------- main
def get_categories(xl: pd.ExcelFile):
    recipe_sheets = {
        s.removesuffix("_RecipesList"): s for s in xl.sheet_names if s.endswith("_RecipesList")
    }
    material_sheets = {
        s.removesuffix("_MaterialsList"): s for s in xl.sheet_names if s.endswith("_MaterialsList")
    }
    return [c for c in recipe_sheets if c in material_sheets]


def migrate(excel_path: str = EXCEL_PATH, db_path: str = DB_PATH):
    init_db(db_path)  # βεβαιώνεται ότι υπάρχουν οι πίνακες

    xl = pd.ExcelFile(excel_path)
    categories = get_categories(xl)
    if not categories:
        print("❌ Δεν βρέθηκαν ζευγάρια *_RecipesList / *_MaterialsList.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # καθαρίζουμε πριν ξαναγεμίσουμε (idempotent migration)
    cur.execute("DELETE FROM recipe_materials;")
    cur.execute("DELETE FROM recipes;")
    cur.execute("DELETE FROM materials;")
    cur.execute("DELETE FROM mech_properties;")
    cur.execute("DELETE FROM erema_materials;")
    conn.commit()

    for category in categories:
        print(f"\n📦 Κατηγορία: {category}")

        # -------- materials --------
        mat_df = pd.read_excel(xl, f"{category}_MaterialsList")
        mat_df.columns = mat_df.columns.astype(str).str.strip()
        n_mat = 0
        for _, row in mat_df.iterrows():
            material = clean_material_name(row.get("Material", ""))
            if not material:
                continue
            code = clean_code(row.get("Code", ""))
            stock = clean_numeric(row.get("Stock (kg)", None))
            cur.execute(
                """INSERT OR IGNORE INTO materials (category, code, material, stock_kg)
                   VALUES (?, ?, ?, ?)""",
                (category, code, material, stock),
            )
            n_mat += 1
        print(f"  ✅ {n_mat} materials")

        # -------- mech properties (αν υπάρχει το sheet) --------
        mech_sheet = f"{category}_MechProperties"
        if mech_sheet in xl.sheet_names:
            mech_df = pd.read_excel(xl, mech_sheet)
            mech_df.columns = mech_df.columns.astype(str).str.strip()

            def col(name_options):
                for c in mech_df.columns:
                    for opt in name_options:
                        if opt.lower() in c.lower():
                            return c
                return None

            n_mech = 0
            for _, row in mech_df.iterrows():
                title = clean_material_name(row.get("Title", ""))
                if not title:
                    continue
                cur.execute(
                    """INSERT INTO mech_properties
                       (category, code, title, mfi, density, hardness_rockwell_r,
                        hardness_shore_d, tensile_modulus, flexural_mod, impact,
                        tensile_strain_yield, tensile_strain_break,
                        tensile_break_strength, tensile_yield_strength, hdt, vicat)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        category,
                        clean_code(row.get("KY", "")),
                        title,
                        clean_numeric(row.get("MFI(g/10min)")),
                        clean_numeric(row.get("Density (g/cm^3)")),
                        clean_numeric(row.get("Hardness Rockwell R")),
                        clean_numeric(row.get("Hardness Shore D")),
                        clean_numeric(row.get("Tensile Modulus (MPa)")),
                        clean_numeric(row.get("Flexural Mod (MPa)")),
                        clean_numeric(row.get("Impact (23,kJ/m^2)")),
                        clean_numeric(row.get("Tensile Strain (Yield) %")),
                        clean_numeric(row.get("Tensile Strain (Break) %")),
                        clean_numeric(row.get("Tensile Break Strength (MPa)")),
                        clean_numeric(row.get("Tensile Yield Strength (MPa)")),
                        clean_numeric(row.get("HDT (.45 Mpa)")),
                        clean_numeric(row.get("Vicat")),
                    ),
                )
                n_mech += 1
            print(f"  ✅ {n_mech} mech properties")
        else:
            print(f"  ⚠️  Δεν βρέθηκε sheet '{mech_sheet}'")

        # -------- recipes + recipe_materials (wide -> long) --------
        rec_df = pd.read_excel(xl, f"{category}_RecipesList")
        rec_df.columns = rec_df.columns.astype(str).str.strip()

        material_cols = sorted(
            [c for c in rec_df.columns if c.upper().startswith("Y")],
            key=lambda x: int("".join(filter(str.isdigit, x)) or 0),
        )
        percent_cols = sorted(
            [c for c in rec_df.columns if c.upper().startswith("PRC")],
            key=lambda x: int("".join(filter(str.isdigit, x)) or 0),
        )
        code_cols = sorted(
            [c for c in rec_df.columns if c.upper().startswith("KY")],
            key=lambda x: int("".join(filter(str.isdigit, x)) or 0),
        )

        n_recipes = 0
        n_rows = 0
        for _, row in rec_df.iterrows():
            title = clean_text(row.get("Title", ""))
            if not title:
                continue

            cur.execute(
                """INSERT OR IGNORE INTO recipes
                   (category, title, mixed_kg, net_kg, scrap_pct, return_boot_kg,
                    boot_pct, return_scrap_kg, total_return_kg, total_return_pct,
                    annual_consumption_kg, erema_category)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    category,
                    title,
                    clean_numeric(row.get("Μεικτά κιλά ")),
                    clean_numeric(row.get("Καθαρά κιλά")),
                    clean_numeric(row.get("Scrap ποσοστό%")),
                    clean_numeric(row.get("Επιστροφη μπουκ κιλα")),
                    clean_numeric(row.get("Μπουκ Ποσοστό%")),
                    clean_numeric(row.get("Επιστροφή scap κιλά")),
                    clean_numeric(row.get("Συνολική επιστροφή κιλα(3 χρόνια)")),
                    clean_numeric(row.get("Συνολικό ποσοστό επιστροφής %")),
                    clean_numeric(row.get("Κατανάλωση συνταγής / year")),
                    clean_text(row.get("Erema Category")),
                ),
            )
            recipe_id = cur.execute(
                "SELECT id FROM recipes WHERE category = ? AND title = ?",
                (category, title),
            ).fetchone()[0]
            n_recipes += 1

            for slot, (m_col, p_col, k_col) in enumerate(
                zip(material_cols, percent_cols, code_cols), start=1
            ):
                mat_name = clean_material_name(row.get(m_col, ""))
                if not mat_name or mat_name.lower() in ("nan", "none"):
                    continue
                pct = clean_numeric(row.get(p_col, 0))
                code = clean_code(row.get(k_col, ""))
                cur.execute(
                    """INSERT INTO recipe_materials
                       (recipe_id, slot, material_code, material_name, percent)
                       VALUES (?,?,?,?,?)""",
                    (recipe_id, slot, code, mat_name, pct),
                )
                n_rows += 1

        print(f"  ✅ {n_recipes} recipes, {n_rows} recipe-material γραμμές")

    # -------- Erema Materials (κοινό, όχι ανά κατηγορία) --------
    if "Erema Materials" in xl.sheet_names:
        erema_df = pd.read_excel(xl, "Erema Materials")
        erema_df.columns = erema_df.columns.astype(str).str.strip()
        cols = erema_df.columns.tolist()
        code_col, desc_col = cols[0], cols[1] if len(cols) > 1 else cols[0]
        n_erema = 0
        for _, row in erema_df.iterrows():
            desc = clean_material_name(row.get(desc_col, ""))
            if not desc:
                continue
            cur.execute(
                "INSERT INTO erema_materials (code, description) VALUES (?, ?)",
                (clean_code(row.get(code_col, "")), desc),
            )
            n_erema += 1
        print(f"\n✅ {n_erema} Erema materials")
    else:
        print("\n⚠️  Δεν βρέθηκε sheet 'Erema Materials'")

    conn.commit()
    conn.close()
    print(f"\n🎉 Migration ολοκληρώθηκε -> {db_path}")


if __name__ == "__main__":
    migrate()

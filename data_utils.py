"""
data_utils.py
--------------
Όλη η λογική πρόσβασης δεδομένων (φόρτωση/αποθήκευση) για το MRP πρόγραμμα,
πλέον πάνω σε SQLite αντί για Excel. Το app.py εισάγει από εδώ αντί να
διαβάζει Excel απευθείας.

Καμία εξάρτηση από streamlit εδώ -- καθαρή λογική δεδομένων.
"""

import sqlite3
import re
import unicodedata
import pandas as pd
from contextlib import contextmanager

DB_PATH = r"C:\\MRP\\database.db"  # <-- ίδιο path με το init_db.py


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------- cleaning
def clean_numeric(val):
    clean_val = re.sub(r"[^\d.,]", "", str(val).replace(",", "."))
    try:
        return float(clean_val)
    except Exception:
        return 0.0


def clean_text(text):
    if pd.isna(text) or str(text).lower() == "nan":
        return ""
    return str(text).strip()


def clean_material_name(text):
    text = clean_text(text).replace("\xa0", " ")
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("C"))
    return re.sub(r"\s+", " ", text).strip()


def normalize_material_name(text):
    text = clean_material_name(text)
    text = re.sub(r"\s*([,.;:/\\-])\s*", r"\1", text)
    return text.casefold()


def with_one_based_index(dataframe):
    dataframe = dataframe.copy()
    dataframe.index = range(1, len(dataframe) + 1)
    return dataframe


# --------------------------------------------------------------- categories
def get_categories() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM recipes ORDER BY category"
        ).fetchall()
    return [r[0] for r in rows]


# --------------------------------------------------------------- materials
def load_materials(category: str) -> pd.DataFrame:
    with get_connection() as conn:
        df = pd.read_sql(
            "SELECT code AS Code, material AS Material, stock_kg AS 'Stock (kg)' "
            "FROM materials WHERE category = ? ORDER BY material",
            conn,
            params=(category,),
        )
    return df


# --------------------------------------------------------------- recipes
def load_recipes(category: str) -> pd.DataFrame:
    """Επιστρέφει τις συνταγές μιας κατηγορίας σε WIDE format (Y1..Y7 / PRC1..PRC7 /
    KY1..KY7), ίδιο σχήμα με το παλιό df από Excel, ώστε η υπόλοιπη λογική του
    app.py (που δουλεύει πάνω σε αυτό το σχήμα) να αλλάξει όσο το δυνατόν λιγότερο."""
    with get_connection() as conn:
        recipes = pd.read_sql(
            "SELECT * FROM recipes WHERE category = ? ORDER BY title",
            conn,
            params=(category,),
        )
        rec_mats = pd.read_sql(
            """SELECT rm.* FROM recipe_materials rm
               JOIN recipes r ON r.id = rm.recipe_id
               WHERE r.category = ?""",
            conn,
            params=(category,),
        )

    rows = []
    for _, r in recipes.iterrows():
        row = {"Title": r["title"], "id": r["id"]}
        slots = rec_mats[rec_mats["recipe_id"] == r["id"]].sort_values("slot")
        for i in range(1, 8):
            slot_row = slots[slots["slot"] == i]
            if not slot_row.empty:
                sr = slot_row.iloc[0]
                row[f"KY{i}"] = sr["material_code"]
                row[f"Y{i}"] = sr["material_name"]
                row[f"PRC{i}"] = sr["percent"]
            else:
                row[f"KY{i}"] = None
                row[f"Y{i}"] = None
                row[f"PRC{i}"] = None
        row["Μεικτά κιλά "] = r["mixed_kg"]
        row["Καθαρά κιλά"] = r["net_kg"]
        row["Scrap ποσοστό%"] = r["scrap_pct"]
        row["Επιστροφη μπουκ κιλα"] = r["return_boot_kg"]
        row["Μπουκ Ποσοστό%"] = r["boot_pct"]
        row["Επιστροφή scap κιλά"] = r["return_scrap_kg"]
        row["Συνολική επιστροφή κιλα(3 χρόνια)"] = r["total_return_kg"]
        row["Συνολικό ποσοστό επιστροφής %"] = r["total_return_pct"]
        row["Κατανάλωση συνταγής / year"] = r["annual_consumption_kg"]
        row["Erema Category"] = r["erema_category"]
        rows.append(row)

    return pd.DataFrame(rows)


def save_recipe(recipe_id: int, edited_materials: pd.DataFrame):
    """Αντικαθιστά τα υλικά μιας συνταγής (edited_materials: στήλες
    'Κωδικός', 'Υλικό', 'Ποσοστό (%)') μέσα στη βάση."""
    with get_connection() as conn:
        conn.execute("DELETE FROM recipe_materials WHERE recipe_id = ?", (recipe_id,))
        for slot, (_, row) in enumerate(edited_materials.iterrows(), start=1):
            conn.execute(
                """INSERT INTO recipe_materials
                   (recipe_id, slot, material_code, material_name, percent)
                   VALUES (?,?,?,?,?)""",
                (
                    recipe_id,
                    slot,
                    clean_text(row.get("Κωδικός", "")),
                    clean_text(row.get("Υλικό", "")),
                    clean_numeric(row.get("Ποσοστό (%)", 0)),
                ),
            )


# --------------------------------------------------------------- mech properties
def load_mech_properties(category: str) -> pd.DataFrame | None:
    with get_connection() as conn:
        df = pd.read_sql(
            "SELECT * FROM mech_properties WHERE category = ?", conn, params=(category,)
        )
    if df.empty:
        return None
    df = df.rename(
        columns={
            "code": "KY",
            "title": "Title",
            "mfi": "MFI(g/10min)",
            "density": "Density (g/cm^3)",
            "hardness_rockwell_r": "Hardness Rockwell R",
            "hardness_shore_d": "Hardness Shore D",
            "tensile_modulus": "Tensile Modulus (MPa)",
            "flexural_mod": "Flexural Mod (MPa)",
            "impact": "Impact (23,kJ/m^2)",
            "tensile_strain_yield": "Tensile Strain (Yield) %",
            "tensile_strain_break": "Tensile Strain (Break) %",
            "tensile_break_strength": "Tensile Break Strength (MPa)",
            "tensile_yield_strength": "Tensile Yield Strength (MPa)",
            "hdt": "HDT (.45 Mpa)",
            "vicat": "Vicat",
        }
    )
    return df.drop(columns=["id", "category"])


# --------------------------------------------------------------- erema
def load_erema_materials() -> pd.DataFrame | None:
    with get_connection() as conn:
        df = pd.read_sql("SELECT code AS Κωδικός, description AS Περιγραφή FROM erema_materials", conn)
    return df if not df.empty else None

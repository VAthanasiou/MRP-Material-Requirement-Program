r"""
init_db.py
----------
Δημιουργεί το SQLite database (.db) με το schema που χρειάζεται το MRP πρόγραμμα.
Τρέχεται ΜΙΑ ΦΟΡΑ (ή όποτε θέλεις να ξαναφτιάξεις από το μηδέν το schema).

ΣΗΜΑΝΤΙΚΟ: Άλλαξε το DB_PATH παρακάτω ώστε να δείχνει στο path που θέλεις
στον δικό σου δίσκο (π.χ. r"C:\MRP\database.db").
"""

import sqlite3
import os

# -----------------------------------------------------------------------
# >>> ΑΛΛΑΞΕ ΕΔΩ το path όπου θέλεις να αποθηκεύεται το database <<<
DB_PATH = r"C:\\MRP\\database.db"
# -----------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    code TEXT,
    material TEXT NOT NULL,
    stock_kg REAL,
    UNIQUE(category, material)
);

CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    mixed_kg REAL,
    net_kg REAL,
    scrap_pct REAL,
    return_boot_kg REAL,
    boot_pct REAL,
    return_scrap_kg REAL,
    total_return_kg REAL,
    total_return_pct REAL,
    annual_consumption_kg REAL,
    erema_category TEXT,
    UNIQUE(category, title)
);

CREATE TABLE IF NOT EXISTS recipe_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    slot INTEGER NOT NULL,
    material_code TEXT,
    material_name TEXT,
    percent REAL,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mech_properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    code TEXT,
    title TEXT,
    mfi REAL,
    density REAL,
    hardness_rockwell_r REAL,
    hardness_shore_d REAL,
    tensile_modulus REAL,
    flexural_mod REAL,
    impact REAL,
    tensile_strain_yield REAL,
    tensile_strain_break REAL,
    tensile_break_strength REAL,
    tensile_yield_strength REAL,
    hdt REAL,
    vicat REAL
);

CREATE TABLE IF NOT EXISTS erema_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_recipe_materials_recipe_id ON recipe_materials(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category);
CREATE INDEX IF NOT EXISTS idx_materials_category ON materials(category);
CREATE INDEX IF NOT EXISTS idx_mech_properties_category ON mech_properties(category);
"""


def init_db(db_path: str = DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"✅ Database schema έτοιμο στο: {db_path}")


if __name__ == "__main__":
    init_db()

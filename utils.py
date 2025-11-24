# utils.py
import os
import pandas as pd
from datetime import datetime

EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

def rows_to_df(rows):
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)

def export_dataframe(df, prefix="export"):
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    filename = f"{prefix}_{now}.xlsx"
    path = os.path.join(EXPORT_DIR, filename)
    df.to_excel(path, index=False)
    return path

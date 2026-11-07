from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parent

# Find your data folder, whether named "data" or "Data".
data_folder = root / "data"
if not data_folder.exists():
    data_folder = root / "Data"

ma_folder = data_folder / "raw" / "MA"

for filename in ["MAPlans05052026.csv", "MANetworks05052026.csv"]:
    path = ma_folder / filename
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")

    print(f"\nFILE: {filename}")
    print("Rows:", len(df))
    print("Columns:", df.columns.tolist())

    # Show available years and states if these columns exist.
    for column in ["BusinessYear", "StateCode"]:
        if column in df.columns:
            print(f"{column}:", df[column].dropna().unique().tolist())

    print(df.head(2).to_string(index=False))
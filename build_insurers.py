from pathlib import Path
import pandas as pd

# Locate the project's data folder.
root = Path(__file__).resolve().parent
data = root / "data"
if not data.exists():
    data = root / "Data"

# Each dictionary represents one insurer-directory option.
insurers = [
    {
        "insurer": "Aetna",
        "directory_url":
            "https://www.aetna.com/individuals-families/find-a-doctor.html",
        "instructions":
            "Sign in or choose your exact plan to search for providers.",
    },
    {
        "insurer": "UnitedHealthcare",
        "directory_url":
            "https://www.uhc.com/find-a-doctor",
        "instructions":
            "Use the provider search for your exact plan or member account.",
    },
    {
        "insurer": "Boston University SHIP — Aetna Student Health",
        "directory_url": 
            "https://www.aetna.com/docfind/jsp/rdIndex.jsp?langpref=en&site_id=studenthealth",
        "instructions": 
            "Select Boston University or sign in with your member details to check providers."
    }
    
]

# Convert the list into a table.
df = pd.DataFrame(insurers)

# Save the table.
clean = data / "clean"
clean.mkdir(parents=True, exist_ok=True)

output = clean / "insurers.csv"
df.to_csv(output, index=False)

print(df.to_string(index=False))
print(f"\nSaved to: {output}")
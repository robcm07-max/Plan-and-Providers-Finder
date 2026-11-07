from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parent
data = root / "Data"
if not data.exists():
    data = root / "Data"

raw = data / "raw" / "MA"

plans = pd.read_csv(raw / "MAPlans05052026.csv", dtype=str)
networks = pd.read_csv(raw / "MANetworks05052026.csv", dtype=str)

# Keep only 2026 MA individual medical plans.
plans = plans[
    (plans["BUSINESS YEAR"] == "2026")
    & (plans["STATE CODE"] == "MA")
    & (plans["MARKET COVERAGE"] == "Individual")
    & (plans["DENTAL ONLY PLAN"] == "No")
].copy()

networks = networks[
    (networks["BUSINESS YEAR"] == "2026")
    & (networks["STATE CODE"] == "MA")
    & (networks["MARKET COVERAGE"] == "Individual")
    & (networks["DENTAL PLAN ONLY"] == "No")
].copy()

keys = ["BUSINESS YEAR", "STATE CODE", "ISSUER ID", "NETWORK ID"]

# Collapse cost-sharing variants for our basic plan dropdown.
plans = plans.drop_duplicates(
    ["BUSINESS YEAR", "STATE CODE", "STANDARD COMPONENT ID"]
)

# Keep network information and check that each join key is unique.
networks = networks[
    keys + ["NETWORK NAME", "NETWORK URL"]
].drop_duplicates()

joined = plans.merge(
    networks,
    on=keys,
    how="left",
    validate="many_to_one",
    indicator=True,
)

print("Plans without a network match:",
      (joined["_merge"] == "left_only").sum())

out = joined.rename(columns={
    "BUSINESS YEAR": "year",
    "STATE CODE": "state",
    "STANDARD COMPONENT ID": "plan_id",
    "PLAN MARKETING NAME": "plan_name",
    "ISSUER ID": "issuer_id",
    "ISSUER NAME": "insurer",
    "PLAN TYPE": "plan_type",
    "METAL LEVEL": "metal_level",
    "NETWORK NAME": "network_name",
    "NETWORK URL": "directory_url",
})

# Unknown values stay blank; a missing premium is not zero.
out["premium"] = pd.NA

columns = [
    "state", "year", "plan_id", "plan_name", "issuer_id",
    "insurer", "plan_type", "metal_level", "premium",
    "network_name", "directory_url",
]

out = out[columns].sort_values(["issuer_id", "plan_name"])

clean = data / "clean"
clean.mkdir(parents=True, exist_ok=True)
out.to_csv(clean / "plans.csv", index=False)

print(f"Saved {len(out)} plans to {clean / 'plans.csv'}")
print(out[["plan_name", "network_name"]].head().to_string(index=False))
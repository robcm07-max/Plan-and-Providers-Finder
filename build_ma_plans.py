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

print(out[["plan_name", "network_name"]].head().to_string(index=False))

print(
    out[["issuer_id", "network_name"]]
    .drop_duplicates()
    .to_string(index=False)
)
issuer_names = {
    "31779": "UnitedHealthcare Insurance Company",
    "34484": "Health New England",
    "36046": "Harvard Pilgrim Health Care",
    "41304": "Mass General Brigham Health Plan",
    "42690": "Blue Cross and Blue Shield of Massachusetts HMO Blue",
    "59763": "Tufts Health Public Plans",
    "82569": "Boston Medical Center Health Plan",
    "88806": "Fallon Community Health Plan",
}

out["insurer"] = out["issuer_id"].map(issuer_names)
issuer_directories = {
    "31779": "https://www.uhc.com/find-a-doctor",
    "34484": "https://healthnewengland.org/provider-search",
    "36046": "https://www.harvardpilgrim.org/public/find-a-provider",
    "41304": "https://massgeneralbrighamhealthplan.org/members/find-provider",
    "42690": "https://www.bluecrossma.com/findadoctor",
    "59763": "https://tuftshealthplan.com/plans-benefits/provider-networks",
    "82569": "https://www.wellsense.org/members/ma/clarity-plans/find-a-provider",
    "88806": "https://www.myfallonhealth.org/findphysician/search.aspx",
}

out["directory_url"] = out["issuer_id"].map(issuer_directories)

print("Plans missing directory links:",
      out["directory_url"].isna().sum())
print("Plans missing insurer names:", out["insurer"].isna().sum())
out.to_csv(clean / "plans.csv", index=False)
print(f"Saved {len(out)} plans to {clean / 'plans.csv'}")
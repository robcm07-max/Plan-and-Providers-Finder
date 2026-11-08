from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "Data"
if not DATA.exists():
    DATA = ROOT / "data"

benefits = pd.read_csv(
    DATA / "raw" / "MA" / "MABenefits05052026.csv",
    dtype=str,
    encoding="utf-8-sig",
).fillna("")

plans = pd.read_csv(
    DATA / "clean" / "plans.csv",
    dtype=str,
).fillna("")

# Keep only benefits belonging to our 2026 MA plans.
benefits = benefits[
    (benefits["BUSINESS YEAR"] == "2026")
    & (benefits["STATE CODE"] == "MA")
    & benefits["STANDARD COMPONENT ID"].isin(plans["plan_id"])
].copy()

# Preserve the full variant ID: different variants can have
# different benefits or cost-sharing rules.
benefits = benefits.rename(columns={
    "BUSINESS YEAR": "year",
    "STATE CODE": "state",
    "ISSUER ID": "issuer_id",
    "STANDARD COMPONENT ID": "plan_id",
    "PLAN ID": "variant_id",
    "BENEFIT NAME": "benefit_name",
    "IS COVERED": "covered",
    "QUANTITY LIMIT ON SVC": "has_quantity_limit",
    "LIMIT QUANTITY": "limit_quantity",
    "LIMIT UNIT": "limit_unit",
    "EXCLUSIONS": "exclusions",
    "EXPLANATION": "explanation",
    "IS SUBJECTED TO DED TIER 1": "subject_to_deductible_tier1",
    "IMPORT DATE": "source_import_date",
})

columns = [
    "year",
    "state",
    "issuer_id",
    "plan_id",
    "variant_id",
    "benefit_name",
    "covered",
    "has_quantity_limit",
    "limit_quantity",
    "limit_unit",
    "exclusions",
    "explanation",
    "subject_to_deductible_tier1",
    "source_import_date",
]

output = benefits[columns].drop_duplicates().sort_values(
    ["plan_id", "variant_id", "benefit_name"]
)

# Preserve blanks as unknown; do not turn them into "No."
output["source_url"] = (
    "https://www.cms.gov/marketplace/resources/data/"
    "state-based-public-use-files"
)

destination = DATA / "clean" / "benefits.csv"
destination.parent.mkdir(parents=True, exist_ok=True)
output.to_csv(destination, index=False)

print(f"Saved {len(output)} benefit records")
print("Plans:", output["plan_id"].nunique())
print("Variants:", output["variant_id"].nunique())
print("Saved to:", destination)
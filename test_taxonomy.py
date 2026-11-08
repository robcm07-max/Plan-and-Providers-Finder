import json
import time
from urllib.parse import urlencode
from urllib.request import urlopen

# Candidate search terms to test, one per need.
terms = [
    "Prosthetist",
    "Orthotist",
    "Physical Medicine & Rehabilitation",
    "Cardiovascular Disease",
]
for term in terms:
    parameters = {
        "version": "2.1",
        "state": "MA",
        "city": "Boston",
        "taxonomy_description": term,
        "address_purpose": "LOCATION",
        "enumeration_type": "NPI-1",
        "limit": 5,
    }
    url = "https://npiregistry.cms.hhs.gov/api/?" + urlencode(parameters)

    try:
        with urlopen(url, timeout=30) as response:
            data = json.load(response)

        if "Errors" in data:
            print(f"{term!r}: API error {data['Errors']}")
        else:
            results = data.get("results", [])
            specialties = sorted({
                item.get("desc") or ""
                for provider in results
                for item in provider.get("taxonomies", [])
            })
            print(f"{term!r}: {len(results)} results; specialties seen: {specialties[:3]}")
    except Exception as error:
        print(f"{term!r}: request failed ({error})")

    time.sleep(1)
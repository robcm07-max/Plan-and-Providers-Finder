import json
from urllib.parse import urlencode
from urllib.request import urlopen
import streamlit as st

st.title("Find providers in Boston")

# Get the specialty from the person using the app.
specialty = st.text_input(
    "Enter a specialty",
    value="Family Medicine",
    placeholder="For example: Dermatology",
).strip()

# Search only when the button is clicked.
if st.button("Search providers"):
    if not specialty:
        st.warning("Please enter a specialty.")
    else:
        parameters = {
            "version": "2.1",
            "state": "MA",
            "city": "Boston",
            "taxonomy_description": specialty,
            "address_purpose": "LOCATION",
            "enumeration_type": "NPI-1",
            "limit": 20,
        }

        url = (
            "https://npiregistry.cms.hhs.gov/api/?"
            + urlencode(parameters)
        )

        try:
            with st.spinner("Searching for providers..."):
                with urlopen(url, timeout=30) as response:
                    data = json.load(response)

            if "Errors" in data:
                st.error("The search could not process this request.")
                st.json(data["Errors"])
            elif not data.get("results"):
                st.info("No results found. Try another specialty.")
            else:
                st.write(
                    f"Records returned: {data.get('result_count', 0)}"
                )
                st.json(data)

        except Exception as error:
            st.error(f"Could not load providers: {error}")

st.caption(
    "These are provider registry listings. "
    "Insurance participation and appointment availability are not verified."
)
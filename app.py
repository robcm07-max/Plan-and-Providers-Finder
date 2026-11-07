import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from math import radians, sin, cos, sqrt, atan2

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Plan Places Finder", layout="wide")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "Data"
if not DATA.exists():
    DATA = ROOT / "data"


@st.cache_data
def load_data():
    hospitals = pd.read_csv(
        DATA / "clean" / "hospitals.csv",
        dtype={"zip": str},
    )
    plans = pd.read_csv(
        DATA / "clean" / "plans.csv",
        dtype={"plan_id": str},
    )

    for column in ["rating", "latitude", "longitude"]:
        hospitals[column] = pd.to_numeric(
            hospitals[column], errors="coerce"
        )

    return hospitals, plans


def search_providers(city, specialty, provider_type):
    parameters = {
        "version": "2.1",
        "state": "MA",
        "taxonomy_description": specialty,
        "address_purpose": "LOCATION",
        "enumeration_type": provider_type,
        "limit": 15,
    }

    if city:
        parameters["city"] = city

    url = (
        "https://npiregistry.cms.hhs.gov/api/?"
        + urlencode(parameters)
    )

    with urlopen(url, timeout=30) as response:
        return json.load(response)


def format_providers(results):
    rows = []

    for provider in results:
        basic = provider.get("basic", {})

        name = basic.get("organization_name")
        if not name:
            name = " ".join(
                basic.get(part, "")
                for part in ["first_name", "middle_name", "last_name"]
                if basic.get(part)
            )

        address = next(
            (
                item
                for item in provider.get("addresses", [])
                if item.get("address_purpose") == "LOCATION"
            ),
            {},
        )

        specialties = ", ".join(
            item["desc"]
            for item in provider.get("taxonomies", [])
            if item.get("desc")
        )

        street = " ".join(
            address.get(part, "")
            for part in ["address_1", "address_2"]
            if address.get(part)
        )

        rows.append({
            "Name": name or "Name unavailable",
            "Specialty": specialties,
            "Address": street,
            "City": address.get("city", ""),
            "State": address.get("state", ""),
            "ZIP": address.get("postal_code", "")[:5],
            "Phone": address.get("telephone_number", ""),
            "NPI": str(provider.get("number", "")),
        })

    return pd.DataFrame(rows)

def geocode_address(address):
    parameters = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "format": "json",
    }

    url = (
        "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?"
        + urlencode(parameters)
    )

    with urlopen(url, timeout=30) as response:
        result = json.load(response)

    return result.get("result", {}).get("addressMatches", [])


def distance_miles(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(
        radians, [lat1, lon1, lat2, lon2]
    )

    difference_lat = lat2 - lat1
    difference_lon = lon2 - lon1

    a = (
        sin(difference_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(difference_lon / 2) ** 2
    )

    a = max(0.0, min(1.0, a))
    return 3958.8 * 2 * atan2(sqrt(a), sqrt(1 - a))

# Cache provider coordinates so repeat searches are faster.
@st.cache_data(ttl=86400, show_spinner=False)
def get_provider_coordinates(address):
    matches = geocode_address(address)

    # Only use an unambiguous address match.
    if len(matches) != 1:
        return None

    coordinates = matches[0]["coordinates"]
    return coordinates["y"], coordinates["x"]

hospitals, plans = load_data()

st.title("Plan Places Finder")
st.write("Explore Massachusetts hospitals, plans, and providers.")

st.info(
    "Hospital and provider results are not matched to your insurance "
    "network. Confirm coverage with your insurer before getting care."
)

# Plan selection
st.sidebar.header("Your plan")

selected_index = st.sidebar.selectbox(
    "Choose a 2026 MA marketplace plan",
    options=plans.index.tolist(),
    format_func=lambda index: (
        f"{plans.at[index, 'insurer']} — "
        f"{plans.at[index, 'plan_name']}"
    ),
)

plan = plans.loc[selected_index]

st.subheader("Selected plan")
st.write(f"**{plan['plan_name']}**")
st.write(f"Insurer: {plan['insurer']}")

col1, col2 = st.columns(2)
col1.metric("Plan type", str(plan["plan_type"]))
col2.metric("Metal level", str(plan["metal_level"]))

st.write(f"**Network:** {plan['network_name']}")

directory_url = plan.get("directory_url")
if pd.notna(directory_url) and str(directory_url).startswith(
    ("https://", "http://")
):
    st.link_button(
        "Check coverage in the insurer’s directory",
        str(directory_url),
    )

st.caption(
    "Choosing a plan shows its details and directory link. "
    "It does not filter the hospitals or providers below by coverage."
)

# Hospital filters
st.sidebar.header("Hospital filters")

types = st.sidebar.multiselect(
    "Hospital type",
    sorted(hospitals["type"].dropna().unique()),
)

min_rating = st.sidebar.slider("Minimum rating", 1, 5, 1)
emergency_only = st.sidebar.checkbox("Emergency services only")

filtered = hospitals.copy()

if types:
    filtered = filtered[filtered["type"].isin(types)]

filtered = filtered[
    filtered["rating"].isna()
    | (filtered["rating"] >= min_rating)
]

if emergency_only:
    filtered = filtered[
        filtered["emergency"].astype(str).str.strip().str.lower()
        == "yes"
    ]

# Address and radius search
st.divider()
st.subheader("Find hospitals near an address")

st.caption(
    "Your search address is sent to the U.S. Census Geocoder. "
    "You can use a nearby street address instead of your home."
)

with st.form("hospital_address_search"):
    search_address = st.text_input(
        "Street address, city, state, and ZIP",
        placeholder="123 Main Street, Boston, MA 02101",
    )

    radius = st.slider(
        "Search radius in miles",
        min_value=1,
        max_value=100,
        value=10,
    )

    find_nearby = st.form_submit_button("Find nearby hospitals")

if find_nearby:
    st.session_state.pop("hospital_origin", None)

    if not search_address.strip():
        st.warning("Enter a complete street address.")
    else:
        try:
            with st.spinner("Finding your address..."):
                matches = geocode_address(search_address.strip())

            if not matches:
                st.warning(
                    "Address not found. Check the street, city, "
                    "state, and ZIP, then try again."
                )
            elif len(matches) > 1:
                st.warning(
                    "More than one address matched. "
                    "Add a ZIP code or make the address more specific."
                )
            else:
                match = matches[0]

                st.session_state["hospital_origin"] = {
                    "latitude": match["coordinates"]["y"],
                    "longitude": match["coordinates"]["x"],
                    "address": match["matchedAddress"],
                    "radius": radius,
                }

        except Exception:
            st.error(
                "The address lookup failed. Please try again."
            )

if st.button("Clear address filter"):
    st.session_state.pop("hospital_origin", None)

origin = st.session_state.get("hospital_origin")

if origin:
    st.write(f"**Searching near:** {origin['address']}")
    st.write(f"**Radius:** {origin['radius']} miles")

    # Keep the existing hospital type, rating, and emergency filters.
    filtered = filtered.dropna(
        subset=["latitude", "longitude"]
    ).copy()

    if not filtered.empty:
        filtered["distance_miles"] = filtered.apply(
            lambda row: distance_miles(
                origin["latitude"],
                origin["longitude"],
                row["latitude"],
                row["longitude"],
            ),
            axis=1,
        )
    else:
        filtered["distance_miles"] = pd.Series(dtype=float)

    filtered = filtered[
        filtered["distance_miles"] <= origin["radius"]
    ].sort_values("distance_miles")

    filtered["distance_miles"] = filtered["distance_miles"].round(1)

    st.caption(
        "Approximate straight-line distances to hospital ZIP-code "
        "centers—not driving distances. Hospitals without coordinates "
        "are excluded from proximity results."
    )
else:
    st.caption(
        "No address filter is active. Showing Massachusetts hospitals "
        "that match the sidebar filters."
    )

st.subheader(f"{len(filtered)} hospitals match")

map_data = filtered.dropna(subset=["latitude", "longitude"])

if map_data.empty:
    st.info("No hospital locations match. Try a wider radius or fewer filters.")
else:
    st.map(
        map_data,
        latitude="latitude",
        longitude="longitude",
    )

display_columns = ["name", "city", "type", "rating", "emergency"]

if "distance_miles" in filtered.columns:
    display_columns.insert(2, "distance_miles")

st.dataframe(
    filtered[display_columns],
    hide_index=True,
    use_container_width=True,
)

st.caption(
    "Hospitals without ratings remain included. "
    "Insurance participation is not verified."
)
# Provider search
st.divider()
st.subheader("Find doctors and urgent care near an address")

st.caption(
    "Addresses are sent to the U.S. Census Geocoder to calculate "
    "approximate straight-line distances. These are not driving distances."
)

with st.form("provider_proximity_search"):
    care_type = st.selectbox(
        "Type of care",
        ["Individual providers", "Urgent care"],
    )

    user_address = st.text_input(
        "Search near this street address",
        placeholder="Street, city, MA, ZIP",
    )

    search_city = st.text_input(
        "City to search for providers",
        value="Boston",
        help=(
            "Leave blank to search Massachusetts. A city filter excludes "
            "providers in neighboring cities, even if they are nearby."
        ),
    )

    specialty = st.text_input(
        "Specialty — ignored for urgent care",
        value="Family Medicine",
        placeholder="For example: Dermatology",
    )

    provider_radius = st.slider(
        "Provider search radius in miles",
        min_value=1,
        max_value=100,
        value=10,
    )

    submitted = st.form_submit_button("Find nearby providers")

if submitted:
    # Clear old results so they cannot be mistaken for this search.
    st.session_state.pop("provider_proximity_results", None)

    if care_type == "Urgent care":
        search_specialty = "Urgent Care"
        provider_type = "NPI-2"
    else:
        search_specialty = specialty.strip()
        provider_type = "NPI-1"

    if not user_address.strip():
        st.warning("Enter a complete street address.")
    elif not search_specialty:
        st.warning("Enter a specialty.")
    else:
        try:
            with st.spinner("Finding your search address..."):
                origin_matches = geocode_address(user_address.strip())

            if not origin_matches:
                st.warning(
                    "Your address was not found. Check the street, "
                    "city, state, and ZIP."
                )
            elif len(origin_matches) != 1:
                st.warning(
                    "Multiple addresses matched. Please enter "
                    "a more specific address, including ZIP."
                )
            else:
                origin = origin_matches[0]
                origin_lat = origin["coordinates"]["y"]
                origin_lon = origin["coordinates"]["x"]

                with st.spinner("Searching the provider registry..."):
                    response = search_providers(
                        search_city.strip(),
                        search_specialty,
                        provider_type,
                    )

                if "Errors" in response:
                    st.error("The registry could not process this search.")
                    st.json(response["Errors"])
                else:
                    providers = format_providers(
                        response.get("results", [])
                    )

                    located_rows = []
                    unavailable_rows = []

                    if not providers.empty:
                        progress = st.progress(
                            0, text="Finding provider locations..."
                        )

                        for position, (_, row) in enumerate(
                            providers.iterrows(), start=1
                        ):
                            record = row.to_dict()

                            address_text = ", ".join(
                                str(record.get(field, "")).strip()
                                for field in [
                                    "Address", "City", "State", "ZIP"
                                ]
                                if str(record.get(field, "")).strip()
                            )

                            coordinates = None

                            if record.get("Address"):
                                try:
                                    coordinates = get_provider_coordinates(
                                        address_text
                                    )
                                except Exception:
                                    # Keep the provider visible even when
                                    # its address lookup fails.
                                    coordinates = None

                            if coordinates is None:
                                record["Distance status"] = (
                                    "Unavailable — address not matched "
                                    "or lookup failed"
                                )
                                unavailable_rows.append(record)
                            else:
                                latitude, longitude = coordinates

                                record["latitude"] = latitude
                                record["longitude"] = longitude
                                record["distance_miles"] = distance_miles(
                                    origin_lat,
                                    origin_lon,
                                    latitude,
                                    longitude,
                                )

                                located_rows.append(record)

                            progress.progress(
                                position / len(providers),
                                text=(
                                    f"Checked {position} of "
                                    f"{len(providers)} provider locations"
                                ),
                            )

                        progress.empty()

                    nearby = pd.DataFrame(located_rows)

                    if not nearby.empty:
                        # Filter before rounding the distance.
                        nearby = nearby[
                            nearby["distance_miles"] <= provider_radius
                        ].sort_values("distance_miles")

                        nearby["distance_miles"] = (
                            nearby["distance_miles"].round(1)
                        )

                    st.session_state["provider_proximity_results"] = {
                        "nearby": nearby,
                        "unavailable": pd.DataFrame(unavailable_rows),
                        "searched_count": len(providers),
                        "origin_address": origin["matchedAddress"],
                        "radius": provider_radius,
                        "specialty": search_specialty,
                        "city": search_city.strip() or "Massachusetts",
                    }

        except Exception:
            st.error(
                "The search could not finish. Please try again."
            )

# Keep results visible when another app filter changes.
saved = st.session_state.get("provider_proximity_results")

if saved is not None:
    nearby = saved["nearby"]
    unavailable = saved["unavailable"]

    st.write(f"**Near:** {saved['origin_address']}")
    st.write(
        f"**Search:** {saved['specialty']} in {saved['city']} "
        f"within {saved['radius']} miles"
    )

    st.warning(
        f"Checked {saved['searched_count']} registry listings "
        "(up to 15 per search). Results are sorted by distance "
        "among these listings, not all nearby providers."
    )

    if nearby.empty:
        st.info(
            "None of the successfully located listings were within "
            "your radius. Try a wider radius or a different search city."
        )
    else:
        st.subheader(f"{len(nearby)} listings within your radius")

        st.map(
            nearby,
            latitude="latitude",
            longitude="longitude",
        )

        st.dataframe(
            nearby[
                [
                    "Name",
                    "Specialty",
                    "distance_miles",
                    "Address",
                    "City",
                    "State",
                    "ZIP",
                    "Phone",
                    "NPI",
                ]
            ].rename(
                columns={"distance_miles": "Approx. distance (miles)"}
            ),
            hide_index=True,
            use_container_width=True,
        )

    if not unavailable.empty:
        with st.expander(
            f"{len(unavailable)} listings with distance unavailable"
        ):
            st.write(
                "These listings could not be located reliably. "
                "We cannot determine whether they are within your radius."
            )
            st.dataframe(
                unavailable,
                hide_index=True,
                use_container_width=True,
            )

st.caption(
    "Source: CMS NPI Registry. The displayed location is the primary "
    "practice address; providers may have additional locations. "
    "Insurance participation, opening hours, and appointment "
    "availability are not verified."
)
# Sources
st.divider()
st.caption(
    "Hospital source: CMS Hospital General Information. "
    "Plan source: CMS 2026 Massachusetts State-Based Exchange "
    "Public Use Files. Insurer directory links are manually maintained."
)

with st.expander("What do these insurance terms mean?"):
    st.write("**Premium:** the amount you pay each month for insurance.")
    st.write(
        "**Deductible:** the amount you pay for certain covered services "
        "before your plan starts sharing those costs."
    )
    st.write("**Copay:** a fixed amount you pay for a covered service.")
    st.write(
        "**Coinsurance:** your percentage of the cost of a covered service."
    )
    st.write(
        "**Out-of-pocket maximum:** the most you pay for covered "
        "in-network services during the plan year. Premiums and "
        "noncovered services generally do not count toward this limit."
    )
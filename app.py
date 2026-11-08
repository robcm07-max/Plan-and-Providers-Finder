import json
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Plan Places Finder", layout="wide")

# Smooth scrolling when a table-of-contents link is clicked.
st.markdown(
    """
    <style>
    html, body, [data-testid="stMain"], section.main {
        scroll-behavior: smooth;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "Data"
if not DATA.exists():
    DATA = ROOT / "data"


# ---------------------------------------------------------------------
# Data and helper functions
# ---------------------------------------------------------------------

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
            "ZIP": (address.get("postal_code") or "")[:5],
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


def run_provider_search(
    origin_lat, origin_lon, city, specialty, provider_type, radius
):
    """Search the NPI Registry, locate each listing, and keep the ones
    inside the radius. Returns a dictionary that is saved for display."""
    try:
        response = search_providers(city, specialty, provider_type)
    except Exception:
        return {"failed": True}

    if "Errors" in response:
        return {"failed": True}

    providers = format_providers(response.get("results", []))

    located_rows = []
    unavailable_rows = []

    if not providers.empty:
        progress = st.progress(0, text="Finding provider locations...")

        for position, (_, row) in enumerate(
            providers.iterrows(), start=1
        ):
            record = row.to_dict()

            address_text = ", ".join(
                str(record.get(field, "")).strip()
                for field in ["Address", "City", "State", "ZIP"]
                if str(record.get(field, "")).strip()
            )

            coordinates = None

            if record.get("Address"):
                try:
                    coordinates = get_provider_coordinates(address_text)
                except Exception:
                    # Keep the provider visible even if the lookup fails.
                    coordinates = None

            if coordinates is None:
                record["Distance status"] = (
                    "Unavailable — address not matched or lookup failed"
                )
                unavailable_rows.append(record)
            else:
                latitude, longitude = coordinates
                record["latitude"] = latitude
                record["longitude"] = longitude
                record["distance_miles"] = distance_miles(
                    origin_lat, origin_lon, latitude, longitude
                )
                located_rows.append(record)

            progress.progress(
                position / len(providers),
                text=(
                    f"Checked {position} of {len(providers)} "
                    "provider locations"
                ),
            )

        progress.empty()

    nearby = pd.DataFrame(located_rows)

    if not nearby.empty:
        # Filter before rounding the distance.
        nearby = nearby[
            nearby["distance_miles"] <= radius
        ].sort_values("distance_miles").copy()

        nearby["distance_miles"] = nearby["distance_miles"].round(1)

    return {
        "nearby": nearby,
        "unavailable": pd.DataFrame(unavailable_rows),
        "searched_count": len(providers),
        "specialty": specialty,
        "city": city or "Massachusetts",
    }


def show_provider_results(result, radius):
    """Display one saved provider search (doctors or urgent care)."""
    if result.get("failed"):
        st.error(
            "The provider registry could not process this search. "
            "Please try again."
        )
        return

    nearby = result["nearby"]
    unavailable = result["unavailable"]

    st.write(
        f"**Search:** {result['specialty']} in {result['city']} "
        f"within {radius} miles"
    )

    st.warning(
        f"Checked {result['searched_count']} registry listings "
        "(up to 15 per search). Results are sorted by distance "
        "among these listings, not all nearby providers."
    )

    if nearby.empty:
        st.info(
            "None of the successfully located listings were within "
            "your radius. Try a wider radius or a different search city."
        )
    else:
        st.write(f"**{len(nearby)} listings within your radius**")

        st.map(nearby, latitude="latitude", longitude="longitude")

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


hospitals, plans = load_data()


# ---------------------------------------------------------------------
# Sidebar: table of contents
# ---------------------------------------------------------------------

st.sidebar.title("On this page")
st.sidebar.markdown(
    "- [What matters to you](#what-matters)\n"
    "- [Your plan](#your-plan)\n"
    "- [Find care near you](#find-care)\n"
    "- [Questions and terms (FAQ)](#faq)\n"
    "- [Sources and limits](#sources)\n"
)


# ---------------------------------------------------------------------
# Top of page
# ---------------------------------------------------------------------

st.title("Plan Places Finder")
st.write(
    "Health insurance can be confusing. Tell us what matters to you, "
    "look at a plan, and see care near you in Massachusetts."
)

st.info(
    "Hospital and provider results are not matched to your insurance "
    "network. Confirm coverage with your insurer before getting care."
)


# ---------------------------------------------------------------------
# Section 1: what matters to you
# ---------------------------------------------------------------------

NEEDS = {
    "Emergency care": {
        "look_for": "Hospitals with emergency services near you. "
                    "The hospital map further down can filter for these.",
        "ask": "Is the nearest emergency room in my network, and what "
               "is my cost for an emergency visit?",
    },
    "Hearing care": {
        "look_for": "Coverage for hearing exams, and separately for "
                    "hearing aids, which many plans limit or exclude.",
        "ask": "Are hearing exams and hearing aids covered, and "
               "what is the limit?",
    },
    "Dental care": {
        "look_for": "Dental is often sold as a separate plan. Our plan "
                    "list does not include dental-only plans.",
        "ask": "Is dental included in this plan, or do I need a "
               "separate dental plan?",
    },
    "Amputee and mobility needs": {
        "look_for": "Coverage for prosthetics, orthotics, and "
                    "mobility equipment, including repair and "
                    "replacement limits.",
        "ask": "Are prosthetics and durable medical equipment covered, "
               "and which suppliers are in network?",
    },
    "Ongoing disease care": {
        "look_for": "Specialists, regular lab work, and prescription "
                    "coverage for a long-term condition.",
        "ask": "Are my specialists and my medications covered, and do "
               "I need referrals?",
    },
    "Lower monthly cost": {
        "look_for": "Bronze plans usually have lower monthly premiums "
                    "but higher costs when you use care.",
        "ask": "What is the monthly premium for my age and "
               "address, and what is the deductible?",
    },
    "Lower cost when I use care": {
        "look_for": "Gold and Platinum plans usually cost more each "
                    "month but less when you get care.",
        "ask": "What are the deductible, copays, and out-of-pocket "
               "maximum?",
    },
    "Family care": {
        "look_for": "Primary care, pediatric care, and pharmacies "
                    "that work for everyone covered.",
        "ask": "Can everyone in my family find in-network primary "
               "care, and how do family deductibles work?",
    },
    "Senior care": {
        "look_for": "Primary care, specialists, and prescription "
                    "coverage. If you are 65 or older, Medicare may "
                    "apply instead of a marketplace plan.",
        "ask": "Am I eligible for Medicare, and how would this plan "
               "work alongside it?",
    },
    "Child care": {
        "look_for": "Pediatricians, vaccines, and children's dental "
                    "and vision coverage.",
        "ask": "Are well-child visits, vaccines, and children's dental "
               "and vision covered?",
    },
}

NEED_SPECIALTIES = {
    "Hearing care": ["Audiologist"],
    "Dental care": ["Dentist"],
    "Amputee and mobility needs": [
        "Prosthetist",
        "Physical Medicine & Rehabilitation",
    ],
    "Ongoing disease care": [
        "Endocrinology",
        "Cardiovascular Disease",
    ],
    "Family care": ["Family Medicine", "Pediatrics"],
    "Senior care": ["Geriatric Medicine"],
    "Child care": ["Pediatrics"],
}

st.header("What matters most to you in a health plan?", anchor="what-matters")
st.write(
    "Pick everything that applies. We will show what to look for and "
    "what to ask, based on your choices."
)

selected_needs = st.multiselect(
    "I need help with",
    options=list(NEEDS.keys()),
)

for need in selected_needs:
    st.markdown(f"**{need}**")
    st.write(NEEDS[need]["look_for"])
    st.caption(f"Ask the insurer: {NEEDS[need]['ask']}")

specialty_needs = [
    need for need in selected_needs if need in NEED_SPECIALTIES
]

if specialty_needs:
    st.subheader("Providers for your needs")

    with st.form("need_provider_search"):
        need_city = st.text_input("City", value="Boston")
        need_submit = st.form_submit_button("Show providers")

    if need_submit:
        if not need_city.strip():
            st.warning("Enter a city.")
        else:
            need_tables = {}

            with st.spinner("Searching the provider registry..."):
                for need in specialty_needs:
                    for term in NEED_SPECIALTIES[need]:
                        if term in need_tables:
                            continue

                        try:
                            response = search_providers(
                                need_city.strip(), term, "NPI-1"
                            )
                            if "Errors" in response:
                                need_tables[term] = None
                            else:
                                need_tables[term] = format_providers(
                                    response.get("results", [])
                                )
                        except Exception:
                            need_tables[term] = None

            st.session_state["need_provider_results"] = {
                "city": need_city.strip(),
                "tables": need_tables,
            }

    saved_need_results = st.session_state.get("need_provider_results")

    if saved_need_results:
        st.caption(
            f"Up to 15 registry listings per specialty in "
            f"{saved_need_results['city']}. These are a sample, not the "
            "closest or best providers, and the registry does not show "
            "whether a provider accepts your plan."
        )

        for need in specialty_needs:
            st.markdown(f"**{need}**")

            for term in NEED_SPECIALTIES[need]:
                if term not in saved_need_results["tables"]:
                    st.caption(
                        f"Press “Show providers” to search for {term}."
                    )
                    continue

                table = saved_need_results["tables"][term]

                if table is None:
                    st.warning(f"Could not load {term} listings.")
                elif table.empty:
                    st.info(f"No {term} listings found in that city.")
                else:
                    st.write(f"{term} listings")
                    st.dataframe(
                        table[
                            ["Name", "Specialty", "Address", "City", "Phone"]
                        ],
                        hide_index=True,
                        use_container_width=True,
                    )

st.divider()


# ---------------------------------------------------------------------
# Section 2: your plan (picker and details together)
# ---------------------------------------------------------------------

METAL_NOTES = {
    "Bronze": "Usually the lowest monthly premium, with higher costs "
              "when you use care.",
    "Expanded Bronze": "A bronze-tier plan: usually a lower monthly "
                       "premium, with higher costs when you use care.",
    "Silver": "A middle option for monthly premium and cost when you "
              "use care.",
    "Gold": "Usually a higher monthly premium, with lower costs when "
            "you use care.",
    "Platinum": "Usually the highest monthly premium, with the lowest "
                "costs when you use care.",
}

st.header("Your plan", anchor="your-plan")
st.write(
    "Choose a 2026 Massachusetts marketplace plan to see its details "
    "and a link to the insurer's official provider directory."
)

selected_index = st.selectbox(
    "Choose a plan",
    options=plans.index.tolist(),
    format_func=lambda index: (
        f"{plans.at[index, 'insurer']} — "
        f"{plans.at[index, 'plan_name']}"
    ),
    key="plan_picker",
)

plan = plans.loc[selected_index]

with st.container(border=True):
    st.markdown(f"**{plan['plan_name']}**")
    st.write(f"Insurer: {plan['insurer']}")

    col1, col2 = st.columns(2)
    col1.metric("Plan type", str(plan["plan_type"]))
    col2.metric("Metal level", str(plan["metal_level"]))

    metal_note = METAL_NOTES.get(str(plan["metal_level"]))
    if metal_note:
        st.caption(f"General guide: {metal_note}")

    network_name = plan.get("network_name")
    if pd.notna(network_name):
        st.write(f"**Network:** {network_name}")
    else:
        st.write("**Network:** not listed")

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
    "It does not filter the hospitals or providers below by coverage, "
    "and this site does not show prices."
)

st.divider()


# ---------------------------------------------------------------------
# Section 3: find care near you (hospitals, doctors, urgent care)
# ---------------------------------------------------------------------

st.header("Find care near you", anchor="find-care")
st.write(
    "Enter an address to see hospitals, doctors, and urgent care "
    "nearby. Without an address, the Hospitals tab lists hospitals "
    "across Massachusetts."
)

st.caption(
    "Your search address is sent to the U.S. Census Geocoder to "
    "calculate approximate straight-line distances (not driving "
    "distances). You can use a nearby street address instead of your "
    "home."
)

with st.expander("Hospital filters"):
    types = st.multiselect(
        "Hospital type",
        sorted(hospitals["type"].dropna().unique()),
    )
    min_rating = st.slider("Minimum rating", 1, 5, 1)
    emergency_only = st.checkbox("Emergency services only")

with st.form("care_search_form"):
    search_address = st.text_input(
        "Your street address",
        placeholder="123 Main Street, Boston, MA 02101",
    )

    radius = st.slider(
        "Search radius in miles",
        min_value=1,
        max_value=100,
        value=10,
    )

    care_choices = st.multiselect(
        "What are you looking for?",
        ["Hospitals", "Doctors and specialists", "Urgent care"],
        default=["Hospitals"],
    )

    form_col1, form_col2 = st.columns(2)

    provider_city = form_col1.text_input(
        "City for doctor and urgent care search",
        value="Boston",
        help=(
            "Leave blank to search Massachusetts. A city filter excludes "
            "providers in neighboring cities, even if they are nearby."
        ),
    )

    specialty = form_col2.text_input(
        "Specialty (doctors only)",
        value="Family Medicine",
        placeholder="For example: Dermatology",
    )

    submitted = st.form_submit_button("Search")

if submitted:
    # Clear old results so they cannot be mistaken for this search.
    st.session_state.pop("care_search", None)

    wants_doctors = "Doctors and specialists" in care_choices
    wants_urgent = "Urgent care" in care_choices

    if not search_address.strip():
        st.warning("Enter a complete street address.")
    elif not care_choices:
        st.warning("Choose at least one type of care.")
    elif wants_doctors and not specialty.strip():
        st.warning("Enter a specialty for the doctor search.")
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
                origin_lat = match["coordinates"]["y"]
                origin_lon = match["coordinates"]["x"]

                search = {
                    "origin": {
                        "latitude": origin_lat,
                        "longitude": origin_lon,
                        "address": match["matchedAddress"],
                    },
                    "radius": radius,
                    "providers": None,
                    "urgent": None,
                }

                if wants_doctors:
                    with st.spinner("Searching for doctors..."):
                        search["providers"] = run_provider_search(
                            origin_lat,
                            origin_lon,
                            provider_city.strip(),
                            specialty.strip(),
                            "NPI-1",
                            radius,
                        )

                if wants_urgent:
                    with st.spinner("Searching for urgent care..."):
                        search["urgent"] = run_provider_search(
                            origin_lat,
                            origin_lon,
                            provider_city.strip(),
                            "Urgent Care",
                            "NPI-2",
                            radius,
                        )

                st.session_state["care_search"] = search

        except Exception:
            st.error("The search could not finish. Please try again.")

if st.button("Clear search"):
    st.session_state.pop("care_search", None)

search = st.session_state.get("care_search")
origin = search["origin"] if search else None

if origin:
    st.write(f"**Searching near:** {origin['address']}")
    st.write(f"**Radius:** {search['radius']} miles")

hospital_tab, doctor_tab, urgent_tab = st.tabs(
    ["Hospitals", "Doctors and specialists", "Urgent care"]
)

with hospital_tab:
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

    if origin:
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
            filtered["distance_miles"] <= search["radius"]
        ].sort_values("distance_miles")

        filtered["distance_miles"] = filtered["distance_miles"].round(1)

        st.caption(
            "Approximate straight-line distances to hospital ZIP-code "
            "centers, not driving distances. Hospitals without "
            "coordinates are excluded from proximity results."
        )
    else:
        st.caption(
            "No address search is active. Showing Massachusetts "
            "hospitals that match the hospital filters."
        )

    st.subheader(f"{len(filtered)} hospitals match")

    map_data = filtered.dropna(subset=["latitude", "longitude"])

    if map_data.empty:
        st.info(
            "No hospital locations match. Try a wider radius or "
            "fewer filters."
        )
    else:
        st.map(map_data, latitude="latitude", longitude="longitude")

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

with doctor_tab:
    if search is None:
        st.info(
            "Enter an address above, choose “Doctors and specialists,” "
            "and press Search."
        )
    elif search["providers"] is None:
        st.info(
            "You did not choose doctors in your last search. Choose "
            "“Doctors and specialists” above and search again."
        )
    else:
        show_provider_results(search["providers"], search["radius"])

with urgent_tab:
    if search is None:
        st.info(
            "Enter an address above, choose “Urgent care,” "
            "and press Search."
        )
    elif search["urgent"] is None:
        st.info(
            "You did not choose urgent care in your last search. Choose "
            "“Urgent care” above and search again."
        )
    else:
        show_provider_results(search["urgent"], search["radius"])

st.divider()


# ---------------------------------------------------------------------
# Section 4: FAQ
# ---------------------------------------------------------------------

# Each entry is (group, question, answer).
FAQ = [
    # ---- Costs ----
    (
        "Costs",
        "What is a premium, and is it the whole cost?",
        "The premium is the amount you pay each month to have the plan. "
        "It is not the whole cost. You also pay deductibles, copays, "
        "and coinsurance when you use care, so a low premium can mean "
        "higher costs when you need care.",
    ),
    (
        "Costs",
        "What is a deductible?",
        "The amount you pay for covered services before your plan "
        "starts sharing the cost. Some plans cover certain services, "
        "such as some office visits, with a copay before you reach the "
        "deductible. Check the plan's Summary of Benefits and Coverage.",
    ),
    (
        "Costs",
        "What is the difference between a copay and coinsurance?",
        "A copay is a fixed amount, such as a set fee for a visit. "
        "Coinsurance is a percentage of the cost of a covered service "
        "that you pay, usually after you meet your deductible.",
    ),
    (
        "Costs",
        "What is an out-of-pocket maximum?",
        "The most you pay in a plan year for covered, in-network "
        "services. Premiums, services your plan does not cover, and "
        "often out-of-network costs do not count toward it. After you "
        "reach it, the plan generally pays the rest of covered "
        "in-network costs.",
    ),
    (
        "Costs",
        "How do deductibles work for a family?",
        "Many plans have both an individual and a family deductible "
        "and out-of-pocket maximum, and the rules vary. Ask how the "
        "plan counts costs when more than one person is covered.",
    ),
    (
        "Costs",
        "What is an HSA-eligible plan?",
        "Some plans with higher deductibles can be paired with a "
        "health savings account (HSA), a tax-advantaged account for "
        "qualified medical costs. Eligibility rules are set by the IRS, "
        "so ask a tax professional if you are unsure.",
    ),
    # ---- Plan types ----
    (
        "Plan types and metal levels",
        "What do HMO, EPO, PPO, and POS mean?",
        "These describe how a plan's network works. HMO plans usually "
        "require you to use in-network providers and may require a "
        "primary care provider and referrals. EPO plans usually cover "
        "only in-network care (except emergencies) but often do not "
        "require referrals. PPO plans allow out-of-network care at a "
        "higher cost. POS plans mix HMO and PPO features. Details "
        "vary by plan, so check the plan documents.",
    ),
    (
        "Plan types and metal levels",
        "What are Bronze, Silver, Gold, and Platinum?",
        "Metal levels describe how costs are split between you and the "
        "plan, on average. Bronze plans usually have lower premiums "
        "and higher costs when you use care. Platinum plans are the "
        "reverse. The metal level says nothing about the quality of "
        "care, and plans at the same level can have different "
        "networks and benefits.",
    ),
    (
        "Plan types and metal levels",
        "What does “Expanded Bronze” mean?",
        "A bronze-tier plan. Expanded Bronze plans may pay somewhat "
        "more of your costs than a standard Bronze plan. Check the "
        "deductible and out-of-pocket maximum in the plan documents.",
    ),
    (
        "Plan types and metal levels",
        "Are the plans in this app all the plans I can buy?",
        "No. This app lists 48 individual medical plans from 2026 "
        "Massachusetts public data. It is not every option available "
        "in Massachusetts, and it does not show prices.",
    ),
    # ---- Networks ----
    (
        "Networks and getting care",
        "What is the difference between in-network and out-of-network?",
        "In-network providers have an agreement with your plan, so "
        "your costs are usually lower. Out-of-network care may cost "
        "much more or may not be covered at all, depending on your "
        "plan type.",
    ),
    (
        "Networks and getting care",
        "Can I trust an insurer's provider directory?",
        "Directories can be out of date. Before an appointment, call "
        "the provider's office and ask whether they accept your exact "
        "plan, not just the insurer's name. You can also ask your "
        "insurer to confirm.",
    ),
    (
        "Networks and getting care",
        "If a hospital is in my network, are all its doctors?",
        "Not always. Some doctors who work at a hospital, such as "
        "emergency physicians, anesthesiologists, or radiologists, may "
        "be billed separately and may be out of network. Ask about the "
        "specific doctor or group when you can.",
    ),
    (
        "Networks and getting care",
        "What are referrals and prior authorization?",
        "A referral is approval from your primary care provider to "
        "see a specialist. Prior authorization is approval from your "
        "insurer before certain services, tests, or medications. "
        "Without required approval, a plan may refuse to pay.",
    ),
    (
        "Networks and getting care",
        "What if I have an emergency?",
        "Federal rules generally protect your coverage for emergency "
        "care, including at an out-of-network hospital, and you "
        "generally do not need approval first. Go to the nearest "
        "emergency room or call 911. Ask your plan about follow-up "
        "care afterward.",
    ),
    (
        "Networks and getting care",
        "Urgent care or the emergency room?",
        "Urgent care can treat problems that need prompt attention but "
        "are not life-threatening, such as minor injuries or "
        "infections, and is often less expensive. For chest pain, "
        "trouble breathing, severe bleeding, or other emergencies, "
        "call 911 or go to the emergency room.",
    ),
    (
        "Networks and getting care",
        "What is a surprise bill?",
        "A bill from an out-of-network provider you did not choose, "
        "for example at an in-network hospital. The federal No "
        "Surprises Act protects you from many of these bills, but not "
        "all, and ground ambulance rides are generally not covered by "
        "it. If you get a bill that seems wrong, call your insurer.",
    ),
    # ---- Coverage ----
    (
        "What plans cover",
        "What must marketplace plans cover?",
        "Marketplace plans must cover ten categories called essential "
        "health benefits, including emergency services, hospital "
        "care, maternity care, mental health care, prescription "
        "drugs, rehabilitation, lab tests, preventive care, and "
        "pediatric services. Adult dental and vision are usually not "
        "included.",
    ),
    (
        "What plans cover",
        "Are dental, vision, and hearing aids covered?",
        "Often not for adults, or only with limits. Dental and vision "
        "are commonly sold as separate plans, and hearing aid "
        "coverage varies. Ask your insurer exactly what is covered "
        "and what the dollar or frequency limits are.",
    ),
    (
        "What plans cover",
        "Is preventive care free?",
        "Many preventive services, such as certain screenings and "
        "vaccines, are covered with no cost to you when you use an "
        "in-network provider. If a visit turns into diagnosis or "
        "treatment, extra costs can apply.",
    ),
    (
        "What plans cover",
        "How do prescription drug costs work?",
        "Plans keep a list of covered drugs called a formulary, "
        "usually sorted into tiers that cost different amounts. Some "
        "drugs need prior authorization or require trying a cheaper "
        "drug first. Check that your medications are on the list "
        "before you choose a plan.",
    ),
    (
        "What plans cover",
        "Can a plan turn me down for a pre-existing condition?",
        "No. Marketplace plans cannot deny coverage or charge you more "
        "because of your health conditions.",
    ),
    (
        "What plans cover",
        "How do prosthetics and medical equipment coverage work?",
        "Coverage, approved suppliers, and limits on repair or "
        "replacement vary by plan. Ask whether your device is "
        "covered, which suppliers are in network, and whether prior "
        "authorization is needed.",
    ),
    # ---- Enrolling ----
    (
        "Enrolling and getting help",
        "When can I sign up?",
        "You can generally enroll during open enrollment, or after a "
        "qualifying life event such as losing other coverage, moving, "
        "marriage, or having a baby. Check the Massachusetts Health "
        "Connector (mahealthconnector.org) for current dates.",
    ),
    (
        "Enrolling and getting help",
        "Is there help paying for coverage?",
        "Depending on income and other factors, financial help may "
        "lower your premium and your costs when you use care. The "
        "Massachusetts Health Connector (mahealthconnector.org) can "
        "tell you what you qualify for. This site does not show prices.",
    ),
    (
        "Enrolling and getting help",
        "What about Medicare at 65?",
        "People generally become eligible for Medicare at 65, and "
        "Medicare works differently from marketplace plans. "
        "Massachusetts offers free Medicare counseling through the "
        "SHINE program.",
    ),
    (
        "Enrolling and getting help",
        "Is student health insurance the same as a marketplace plan?",
        "No. Many colleges offer their own student health plans, "
        "which have their own networks and rules. Check the school's "
        "plan documents and directory.",
    ),
    # ---- Watch for ----
    (
        "Things to watch for",
        "Is the cheapest premium the cheapest plan?",
        "Not necessarily. Add up the premium plus what you might pay "
        "in deductibles, copays, and coinsurance if you use care. A "
        "plan with a low premium can cost more overall if you need "
        "regular care.",
    ),
    (
        "Things to watch for",
        "Do plans from the same insurer share a network?",
        "Not always. One insurer can have several networks, and "
        "different plans may use different ones. Check the network "
        "name listed for your exact plan.",
    ),
    (
        "Things to watch for",
        "What documents should I ask for?",
        "Ask for the plan's Summary of Benefits and Coverage, a "
        "standard summary of costs and coverage, and for the "
        "formulary if you take medications. These are the best places "
        "to confirm specific costs and limits.",
    ),
    (
        "Things to watch for",
        "What is an Explanation of Benefits (EOB)?",
        "A statement from your insurer showing what a provider "
        "charged and what the plan paid. It is not a bill. Compare it "
        "with any bill you receive before paying.",
    ),
    (
        "Things to watch for",
        "What can this site NOT tell me?",
        "It cannot tell you whether a specific doctor or hospital "
        "accepts your plan, what a plan costs, or whether a provider "
        "is open or taking new patients. Always confirm with the "
        "insurer and the provider.",
    ),
]

st.header("Questions and terms (FAQ)", anchor="faq")
st.caption(
    "Tap a question to open it. This is general information, not "
    "advice about your specific plan."
)

faq_query = st.text_input(
    "Search the FAQ",
    placeholder="For example: deductible, referral, surprise bill",
).strip().lower()

shown_count = 0
current_group = None

for group, question, answer in FAQ:
    if faq_query and faq_query not in f"{question} {answer}".lower():
        continue

    if group != current_group:
        st.markdown(f"##### {group}")
        current_group = group

    with st.expander(question):
        st.write(answer)

    shown_count += 1

if shown_count == 0:
    st.info("No questions match that search. Try a different word.")

st.divider()


# ---------------------------------------------------------------------
# Sources and limits
# ---------------------------------------------------------------------

st.header("Sources and limits", anchor="sources")
st.caption(
    "Hospital source: CMS Hospital General Information. Hospital map "
    "pins use ZIP-code centers, so they are approximate. "
    "Plan source: CMS 2026 Massachusetts State-Based Exchange Public "
    "Use Files. Insurer directory links are manually maintained. "
    "Provider source: CMS NPI Registry. Address matching: U.S. Census "
    "Geocoder."
)
st.caption(
    "This site does not know which providers accept which plans. "
    "Always confirm network status, costs, and coverage with your "
    "insurer and the provider before getting care."
)
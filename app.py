import json
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
import streamlit as st


st.set_page_config(page_title="Plan Places Finder", layout="wide")

# Page styling: smooth scrolling, rounded boxes, sidebar link buttons.
# Keep the theme switch outside the page functions so it stays visible.
dark_mode = st.sidebar.toggle("Dark mode", key="dark_mode")

if dark_mode:
    colors = {
        "background": "#1F1E1D",   # near-black, warm neutral
        "sidebar": "#262624",
        "surface": "#30302E",
        "text": "#F5F4EE",
        "muted": "#B8B5AA",
        "border": "#4A4945",
        "accent": "#D97757",       # Claude-style orange
        "button_text": "#1F1E1D",
        "banner": "#2B2A28",
    }
else:
    colors = {
        "background": "#FAF7F2",
        "sidebar": "#F1EADF",
        "surface": "#FFFDF9",
        "text": "#2F2A26",
        "muted": "#615C54",
        "border": "#B8C2AE",
        "accent": "#A64D35",
        "button_text": "#FFFFFF",
        "banner": "#F3E7D6",
    }

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {colors["background"]};
        color: {colors["text"]};
        color-scheme: {"dark" if dark_mode else "light"};
    }}

    [data-testid="stSidebar"],
    [data-testid="stHeader"] {{
        background-color: {colors["sidebar"]};
    }}

    [data-testid="stMain"] h1,
    [data-testid="stMain"] h2,
    [data-testid="stMain"] h3,
    [data-testid="stMain"] h4,
    [data-testid="stMain"] h5,
    [data-testid="stMarkdownContainer"],
    [data-testid="stWidgetLabel"],
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"],
    [data-testid="stSidebarNav"] a {{
        color: {colors["text"]};
    }}

    [data-testid="stCaptionContainer"] {{
        color: {colors["muted"]};
    }}

    [data-testid="stForm"],
    [data-testid="stExpander"],
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {colors["surface"]};
        border-color: {colors["border"]};
        border-radius: 14px;
    }}

    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-baseweb="select"] > div {{
        background-color: {colors["surface"]};
        color: {colors["text"]};
        border-color: {colors["border"]};
    }}

    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [role="listbox"],
    [role="option"] {{
        background-color: {colors["surface"]};
        color: {colors["text"]};
    }}

    [data-testid="stButton"] button,
    [data-testid="stFormSubmitButton"] button,
    [data-testid="stLinkButton"] a {{
        background-color: {colors["accent"]};
        color: {colors["button_text"]};
        border: 1px solid {colors["accent"]};
        border-radius: 999px;
    }}

    [data-testid="stButton"] button p,
    [data-testid="stFormSubmitButton"] button p,
    [data-testid="stLinkButton"] a p {{
        color: {colors["button_text"]};
    }}

    [data-testid="stButton"] button:hover,
    [data-testid="stFormSubmitButton"] button:hover,
    [data-testid="stLinkButton"] a:hover {{
        filter: brightness(1.1);
    }}

    [data-testid="stMain"] a:not(
        [data-testid="stLinkButton"] a
    ) {{
        color: {colors["accent"]};
    }}

    .hero {{
        background-color: {colors["banner"]};
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 1rem;
    }}

    .hero h1 {{
        color: {colors["accent"]};
        margin: 0 0 0.5rem;
        font-size: 2.4rem;
    }}

    .hero p {{
        color: {colors["text"]};
        margin: 0;
        font-size: 1.1rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)
# ---------------------------------------------------------------------
# Data and helper functions
# ---------------------------------------------------------------------
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
        provider_options = nearby.reset_index(drop=True)

        selected_position = st.selectbox(
            "Choose a provider to plan your next steps",
            options=provider_options.index.tolist(),
            format_func=lambda index: (
                f"{provider_options.at[index, 'Name']} — "
                f"{provider_options.at[index, 'City']} — "
                f"{provider_options.at[index, 'distance_miles']:.1f} miles"
            ),
            key=f"provider_choice_{result['specialty']}",
        )

        selected_provider = provider_options.loc[selected_position]

        if st.button(
            "Use this provider for my checklist",
            key=f"save_provider_{result['specialty']}",
        ):
            st.session_state["checklist_provider"] = (
                selected_provider.to_dict()
            )
            st.session_state["checklist_specialty"] = result["specialty"]

            st.success(
                f"Selected {selected_provider['Name']} for your checklist."
            )
        saved_provider = st.session_state.get("checklist_provider")
            
        if saved_provider is not None:
            with st.container(border=True):
                st.subheader("Your next steps")
                st.write(f"**Provider:** {saved_provider['Name']}")
                st.write(
                    f"**Address:** {saved_provider['Address']}, "
                    f"{saved_provider['City']}, "
                    f"{saved_provider['State']} {saved_provider['ZIP']}"
                )
                st.write(
                    f"**Phone:** {saved_provider.get('Phone') or 'Not listed'}"
                )
                st.write(f"**NPI:** {saved_provider['NPI']}")

                selected_plan_index = st.session_state.get(
                    "selected_plan_index"
                )

                if (
                    selected_plan_index is not None
                    and selected_plan_index in plans.index
                ):
                    checklist_plan = plans.loc[selected_plan_index]

                    st.write(f"**Plan:** {checklist_plan['plan_name']}")
                    st.write(
                        f"**Network:** {checklist_plan['network_name']}"
                    )

                    st.markdown(
                        "1. Search the insurer’s directory using the "
                        "provider’s name or NPI.\n"
                        "2. Call the provider to confirm the exact plan "
                        "and practice address.\n"
                        "3. Ask your insurer about referrals and your "
                        "cost for the visit."
                    )

                    st.write("**What to say when you call:**")
                    st.code(
                        f"Are you in network for "
                        f"{checklist_plan['plan_name']} through "
                        f"{checklist_plan['insurer']}, using the "
                        f"{checklist_plan['network_name']} network, "
                        f"at {saved_provider['Address']}? "
                        "Are you accepting new patients?",
                        language=None,
                        wrap_lines=True,
                    )

                    directory_url = checklist_plan.get("directory_url")

                    if (
                        pd.notna(directory_url)
                        and str(directory_url).startswith(
                            ("https://", "http://")
                        )
                    ):
                        st.link_button(
                            "Check the insurer’s directory",
                            str(directory_url),
                            key=f"checklist_directory_{result['specialty']}",
                        )
                else:
                    st.info(
                        "Choose a plan on the Your plan page, then "
                        "return here to see your personalized call script."
                    )

                st.caption(
                    "Coverage is not verified. This checklist helps "
                    "you confirm it with the insurer and provider."
                )
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



def home_page():
    # ---------------------------------------------------------------------
    # Top of page
    # ---------------------------------------------------------------------

    st.title("Plan Places Finder")
    st.markdown(
        """
        <div class="hero">
        <h1>Plan Places Finder</h1>
        <p>Health insurance is confusing. Tell us what matters to you, look at a plan, and see real hospitals and doctors near you in Massachusetts.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    step_columns = st.columns(3)
    steps = [
        ("1. Tell us what matters", "Pick the kinds of care you need."),
        ("2. Look at a plan", "See its details and the insurer's directory."),
        ("3. Find care near you", "Search hospitals, doctors, and urgent care."),
    ]

    for column, (step_title, step_text) in zip(step_columns, steps):
        with column.container(border=True):
            st.markdown(f"**{step_title}**")
            st.caption(step_text)
    st.info(
        "Hospital and provider results are not matched to your insurance "
        "network. Confirm coverage with your insurer before getting care."
    )



    st.subheader("Where would you like to start?")
    st.page_link(journey_nav, label="Start the guided care search")
    st.page_link(needs_nav, label="Explore your care needs")
    st.page_link(plan_nav, label="Choose an insurance plan")
    st.page_link(care_nav, label="Find nearby care")


def needs_page():
    # ---------------------------------------------------------------------
    # Section 1: what matters to you
    # ---------------------------------------------------------------------

    NEEDS = {
        "Emergency care": {
            "look_for": "Hospitals with emergency services near you. "
                        "The hospital map on the Find care page can filter for these.",
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

    if "needs_picker" not in st.session_state:
        st.session_state["needs_picker"] = st.session_state.get("selected_needs", [])

    def remember_needs():
        st.session_state["selected_needs"] = st.session_state["needs_picker"]

    selected_needs = st.multiselect(
        "I need help with",
        options=list(NEEDS.keys()),
        key="needs_picker",
        on_change=remember_needs,
    )

    if selected_needs:
        need_columns = st.columns(2)

        for position, need in enumerate(selected_needs):
            with need_columns[position % 2].container(border=True):
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

@st.cache_data
def load_benefits():
    return pd.read_csv(
        DATA / "clean" / "benefits.csv",
        dtype=str,
    ).fillna("")

def plan_page():
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

    if "selected_plan_index" not in st.session_state:
        st.session_state["selected_plan_index"] = plans.index[0]
    if "plan_picker" not in st.session_state:
        st.session_state["plan_picker"] = st.session_state["selected_plan_index"]

    def remember_plan():
        st.session_state["selected_plan_index"] = st.session_state["plan_picker"]

    selected_index = st.selectbox(
        "Choose a plan",
        options=plans.index.tolist(),
        format_func=lambda index: (
            f"{plans.at[index, 'insurer']} — "
            f"{plans.at[index, 'plan_name']}"
        ),
        key="plan_picker",
        on_change=remember_plan,
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
    st.subheader("What does this plan cover?")
    st.write(
        "Look up a service in the official 2026 Massachusetts "
        "plan benefits data."
    )

    benefits = load_benefits()

    plan_benefits = benefits[
        benefits["plan_id"] == str(plan["plan_id"])
    ]

    if plan_benefits.empty:
        st.info("No benefit records are available for this plan.")
    else:
        variants = sorted(
            plan_benefits["variant_id"].unique().tolist()
        )

        variant = st.selectbox(
            "Choose your exact plan variant",
            options=["I'm not sure"] + variants,
            key=f"benefit_variant_{plan['plan_id']}",
            help=(
                "The full plan ID includes a suffix such as -01. "
                "Check your enrollment documents or ask your insurer. "
                "Do not guess based on the insurer name."
            ),
        )

        if variant == "I'm not sure":
            st.session_state.pop("selected_benefit", None)
            st.info(
                "Select the full plan ID from your enrollment documents "
                "to see variant-specific benefits. Your base plan ID is "
                f"{plan['plan_id']}."
            )
        else:
            variant_benefits = plan_benefits[
                plan_benefits["variant_id"] == variant
            ]

            service = st.selectbox(
                "Which service do you want to understand?",
                options=sorted(
                    variant_benefits["benefit_name"].unique().tolist()
                ),
                key=f"benefit_service_{variant}",
            )

            records = variant_benefits[
                variant_benefits["benefit_name"] == service
            ]
            st.session_state["selected_benefit"] = {
                "plan_id": str(plan["plan_id"]),
                "variant_id": variant,
                "service": service,
            }

            st.page_link(
                care_nav,
                label="Find care and view this benefit",
            )

            coverage_values = set(
                records["covered"].str.strip().str.lower()
            )

            with st.container(border=True):
                st.markdown(f"### {service}")

                if coverage_values == {"yes"}:
                    st.success(
                        "Listed as covered in this plan variant’s "
                        "2026 benefits data."
                    )
                elif coverage_values == {"no"}:
                    st.warning(
                        "Listed as not covered in this plan variant’s "
                        "2026 benefits data."
                    )
                else:
                    st.info(
                        "The records do not give one clear coverage answer."
                    )

                # Show all distinct notes rather than silently picking
                # the first row when multiple records exist.
                for column, label in [
                    ("explanation", "Conditions and explanation"),
                    ("exclusions", "Exclusions"),
                ]:
                    notes = [
                        value
                        for value in records[column].str.strip().unique()
                        if value
                    ]

                    if notes:
                        st.markdown(f"**{label}**")
                        for note in notes:
                            st.write(note)
                    else:
                        st.caption(
                            f"{label}: not specified in this dataset."
                        )

                st.markdown("**Service limits**")

                limit_records = records[
                    [
                        "has_quantity_limit",
                        "limit_quantity",
                        "limit_unit",
                    ]
                ].drop_duplicates()

                for _, limit in limit_records.iterrows():
                    flag = limit["has_quantity_limit"].strip().lower()
                    amount = " ".join(
                        value.strip()
                        for value in [
                            limit["limit_quantity"],
                            limit["limit_unit"],
                        ]
                        if value.strip()
                    )

                    if flag == "yes":
                        st.write(
                            f"Quantity limit: {amount}"
                            if amount
                            else "A quantity limit is listed, but its "
                                 "amount is not specified."
                        )
                    elif flag == "no":
                        st.write(
                            "The dataset lists no quantity limit. "
                            "Other conditions may still apply."
                        )
                    else:
                        st.write("Quantity-limit status is not specified.")
                        if amount:
                            st.write(f"Additional limit detail: {amount}")

                st.markdown("**What this does not answer**")
                st.write(
                    "This file does not provide copay or coinsurance "
                    "amounts. It also does not establish whether your "
                    "chosen provider is in network, whether a referral "
                    "or prior authorization is required, or whether "
                    "your particular service will be approved."
                )

                st.caption(
                    f"Plan variant: {variant} · Benefit year: 2026. "
                    "Blank fields mean information was not supplied, "
                    "not that restrictions do not exist."
                )

                st.link_button(
                    "View the CMS source",
                    "https://www.cms.gov/marketplace/resources/data/"
                    "state-based-public-use-files",
                    key=f"benefit_source_{variant}",
                )

    st.divider()

def show_selected_benefit():
    selection = st.session_state.get("selected_benefit")
    plan_index = st.session_state.get("selected_plan_index")

    if plan_index is None or plan_index not in plans.index:
        st.info("Choose a plan to see its service coverage here.")
        st.page_link(plan_nav, label="Choose a plan")
        return

    current_plan = plans.loc[plan_index]

    # Prevent an old plan's benefit from appearing under a new plan.
    if (
        selection is None
        or selection["plan_id"] != str(current_plan["plan_id"])
    ):
        st.info(
            "On Your plan, choose your exact variant and a service "
            "to bring its coverage details here."
        )
        st.page_link(plan_nav, label="Choose a benefit to check")
        return

    benefits = load_benefits()

    records = benefits[
        (benefits["plan_id"] == selection["plan_id"])
        & (benefits["variant_id"] == selection["variant_id"])
        & (benefits["benefit_name"] == selection["service"])
    ]

    with st.container(border=True):
        st.subheader("Your selected service benefit")
        st.write(f"**Service:** {selection['service']}")
        st.write(f"**Plan:** {current_plan['plan_name']}")
        st.caption(f"Exact variant: {selection['variant_id']}")

        if records.empty:
            st.info("No benefit record was found for this selection.")
            return

        statuses = set(
            records["covered"].str.strip().str.lower()
        )

        if statuses == {"yes"}:
            st.success("Listed as covered in the 2026 benefits data.")
        elif statuses == {"no"}:
            st.warning("Listed as not covered in the 2026 benefits data.")
        else:
            st.info("Coverage status is unclear in these records.")

        with st.expander("Read conditions, exclusions, and limits"):
            for column, label in [
                ("explanation", "Conditions"),
                ("exclusions", "Exclusions"),
            ]:
                notes = [
                    note
                    for note in records[column].str.strip().unique()
                    if note
                ]

                st.markdown(f"**{label}**")
                if notes:
                    for note in notes:
                        st.write(note)
                else:
                    st.write("Not specified in this dataset.")

            st.markdown("**Quantity limits from the source**")
            st.dataframe(
                records[
                    [
                        "has_quantity_limit",
                        "limit_quantity",
                        "limit_unit",
                    ]
                ]
                .drop_duplicates()
                .replace("", "Not specified")
                .rename(columns={
                    "has_quantity_limit": "Limit listed?",
                    "limit_quantity": "Quantity",
                    "limit_unit": "Unit",
                }),
                hide_index=True,
                use_container_width=True,
            )

        st.caption(
            "Service coverage does not establish that any provider "
            "below accepts this plan. Copays, referral requirements, "
            "and prior authorization are not established here."
        )

        st.page_link(plan_nav, label="Change service or plan variant")
def care_page():
    # ---------------------------------------------------------------------
    # Section 3: find care near you (hospitals, doctors, urgent care)
    # ---------------------------------------------------------------------

    st.header("Find care near you", anchor="find-care")
    show_selected_benefit()
    st.info("Results are not matched to your insurance network. Confirm coverage with your insurer.")
    selected_plan_index = st.session_state.get("selected_plan_index")
    if selected_plan_index is not None and selected_plan_index in plans.index:
        chosen_plan = plans.loc[selected_plan_index]
        st.caption(f"Selected plan: {chosen_plan['plan_name']}")
        chosen_url = chosen_plan.get("directory_url")
        if pd.notna(chosen_url) and str(chosen_url).startswith(("https://", "http://")):
            st.link_button("Check your plan’s provider directory", str(chosen_url))
    else:
        st.page_link(plan_nav, label="Choose your insurance plan")
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
            filtered[display_columns].rename(columns={
    "name": "Hospital",
    "city": "City",
    "type": "Hospital type",
    "rating": "Rating",
    "emergency": "Emergency services",
    "distance_miles": "Approx. distance (miles)",
}),
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


def faq_page():
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


def sources_page():
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

def guided_zip_map(providers, search_key):
    """Filter only retrieved providers; markers summarize each ZIP group."""
    import hashlib
    import pydeck as pdk

    providers = providers.copy()
    providers['ZIP'] = providers['ZIP'].fillna('').astype(str).str.strip().str[:5]
    stamp = hashlib.sha256((search_key + providers.to_json()).encode()).hexdigest()[:16]
    map_key = f'care_zip_map_{stamp}'
    filter_key = f'care_zip_filter_{stamp}'
    options = ['All ZIP codes'] + sorted(z for z in providers['ZIP'].unique() if len(z) == 5 and z.isdigit())
    st.session_state.setdefault(filter_key, 'All ZIP codes')

    def use_map_selection():
        event = st.session_state.get(map_key, {})
        selected = event.get('selection', {}).get('objects', {}).get('provider-zips', [])
        if selected and str(selected[0].get('ZIP')) in options:
            st.session_state[filter_key] = str(selected[0]['ZIP'])

    st.subheader('Explore matches by ZIP code')
    st.caption('Select a dot to show the retrieved providers in that ZIP code. Dots are placed at the average location of matched providers—not ZIP boundaries or exact clinic locations. Counts include only results from this search.')
    st.selectbox('Show providers in ZIP code', options, key=filter_key, help='Keyboard-accessible alternative to clicking the map. Choose All ZIP codes to clear the filter.')
    if {'latitude', 'longitude'}.issubset(providers.columns):
        mapped = providers[providers['ZIP'].isin(options[1:])].dropna(subset=['latitude', 'longitude'])
        if not mapped.empty:
            groups = mapped.groupby('ZIP', as_index=False).agg(latitude=('latitude', 'mean'), longitude=('longitude', 'mean'), count=('Name', 'size'))
            chosen_zip = st.session_state[filter_key]
            groups['color'] = groups['ZIP'].map(lambda z: [31, 111, 95, 230] if z == chosen_zip else [166, 77, 53, 210])
            layer = pdk.Layer('ScatterplotLayer', id='provider-zips', data=groups,
                get_position='[longitude, latitude]', get_fill_color='color',
                get_radius=180, radius_min_pixels=12, radius_max_pixels=28,
                pickable=True, auto_highlight=True)
            span = max(float(groups.latitude.max() - groups.latitude.min()), float(groups.longitude.max() - groups.longitude.min()))
            zoom = 11 if span < .1 else 9 if span < .5 else 7
            deck = pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=float(groups.latitude.mean()), longitude=float(groups.longitude.mean()), zoom=zoom), map_style=None,
                tooltip={'text': 'ZIP {ZIP}\n{count} retrieved provider(s)\nSelect to filter the list'})
            st.pydeck_chart(deck, key=map_key, on_select=use_map_selection, selection_mode='single-object', height=350)
        else:
            st.info('These results do not have valid ZIP locations to map. Use the provider list below.')
    active = st.session_state[filter_key]
    visible = providers if active == 'All ZIP codes' else providers[providers['ZIP'] == active]
    st.write(f"**{len(visible)} provider(s)** · {active}")
    if active != 'All ZIP codes':
        st.dataframe(visible[['Name', 'Address', 'City', 'ZIP', 'Phone']], hide_index=True)
    return visible.reset_index(drop=True)


def care_guide_page():
    paths = {
        "Primary care / general health": (["Family Medicine", "Internal Medicine"], ["Primary Care Visit to Treat an Injury or Illness"]),
        "Hearing": (["Audiologist"], ["Hearing Aids", "Specialist Visit"]),
        "Mental health": (["Psychologist", "Psychiatry"], ["Mental/Behavioral Health Outpatient Services"]),
        "Skin": (["Dermatology"], ["Specialist Visit"]),
        "Eye care": (["Optometrist", "Ophthalmology"], ["Routine Eye Exam (Adult)", "Specialist Visit"]),
        "Dental care": (["Dentist"], ["Routine Dental Services (Adult)", "Basic Dental Care - Adult"]),
        "Movement / rehabilitation": (["Physical Therapist", "Physical Medicine & Rehabilitation"], ["Rehabilitative Occupational and Rehabilitative Physical Therapy"]),
        "Children’s care": (["Pediatrics"], ["Well Baby Visits and Care", "Primary Care Visit to Treat an Injury or Illness"]),
        "Urgent care": (["Urgent Care"], ["Urgent Care Centers or Facilities"]),
        "Another specialty": (["Neurology", "Cardiovascular Disease", "Endocrinology", "Obstetrics & Gynecology", "Enter a specialty"], []),
    }
    state = st.session_state.setdefault("care_wizard", {"step": 0})
    labels = ["Care need", "Your plan", "Location", "Choose a provider", "Your next steps"]
    step = state['step']
    st.title("Your care guide")
    st.caption(f"Step {step + 1} of 5 · {labels[step]}")
    st.progress((step + 1) / 5)
    st.caption("For an emergency, call 911. This guide does not diagnose symptoms or verify insurance acceptance.")

    def go(number):
        state['step'] = number
        st.rerun()

    def back(number):
        if st.button("← Back", key=f"wizard_back_{step}"):
            go(number)

    if step == 0:
        st.header("What kind of care are you looking for?")
        st.write("Choose a care area. We will show only related provider specialties.")
        area = st.selectbox("Care area", list(paths), index=list(paths).index(state.get('area', 'Primary care / general health')), key="w_area")
        choices = paths[area][0]
        previous = state.get('specialty', choices[0])
        specialty = st.selectbox("Provider specialty", choices, index=choices.index(previous) if previous in choices else 0, key=f"w_specialty_{area}")
        if specialty == "Enter a specialty":
            specialty = st.text_input("Exact provider specialty", value=state.get('custom_specialty', ''), placeholder="For example: Rheumatology").strip()
            st.caption("Custom searches use your specialty as the care need. We do not infer it from symptoms or automatically assign benefit categories.")
        st.caption("These options organize a directory search; they are not a medical recommendation.")
        if st.button("Continue to your plan →", type="primary"):
            if not specialty:
                st.warning("Enter a specialty before continuing.")
            else:
                if (area, specialty) != (state.get('area'), state.get('specialty')):
                    for key in ['search', 'provider', 'topics']:
                        state.pop(key, None)
                state.update(area=area, specialty=specialty, custom_specialty=specialty if area == 'Another specialty' else '')
                go(1)
        return

    benefits = load_benefits()
    if step == 1:
        st.header("What does your plan say about this care?")
        st.caption(f"Your search: {state['specialty']} · {state['area']}")
        ids = ["Not listed / I do not know"] + plans['plan_id'].tolist()
        saved_id = state.get('plan_id', ids[0])
        plan_id = st.selectbox("Your 2026 Massachusetts marketplace plan", ids, index=ids.index(saved_id) if saved_id in ids else 0, format_func=lambda v: v if v == ids[0] else f"{plans.loc[plans.plan_id == v].iloc[0]['insurer']} — {plans.loc[plans.plan_id == v].iloc[0]['plan_name']}")
        st.caption("Employer, student and other plans may not be listed. Choose ‘Not listed’ rather than a similar plan; you can still find care.")
        available = benefits[benefits.plan_id == plan_id]
        variants = ["I'm not sure"] + sorted(available.variant_id.unique())
        prior = state.get('variant', variants[0]) if plan_id == state.get('plan_id') else variants[0]
        variant = st.selectbox("Exact plan variant", variants, index=variants.index(prior) if prior in variants else 0, key=f"w_variant_{plan_id}", disabled=available.empty)
        st.caption("A variant is a version of a plan with its own benefit rules. Find the full ID, including its suffix, in enrollment documents. Do not guess.")
        rows = available[available.variant_id == variant]
        options = sorted(rows.benefit_name.unique())
        defaults = state.get('topics', paths[state['area']][1]) if plan_id == state.get('plan_id') and variant == state.get('variant') else paths[state['area']][1]
        topics = st.multiselect("Related services to check", options, default=[t for t in defaults if t in options], key=f"w_topics_{plan_id}_{variant}_{state['area']}", disabled=rows.empty)
        st.caption("Benefit categories describe services, not individual providers. A general specialist benefit does not prove coverage for your specific treatment.")
        findings = []
        if rows.empty:
            st.info("Benefits remain unknown until your exact plan variant is identified.")
            findings.append("Exact plan variant not identified; benefits unconfirmed.")
        elif not topics:
            st.info("Choose a service to see its benefit information, or continue with coverage unconfirmed.")
            findings.append("No service benefit selected; coverage unconfirmed.")
        for topic in topics:
            records = rows[rows.benefit_name == topic]
            statuses = set(records.covered.str.lower().str.strip())
            status = 'listed as covered' if statuses == {'yes'} else 'listed as not covered' if statuses == {'no'} else 'unclear in source records'
            findings.append(f"{topic}: {status} (2026, {variant}).")
            st.write(f"**{topic}:** {status}")
            with st.expander(f"Read conditions and limits: {topic}"):
                for column, title, definition in [
                    ('explanation', 'Explanation', 'Details about how the benefit applies, including conditions you may need to meet.'),
                    ('exclusions', 'Exclusions', 'Services or circumstances the benefit does not cover. A covered benefit can still have exclusions.'),
                ]:
                    st.markdown(f"**{title}**")
                    st.caption(definition)
                    notes = [str(x).strip() for x in records[column].unique() if str(x).strip()]
                    if not notes:
                        st.write("Not specified in this dataset. This does not mean there are no restrictions.")
                    for note in notes:
                        st.write(note)
                        findings.append(f"{topic} — {title}: {note}")
                st.markdown("**Quantity limits**")
                st.caption("A cap on how often or how much of a service is covered, such as visits per year.")
                for _, r in records[['has_quantity_limit', 'limit_quantity', 'limit_unit']].drop_duplicates().iterrows():
                    note = f"{topic}: quantity limit listed: {r['has_quantity_limit'] or 'not specified'}; {r['limit_quantity']} {r['limit_unit']}".strip()
                    st.write(note)
                    findings.append(note)
        st.link_button("View the official benefits data source", "https://www.cms.gov/marketplace/resources/data/state-based-public-use-files")
        back(0)
        if st.button("Continue to location →", type="primary"):
            state.update(plan_id=plan_id, variant=variant, topics=topics, findings=findings)
            if plan_id in plans.plan_id.values:
                st.session_state['selected_plan_index'] = plans[plans.plan_id == plan_id].index[0]
            else:
                st.session_state.pop('selected_plan_index', None)
            go(2)
        return

    if step == 2:
        st.header("Where would you like to find care?")
        st.write(f"Looking for **{state['specialty']}** in Massachusetts.")
        with st.form('wizard_location'):
            street = st.text_input("Street address", value=state.get('street', ''), placeholder="123 Main Street")
            city = st.text_input("City or town", value=state.get('city', ''), placeholder="Boston")
            region = st.selectbox("State", ["Massachusetts (MA)"])
            zip_code = st.text_input("ZIP code", value=state.get('zip', ''), max_chars=5, placeholder="02118")
            radius = st.slider("Maximum distance in miles", 1, 100, state.get('radius', 10))
            scope = st.radio("Provider search area", ['This city or town', 'All Massachusetts'], index=state.get('scope', 0), help="City searches exclude nearby towns. Statewide searches still return only up to 15 registry listings, not all providers.")
            submitted = st.form_submit_button("Search for providers →", type="primary")
        st.caption("Your address is sent to the Census Geocoder. You may use a nearby street address. Distances are approximate straight-line distances, not driving distances.")
        back(1)
        if submitted:
            state.update(street=street.strip(), city=city.strip(), zip=zip_code.strip(), radius=radius, scope=0 if scope == 'This city or town' else 1)
            state.pop('search', None)
            state.pop('provider', None)
            if not street.strip() or not city.strip() or len(zip_code.strip()) != 5 or not zip_code.strip().isascii() or not zip_code.strip().isdigit():
                st.error("Enter a street, city or town, and a five-digit ZIP code.")
                return
            try:
                with st.spinner("Finding the address and provider locations…"):
                    matches = geocode_address(f"{street.strip()}, {city.strip()}, MA {zip_code.strip()}")
                    if len(matches) != 1:
                        st.error("We could not match one address. Check all four address fields and try again.")
                        return
                    origin = matches[0]
                    if origin.get('addressComponents', {}).get('state', 'MA') != 'MA':
                        st.error("The matched address is outside Massachusetts. Check the address.")
                        return
                    result = run_provider_search(origin['coordinates']['y'], origin['coordinates']['x'], city.strip() if state['scope'] == 0 else '', state['specialty'], 'NPI-2' if state['specialty'] == 'Urgent Care' else 'NPI-1', radius)
                    if result.get('failed'):
                        st.error("The registry is unavailable. Please try again.")
                        return
                    state['search'] = {'result': result, 'address': origin['matchedAddress'], 'radius': radius}
            except Exception:
                st.error("The address or provider lookup failed. Please try again.")
                return
            go(3)
        return

    search = state.get('search')
    if not search:
        st.info("Search for providers before continuing.")
        if st.button("Go to location"):
            go(2)
        return
    result = search['result']
    nearby = result['nearby'].reset_index(drop=True)
    if step == 3:
        st.header("Choose a provider to check")
        st.write(f"**{state['specialty']}** near {search['address']}")
        st.caption(f"{result['searched_count']} registry listings checked; {len(nearby)} located within {search['radius']} miles. These are not necessarily the closest providers overall. Coverage is not verified.")
        if not result['unavailable'].empty:
            with st.expander('Providers whose distance could not be determined'):
                st.dataframe(result['unavailable'], hide_index=True)
        back(2)
        if nearby.empty:
            st.info("No located matches within this radius. Go back to change the distance or search area. This does not mean no providers exist nearby.")
            return
        nearby = guided_zip_map(nearby, f"{search['address']}|{search['radius']}|{state['specialty']}")
        if nearby.empty:
            st.info("No providers in the selected ZIP. Choose All ZIP codes to reset.")
            return
        position = st.selectbox("Provider and practice address", list(range(len(nearby))), format_func=lambda i: f"{nearby.iloc[i]['Name']} — {nearby.iloc[i]['Address']} ({nearby.iloc[i]['distance_miles']} miles)")
        provider = nearby.iloc[position]
        with st.container(border=True):
            st.subheader(str(provider['Name']))
            st.write(f"{provider['Address']}, {provider['City']}, {provider['State']} {provider['ZIP']}")
            st.write(f"Phone: {provider['Phone'] or 'Not listed'}")
            st.caption("Primary practice address from the NPI Registry. Additional locations and appointment availability may differ.")
        with st.expander("Compare all retrieved matches"):
            st.dataframe(nearby[['Name', 'Address', 'City', 'Phone', 'distance_miles']].rename(columns={'distance_miles': 'Approx. miles'}), hide_index=True)
        if st.button("Build my next steps →", type='primary'):
            state['provider'] = provider.to_dict()
            go(4)
        return

    provider = state.get('provider')
    if not provider:
        go(3)
    known = state['plan_id'] in plans.plan_id.values
    plan = plans[plans.plan_id == state['plan_id']].iloc[0] if known else {'plan_name': 'Not identified', 'insurer': 'Not identified', 'network_name': 'Not identified', 'directory_url': ''}
    st.header("Your next steps")
    st.write(f"**Your care search:** {state['specialty']}")
    with st.container(border=True):
        st.subheader(provider['Name'])
        st.write(f"{provider['Address']}, {provider['City']}, {provider['State']} {provider['ZIP']}")
        st.write(f"**Phone:** {provider['Phone'] or 'Not listed'} · **NPI:** {provider['NPI']}")
        st.write(f"**Plan:** {plan['plan_name']} · **Network:** {plan['network_name']}")
        st.caption(f"Variant: {state['variant']}")
    findings = state.get('findings', ['Benefits unconfirmed.'])
    with st.expander("What the benefit records say"):
        for finding in findings:
            st.write(finding)
    st.write("**Still to confirm:** this provider’s network participation, your specific service’s cost and approval requirements, and appointment availability.")
    if known:
        script = f"I have {plan['plan_name']} from {plan['insurer']}, network {plan['network_name']}, variant {state['variant']}. Is {provider['Name']} (NPI {provider['NPI']}) in network at {provider['Address']}, {provider['City']}? I am seeking {state['specialty']} care. What costs, referrals or prior authorization apply to my specific service?"
    else:
        script = f"Please help identify my exact plan and network. Is {provider['Name']} (NPI {provider['NPI']}) in network at {provider['Address']}, {provider['City']} for the service I need? What costs or approvals apply?"
    st.markdown("**1. Ask your insurer**")
    st.write(script)
    office = "Are you accepting new patients for this service at this location? Please confirm participation in my exact plan and network."
    st.markdown("**2. Ask the provider’s office**")
    st.write(office)
    url = plan.get('directory_url', '')
    if pd.notna(url) and str(url).startswith(('https://','http://')):
        st.link_button("Open my insurer’s directory", str(url))
    text = '\n'.join([f"Care: {state['specialty']}", f"Plan: {plan['plan_name']}", f"Variant: {state['variant']}", f"Provider: {provider['Name']}", f"Address: {provider['Address']}, {provider['City']}, {provider['State']} {provider['ZIP']}", f"Phone: {provider['Phone'] or 'Not listed'}", f"NPI: {provider['NPI']}", '', 'BENEFITS DATA', *findings, '', 'ASK YOUR INSURER', script, '', 'ASK THE OFFICE', office, '', f"Directory: {url}", 'Sources: CMS 2026 MA SBE benefits; CMS NPI Registry; Census Geocoder.', 'https://www.cms.gov/marketplace/resources/data/state-based-public-use-files', 'https://npiregistry.cms.hhs.gov/', 'Coverage, cost and availability remain unverified.'])
    st.download_button("Download my next steps", text, 'my-care-next-steps.txt', 'text/plain')
    back(3)
    if st.button("Change care need or plan"):
        go(0)


journey_nav = st.Page(care_guide_page, title="Find care: start here", default=True)
home_nav = st.Page(home_page, title="About this app", url_path="about")
needs_nav = st.Page(needs_page, title="Other care needs", url_path="needs")
plan_nav = st.Page(plan_page, title="Browse plans and benefits", url_path="plan")
care_nav = st.Page(care_page, title="Browse nearby care", url_path="care")
faq_nav = st.Page(faq_page, title="Questions and terms", url_path="faq")
sources_nav = st.Page(sources_page, title="Sources and limits", url_path="sources")
navigation = st.navigation({"Guided care": [journey_nav], "Explore": [needs_nav, plan_nav, care_nav], "Help": [home_nav, faq_nav, sources_nav]})
navigation.run()

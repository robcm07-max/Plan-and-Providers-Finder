"""Presentation for the care guide. Data and search logic stay in app.py."""
from html import escape
import streamlit as st


def safe(value):
    return escape(str(value))


def theme(dark=False):
    palette = (
        ['#19231f', '#202d27', '#26362e', '#edf2eb', '#bcc9c0', '#42574a', '#a7d4bf', '#183d30', '#efad8f', '#39342a']
        if dark else
        ['#f8f7f2', '#e9eee7', '#fffefa', '#25372f', '#5e7067', '#dce3db', '#23634f', '#dcebe1', '#bb4b30', '#f3eadb']
    )
    names = ['bg','sidebar','surface','ink','muted','line','green','selected','orange','notice']
    variables = ';'.join(f'--{k}:{v}' for k, v in zip(names, palette))
    st.markdown('<style>:root{' + variables + ';}</style>', unsafe_allow_html=True)
    st.markdown('''<style>
    .stApp { background:var(--bg); color:var(--ink); }
    [data-testid="stHeader"] { background:transparent; }
    [data-testid="stMainBlockContainer"] { max-width:1120px; padding:3rem 3rem 5rem; }
    [data-testid="stSidebar"] { background:var(--sidebar); border-right:1px solid var(--line); }
    [data-testid="stSidebarContent"] { padding-top:1.5rem; }
    [data-testid="stSidebar"] h2 { font-family:Georgia,serif; }
    [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"],
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
    [data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3 { color:var(--ink); }
    [data-testid="stMain"] h2, [data-testid="stMain"] h3 { font-family:Georgia,'Times New Roman',serif; letter-spacing:-.025em; }
    [data-testid="stCaptionContainer"] { color:var(--muted); font-size:.87rem; line-height:1.6; }
    [data-testid="stMain"] p { line-height:1.65; }
    [data-testid="stSidebarNav"] { display:none; }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a { padding:.7rem .8rem; border-radius:12px; color:var(--muted); }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover { background:var(--surface); color:var(--green); }
    .brand { display:flex; align-items:center; gap:12px; margin:0 0 24px; }
    .brand-mark { display:grid; place-items:center; width:43px; height:43px; border-radius:13px; background:#23634f; color:white; font-size:28px; }
    .brand-title { font:700 25px/1.1 Georgia,serif; color:var(--ink); }
    .brand-sub { font:700 11px/2 sans-serif; letter-spacing:3px; color:var(--muted); }
    .nav-label { margin:23px 12px 8px; color:var(--muted); font-size:11px; font-weight:700; letter-spacing:1.8px; }
    .eyebrow { color:var(--orange); text-transform:uppercase; font-size:12px; font-weight:750; letter-spacing:2px; margin:0 0 12px; }
    .stApp h1.page-title, .stApp h1.page-title * { font-family:Georgia,'Times New Roman',serif!important; }
    .stApp h1.page-title { color:var(--ink); font-size:clamp(36px,4.6vw,64px)!important; line-height:1.04!important; font-weight:700; letter-spacing:-2.4px; max-width:870px; margin:0 0 24px; text-wrap:balance; }
    [data-testid="stMarkdownContainer"] h1.page-title { font-family:Georgia,'Times New Roman',serif!important; font-size:clamp(36px,4.6vw,64px)!important; line-height:1.04!important; font-weight:700; padding:0; margin:0 0 24px; }
    .page-intro { color:var(--muted); font-size:17px; line-height:1.7; max-width:850px; margin:0 0 25px; }
    [data-testid="stMainBlockContainer"]:has(.welcome) { max-width:none; padding:6px; }
    .step-line { display:flex; justify-content:space-between; color:var(--muted); font-size:11px; font-weight:700; letter-spacing:1.5px; margin-bottom:9px; }
    .step-line span:last-child { color:var(--green); letter-spacing:.3px; }
    .step-track { height:4px; background:var(--line); border-radius:4px; margin-bottom:46px; }
    .step-track div { background:var(--green); height:100%; border-radius:4px; }
    .care-notice { background:var(--notice); color:var(--ink); padding:15px 19px; border-left:3px solid var(--orange); border-radius:10px; font-size:13px; line-height:1.6; margin:3px 0 22px; }
    .selection-strip { padding:20px 24px; border:1px solid var(--line); background:var(--surface); border-radius:14px; margin:12px 0; color:var(--ink); }
    .selection-strip small { color:var(--muted); text-transform:uppercase; letter-spacing:1.5px; font-size:10px; display:block; margin-bottom:5px; }
    .selection-strip p { margin:6px 0 0; color:var(--muted); }
    .plan-summary { background:var(--selected); border-radius:12px; padding:23px; margin:14px 0 23px; }
    .plan-summary h3 { margin:10px 0 5px; font-size:25px; }
    .plan-summary p { margin:4px 0; color:var(--muted); }
    .pill { display:inline-block; background:var(--surface); border:1px solid var(--line); padding:5px 11px; border-radius:100px; font-size:11px; color:var(--green); }
    .plan-meta { display:flex; flex-wrap:wrap; gap:24px; border-top:1px solid var(--line); padding-top:15px; margin-top:15px; }
    .plan-meta small { display:block; color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:1px; }
    [data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"] { border-radius:16px; border-color:var(--line); background:var(--surface); }
    [data-testid="stForm"] { padding:26px; }
    [data-testid="stExpander"] { border-color:var(--line); border-radius:12px; background:var(--surface); }
    [data-testid="stWidgetLabel"] p { font-size:12px; font-weight:650; }
    [data-baseweb="select"] > div, [data-testid="stTextInput"] input,
    [data-testid="stTextInput"] [data-baseweb="input"] { background:var(--bg); color:var(--ink); border-color:var(--line); border-radius:9px; min-height:45px; }
    [data-baseweb="menu"], [data-baseweb="popover"], [role="listbox"], [role="option"] { background:var(--surface); color:var(--ink); }
    [data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button,
    [data-testid="stDownloadButton"] button, [data-testid="stLinkButton"] a { min-height:46px; border-radius:10px; padding:10px 18px; font-weight:650; background:var(--surface); color:var(--green); border:1px solid var(--line); }
    [data-testid="stButton"] button p, [data-testid="stFormSubmitButton"] button p,
    [data-testid="stDownloadButton"] button p, [data-testid="stLinkButton"] a p { color:inherit; }
    button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] { background:var(--green); color:#fff; border-color:var(--green); }
    .st-key-wizard-next button, .st-key-wizard-next button *,
    .st-key-wizard-next [data-testid="stBaseButton-primary"],
    .st-key-wizard-next [data-testid="stBaseButton-primary"] * { color:#fff!important; -webkit-text-fill-color:#fff!important; }
    button:hover { border-color:var(--green)!important; }
    button:focus-visible, a:focus-visible, input:focus-visible, [role="combobox"]:focus-visible { outline:3px solid var(--orange)!important; outline-offset:3px; }
    [class*="st-key-care_card_"] button { width:100%; min-height:118px; height:100%; align-items:flex-start; justify-content:flex-start; padding:19px 16px; text-align:left; border-radius:14px; }
    [class*="st-key-care_card_"] button p { white-space:pre-line; line-height:1.5; font-size:12px; }
    [class*="st-key-care_card_"] button strong { display:block; font-size:14px; margin-bottom:5px; }
    [class*="st-key-care_card_"] button[kind="primary"] { background:var(--selected); color:var(--ink); border:1.5px solid var(--green); }
    [class*="st-key-provider_card_"] button { width:100%; min-height:135px; text-align:left; justify-content:flex-start; padding:20px; border-radius:14px; }
    [class*="st-key-provider_card_"] button p { white-space:pre-line; line-height:1.6; font-size:12px; }
    [class*="st-key-provider_card_"] button strong { font-size:15px; }
    [class*="st-key-provider_card_"] button[kind="primary"] { background:var(--selected); color:var(--ink); border-color:var(--green); }
    .chosen-provider { background:var(--selected); border:1px solid var(--line); border-radius:18px; padding:30px; margin-bottom:18px; }
    .chosen-provider h2 { font:700 32px/1.2 Georgia,serif; margin:10px 0 16px; }
    .chosen-provider p { color:var(--muted); margin:4px 0; }
    .action-heading { display:flex; align-items:center; gap:15px; margin:4px 0 12px; font:700 26px/1.2 Georgia,serif; }
    .action-number { display:grid; place-items:center; min-width:34px; height:34px; border-radius:50%; background:var(--green); color:var(--bg); font-size:21px; }
    .source-card { background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:27px; min-height:215px; margin-bottom:16px; }
    .source-card h3 { font:700 25px/1.2 Georgia,serif; margin:14px 0; }
    .source-card p { color:var(--muted); font-size:14px; }
    .welcome { background:var(--notice); border-radius:25px; padding:72px 60px 180px; margin-bottom:0; min-height:700px; position:relative; isolation:isolate; overflow:hidden; }
    .welcome::before, .welcome::after { content:""; position:absolute; border-radius:50%; pointer-events:none; z-index:-1; }
    .welcome::before { width:760px; height:760px; top:-430px; right:-400px; background:color-mix(in srgb,var(--notice),var(--orange) 7%); }
    .welcome::after { width:450px; height:450px; top:-190px; right:-180px; background:var(--notice); border:1px solid color-mix(in srgb,var(--orange),transparent 82%); box-shadow:0 0 0 68px color-mix(in srgb,var(--orange),transparent 93%); }
    .welcome-mark { display:grid; place-items:center; width:96px; height:96px; background:var(--surface); color:var(--orange); border-radius:26px; margin-bottom:40px; }
    .welcome-mark svg { width:48px; height:48px; }
    .welcome .eyebrow { font-size:14px; letter-spacing:2.4px; margin-bottom:14px; }
    .welcome h1.page-title { font-size:clamp(44px,5.7vw,82px)!important; line-height:.99!important; letter-spacing:-3.2px; max-width:1180px; margin-bottom:40px; }
    .welcome .page-intro { font-size:clamp(17px,1.8vw,24px); line-height:1.7; max-width:960px; margin:0; }
    .st-key-welcome-cta { margin-top:-130px; margin-left:60px; position:relative; z-index:2; min-height:64px; }
    .st-key-welcome-cta [data-testid="stPageLink"] a { min-height:66px; width:347px; max-width:100%; justify-content:space-between; padding:0 27px; border:0; border-radius:13px; background:var(--green); color:#fff; font-size:16px; font-weight:700; text-decoration:none; }
    .st-key-welcome-cta [data-testid="stPageLink"] a * { color:#fff!important; }
    .st-key-welcome-cta [data-testid="stPageLink"] a p { margin:0; font-size:16px; font-weight:700; }
    .st-key-welcome-cta [data-testid="stPageLink"] a:hover { filter:brightness(1.08); color:#fff; }
    @media (max-width:700px) {
      [data-testid="stMainBlockContainer"] { padding:2rem 1rem 3rem; }
      [data-testid="stMainBlockContainer"]:has(.welcome) { padding:1rem 1rem 3rem; }
      .page-title { font-size:38px; letter-spacing:-1.5px; }
      .page-intro { font-size:15px; }
      .welcome { min-height:500px; padding:30px 22px 110px; }
      .welcome-mark { width:72px; height:72px; border-radius:20px; margin-bottom:32px; }
      .welcome-mark svg { width:38px; height:38px; }
      .welcome h1.page-title { font-size:clamp(42px,10vw,62px)!important; letter-spacing:-2px; margin-bottom:24px; }
      .st-key-welcome-cta { margin-top:-84px; margin-left:22px; }
      .st-key-welcome-cta [data-testid="stPageLink"] a { width:100%; min-height:58px; padding:0 17px; font-size:14px; }
      .step-track { margin-bottom:28px; }
    }
    @media print { [data-testid="stSidebar"], [data-testid="stHeader"], button { display:none!important; } }
    </style>''', unsafe_allow_html=True)


def heading(kicker, title, intro=''):
    st.markdown(f'<div class="eyebrow">{safe(kicker)}</div><h1 class="page-title">{safe(title)}</h1><p class="page-intro">{safe(intro)}</p>', unsafe_allow_html=True)


def progress(step, label):
    st.markdown(f'<div class="step-line"><span>STEP {step + 1} OF 5</span><span>{safe(label)}</span></div><div class="step-track" role="progressbar" aria-label="Care guide progress" aria-valuemin="0" aria-valuemax="5" aria-valuenow="{step+1}"><div style="width:{(step+1)*20}%"></div></div>', unsafe_allow_html=True)


def notice(text):
    st.markdown(f'<div class="care-notice">{safe(text)}</div>', unsafe_allow_html=True)


def plan_card(plan):
    st.markdown(f'''<div class="plan-summary"><span class="pill">{safe(plan.get('metal_level', ''))} · {safe(plan.get('plan_type', ''))}</span><h3>{safe(plan['plan_name'])}</h3><p>{safe(plan['insurer'])}</p><div class="plan-meta"><div><small>Network</small><strong>{safe(plan['network_name'])}</strong></div><div><small>Plan year</small><strong>{safe(plan.get('year', '2026'))}</strong></div></div></div>''', unsafe_allow_html=True)


def selection(area, specialty):
    st.markdown(f'<div class="selection-strip"><small>Your selection</small><strong>{safe(area)}</strong><p>We’ll search for <strong>{safe(specialty)}</strong> providers.</p></div>', unsafe_allow_html=True)


def action_heading(number, title):
    st.markdown(f'<div class="action-heading"><span class="action-number">{number}</span>{safe(title)}</div>', unsafe_allow_html=True)


def sidebar(groups):
    with st.sidebar:
        st.markdown('<div class="brand"><div class="brand-mark" aria-hidden="true">♡</div><div><div class="brand-title">Plan Places</div><div class="brand-sub">Finder</div></div></div>', unsafe_allow_html=True)
        icons = [':material/auto_awesome:', ':material/favorite_border:', ':material/description:', ':material/map:', ':material/chat_bubble_outline:', ':material/help_outline:', ':material/verified_user:']
        i = 0
        for title, pages in groups.items():
            st.markdown(f'<div class="nav-label">{safe(title.upper())}</div>', unsafe_allow_html=True)
            for page in pages:
                st.page_link(page, icon=icons[i % len(icons)])
                i += 1
        st.divider()
        st.toggle('Dark mode', key='dark_mode')
        st.caption('General information only.\n\nNot medical or insurance advice.')


CARE_DESCRIPTIONS = {
    'Primary care / general health': ('Annual visits, new concerns, and ongoing care', ':material/favorite_border:'),
    'Hearing': ('Hearing exams, devices, and specialist care', ':material/hearing:'),
    'Mental health': ('Therapy, counseling, and psychiatric care', ':material/psychology:'),
    'Skin': ('Skin concerns and screenings', ':material/wb_sunny:'),
    'Eye care': ('Vision exams and medical eye care', ':material/visibility:'),
    'Dental care': ('Routine and restorative dental services', ':material/health_and_safety:'),
    'Movement / rehabilitation': ('Physical therapy and mobility support', ':material/accessibility_new:'),
    'Children’s care': ('Well visits and pediatric care', ':material/child_care:'),
    'Urgent care': ('Prompt help for non-life-threatening needs', ':material/verified_user:'),
    'Another specialty': ('Search a different provider specialty', ':material/search:'),
}


def care_cards(paths, state):
    area = state.get('draft_area', state.get('area', next(iter(paths))))
    st.subheader('Choose a care area')
    st.caption('Choose one. You can change this later.')
    items = list(paths)
    for start in range(0, 9, 3):
        for column, name in zip(st.columns(3), items[start:start + 3]):
            description, icon = CARE_DESCRIPTIONS[name]
            with column:
                if st.button(f'**{name}**\n{description}', icon=icon,
                    key=f'care_card_{items.index(name)}', type='primary' if name == area else 'secondary', use_container_width=True):
                    state['draft_area'] = name
                    st.rerun()
    if st.button('Another specialty', icon=':material/search:', key='care_card_other', type='primary' if area == 'Another specialty' else 'secondary'):
        state['draft_area'] = 'Another specialty'
        st.rerun()
    return area


def welcome_page(journey_nav):
    st.markdown('<div class="welcome"><div class="welcome-mark" aria-hidden="true"><svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M24 40 8.7 25.2C.1 16.8 12.2 4.1 24 15.1 35.8 4.1 47.9 16.8 39.3 25.2L24 40Z" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg></div><div class="eyebrow">Welcome to Plan Places</div><h1 class="page-title">Health insurance is confusing. Finding care shouldn’t be.</h1><p class="page-intro">Tell us what matters to you, look at a plan, and see hospitals and doctors near you in Massachusetts.</p></div>', unsafe_allow_html=True)
    with st.container(key="welcome-cta"):
        st.page_link(journey_nav, label='Start the guided care search  →')
    for col, number, title, description in zip(st.columns(3), ['01','02','03'], ['Tell us what matters','Look at your plan','Find nearby care'], ['Choose the kind of care you need.','Understand benefits and network details.','Search providers and prepare next steps.']):
        with col:
            st.markdown(f'<div class="source-card"><div class="eyebrow">{number}</div><h3>{title}</h3><p>{description}</p></div>', unsafe_allow_html=True)
    notice('Hospital and provider results are not matched to your insurance network. Confirm coverage with your insurer before getting care.')


def sources_page():
    heading('Transparency', 'Sources and limits', 'Where the information in Plan Places comes from—and what it cannot tell you.')
    entries = [
        ('Hospital information','CMS Hospital General Information','Hospital locations use approximate ZIP-code centers.','https://data.cms.gov/provider-data/dataset/xubh-q36u'),
        ('Plans and benefits','CMS 2026 MA State-Based Exchange data','Benefit records describe coverage and conditions, but do not establish your exact cost or approval.','https://www.cms.gov/marketplace/resources/data/state-based-public-use-files'),
        ('Provider listings','CMS NPI Registry','Registry listings do not establish insurance participation or new-patient availability. Searches retrieve up to 15 listings.','https://npiregistry.cms.hhs.gov/'),
        ('Address matching','U.S. Census Geocoder','Addresses are sent for matching. Distances are approximate straight-line distances, not driving distances.','https://geocoding.geo.census.gov/'),
    ]
    for offset in [0,2]:
        for col, (category,title,body,url) in zip(st.columns(2), entries[offset:offset+2]):
            with col:
                st.markdown(f'<div class="source-card"><div class="eyebrow">{safe(category)}</div><h3>{safe(title)}</h3><p>{safe(body)}</p><a href="{safe(url)}" target="_blank" rel="noopener noreferrer">View source ↗</a></div>', unsafe_allow_html=True)
    notice('This site does not know which providers accept which plans. Confirm network status, costs, coverage, and availability with your insurer and provider.')

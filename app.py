import pandas as pd
import streamlit as st


st.set_page_config(page_title='Plan Places Finder', layout='wide')


@st.cache_data
def load_data():
    hospitals = pd.read_csv('data/clean/hospitals.csv')
    plans = pd.read_csv('data/clean/fake_plans.csv')
    return hospitals, plans


hospitals, plans = load_data()

# Load and display the selected plan details
st.title('Plan Places Finder')
st.info('This map shows hospitals in the area. It cannot confirm that a hospital is in your plan network. Always confirm with your insurer before getting care.')

# Sidebar for plan selection and filters
plan_name = st.sidebar.selectbox('Choose a plan', plans['plan_name'])
types = st.sidebar.multiselect('Hospital type', sorted(hospitals['type'].dropna().unique()))
min_rating = st.sidebar.slider('Minimum rating', 1, 5, 1)
emergency_only = st.sidebar.checkbox('Emergency services only')

# Display the selected plan details
plan = plans[plans['plan_name'] == plan_name].iloc[0]
col1, col2, col3 = st.columns(3)
col1.metric('Plan type', plan['plan_type'])
col2.metric('Metal level', plan['metal_level'])
col3.metric('Network', str(plan['network_name']))
if pd.notna(plan['directory_url']):
    st.link_button('Open official provider directory', plan['directory_url'])

# Filter hospitals based on selected criteria
filtered = hospitals.copy()
if types:
    filtered = filtered[filtered['type'].isin(types)]
filtered = filtered[(filtered['rating'].isna()) | (filtered['rating'] >= min_rating)]
if emergency_only:
    filtered = filtered[filtered['emergency'] == 'Yes']

# Display the filtered hospitals on a map and in a table
st.subheader(f'{len(filtered)} hospitals match')
st.map(filtered, latitude='latitude', longitude='longitude')
st.dataframe(filtered[['name','city','type','rating','emergency']])
# rating filter keeps hospitals with no rating so they do not silently vanish. Mention this in the app text if you like.

# Data source and disclaimer footer
st.caption('Data: HHS Health Insurance Marketplace, CMS Network PUF, CMS Hospital General Information. Plan data year: [fill in]. Not insurance advice.')

# Glossary of insurance terms
with st.expander('What do these terms mean?'):
    st.write('**Premium:** what you pay each month to have the plan.')
    st.write('**Deductible:** what you pay yourself before the plan starts helping.')
    st.write('**Copay:** a fixed fee for a visit or prescription.')
    st.write('**Coinsurance:** your percentage share of a bill after the deductible.')
    st.write('**Out-of-pocket max:** the most you pay in a year; the plan pays the rest.')

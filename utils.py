
import pandas as pd
    
def load_data():
    hospitals = pd.read_csv('data/clean/hospitals.csv')
    plans = pd.read_csv('data/clean/fake_plans.csv')
    return hospitals, plans


hospitals, plans = load_data()


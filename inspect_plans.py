import pandas as pd

## import insurance plans info

plans = pd.read_csv('Data/raw/PlanAttributes.csv', low_memory=False)
print(plans.columns.tolist())
print(plans['BusinessYear'].value_counts())
print(plans['StateCode'].value_counts().head(20))

net = pd.read_csv('Data/raw/Network.csv')
print(net.columns.tolist())
print(net.head())

keep = ['BusinessYear', 'StateCode', 'PlanId', 'StandardComponentId',
        'PlanMarketingName', 'IssuerId', 'PlanType', 'MetalLevel',
        'NetworkId', 'ServiceAreaId', 'DentalOnlyPlan', 'MarketCoverage']

plans = pd.read_csv('Data/raw/PlanAttributes.csv', usecols=keep, low_memory=False)

plans = plans.rename(columns={
    'PlanMarketingName': 'plan_name',
    'PlanType': 'plan_type',
    'MetalLevel': 'metal_level',
})

plans = plans[plans['StateCode'] == 'MA']
plans = plans[plans['BusinessYear'] == 2016]

net_keep = ['BusinessYear', 'StateCode', 'IssuerId', 'NetworkName', 'NetworkId', 'NetworkURL']
net = pd.read_csv('Data/raw/Network.csv', usecols=net_keep)
net = net.rename(columns={'NetworkName': 'network_name', 'NetworkURL': 'directory_url'})
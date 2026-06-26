import pandas as pd
import numpy as np
import sys
import os

sys.path.append('shared')
from config_loader import get_tariff_vectors, get_parameters

opt = pd.read_csv('optimization/outputs/day_ahead_schedule.csv')
rule = pd.read_csv('optimization/outputs/rule_based_schedule.csv')
params = get_parameters()
eff_c = params.get('eff_c', 0.95)
eff_d = params.get('eff_d', 0.95)
B_d = params.get('B_d', 0.02)

G_b, G_s = get_tariff_vectors(timestamps=opt['Timestamp'])

opt['Tariff_Imp'] = G_b
opt['Tariff_Exp'] = G_s
rule['Tariff_Imp'] = G_b
rule['Tariff_Exp'] = G_s

# Calculate costs
for df in [opt, rule]:
    df['Imp_Cost'] = df['Grid_Import_kW'] * df['Tariff_Imp']
    df['Exp_Rev'] = df['Grid_Export_kW'] * df['Tariff_Exp']
    df['Deg_Cost'] = (df['Bat_Charge_kW'] + df['Bat_Discharge_kW']) * B_d
    df['Net_Cost'] = df['Imp_Cost'] - df['Exp_Rev'] + df['Deg_Cost']

# 1. Arbitrage Analysis
print('--- 1. ARBITRAGE ANALYSIS ---')
arb_mask = (opt['Grid_Export_kW'] > 0) & (rule['Grid_Export_kW'] == 0)
arb_hours = opt[arb_mask]
print('Hours where Opt exports but Rule does not:')
print(arb_hours[['Timestamp', 'Grid_Export_kW', 'Tariff_Exp', 'Exp_Rev']].to_string())
print(f'Total additional revenue from these hours: ${arb_hours.Exp_Rev.sum():.2f}')

# 2. Detailed Table
print('\n--- 2. DETAILED HOURLY COMPARISON TABLE ---')
res = pd.DataFrame({
    'Timestamp': opt['Timestamp'],
    'Imp_Tariff': G_b,
    'Exp_Tariff': G_s,
    'Load': opt['Demand_Forecast_kW'].round(2),
    'PV': opt['Solar_Forecast_kW'].round(2),
    'Opt_Imp': opt['Grid_Import_kW'].round(2),
    'Rule_Imp': rule['Grid_Import_kW'].round(2),
    'Opt_Exp': opt['Grid_Export_kW'].round(2),
    'Rule_Exp': rule['Grid_Export_kW'].round(2),
    'Opt_Chg': opt['Bat_Charge_kW'].round(2),
    'Rule_Chg': rule['Bat_Charge_kW'].round(2),
    'Opt_Dis': opt['Bat_Discharge_kW'].round(2),
    'Rule_Dis': rule['Bat_Discharge_kW'].round(2),
    'Opt_SOC': opt['Scheduled_SOC_kWh'].round(2),
    'Rule_SOC': rule['Scheduled_SOC_kWh'].round(2),
    'Opt_Cost': opt['Net_Cost'].round(2),
    'Rule_Cost': rule['Net_Cost'].round(2)
})
res['Cost_Advantage'] = (res['Rule_Cost'] - res['Opt_Cost']).round(2)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
print(res.to_string())

# 3. Cost Differences
print('\n--- 3. COST DIFFERENCES ---')
imp_diff = opt['Imp_Cost'].sum() - rule['Imp_Cost'].sum()
exp_diff = opt['Exp_Rev'].sum() - rule['Exp_Rev'].sum()
deg_diff = opt['Deg_Cost'].sum() - rule['Deg_Cost'].sum()
net_diff = opt['Net_Cost'].sum() - rule['Net_Cost'].sum()
print(f'Import Cost Diff (Opt - Rule): ${imp_diff:.2f}')
print(f'Export Rev Diff (Opt - Rule): ${exp_diff:.2f}')
print(f'Degradation Diff (Opt - Rule): ${deg_diff:.2f}')
print(f'Net Cost Diff (Opt - Rule): ${net_diff:.2f}')

# 4. Constraints Verification
print('\n--- 4. CONSTRAINTS VERIFICATION ---')
opt_overlap = sum((opt['Grid_Import_kW'] > 1e-4) & (opt['Grid_Export_kW'] > 1e-4))
rule_overlap = sum((rule['Grid_Import_kW'] > 1e-4) & (rule['Grid_Export_kW'] > 1e-4))
print(f'Hours with simultaneous import/export - Opt: {opt_overlap}, Rule: {rule_overlap}')

for name, df in [('Opt', opt), ('Rule', rule)]:
    D_met = (df['Solar_Used_kW'] - df['Bat_Charge_kW'] - df['Grid_Export_kW']) + df['Bat_Discharge_kW'] + df['Grid_Import_kW']
    imbalance = (D_met - df['Demand_Forecast_kW']).abs().max()
    print(f'Max power imbalance in {name}: {imbalance:.4f} kW')

# 5. Top 5 Hours
print('\n--- 5. TOP 5 HOURS DRIVING COST ADVANTAGE ---')
top5 = res.sort_values('Cost_Advantage', ascending=False).head(5)
print(top5[['Timestamp', 'Imp_Tariff', 'Exp_Tariff', 'Opt_Cost', 'Rule_Cost', 'Cost_Advantage']].to_string())

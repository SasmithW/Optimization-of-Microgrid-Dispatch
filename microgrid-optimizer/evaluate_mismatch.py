import pulp
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

# =========================================================================
# 1. SETUP & FORECAST DATA
# =========================================================================
T = 24
hours = list(range(T))

D_forecast = [
    120, 110, 100,  95,  90, 100,
    130, 160, 200, 220, 230, 240,
    250, 240, 230, 220, 210, 230,
    260, 280, 270, 230, 180, 140,
]
S_av_forecast = [
      0,   0,   0,   0,   0,  10,
     40,  80, 150, 220, 270, 300,
    310, 290, 250, 200, 130,  60,
     10,   0,   0,   0,   0,   0,
]
G_b = [0.05]*6 + [0.12]*6 + [0.10]*3 + [0.12, 0.15, 0.18] + [0.22, 0.25, 0.22, 0.15, 0.10, 0.08]
G_s = [0.03]*6 + [0.04, 0.05] + [0.06]*4 + [0.05]*3 + [0.06, 0.07, 0.08] + [0.10, 0.12, 0.10, 0.07, 0.05, 0.04]

B_d = 0.02
C_bl = 500.0
C_br = 200.0
C_g = 300.0
eff_c = 0.95
eff_d = 0.95
S_init = 250.0
S_min = 50.0

# =========================================================================
# 2. RUN BASELINE OPTIMIZATION
# =========================================================================
prob = pulp.LpProblem("Microgrid_Baseline", pulp.LpMinimize)

Qs  = pulp.LpVariable.dicts("Qs",  hours, lowBound=0, cat="Continuous")
Qb  = pulp.LpVariable.dicts("Qb",  hours, lowBound=0, cat="Continuous")
Qsb = pulp.LpVariable.dicts("Qsb", hours, lowBound=0, cat="Continuous")
Qg  = pulp.LpVariable.dicts("Qg",  hours, lowBound=0, cat="Continuous")
Qge = pulp.LpVariable.dicts("Qge", hours, lowBound=0, cat="Continuous")
S   = pulp.LpVariable.dicts("S",   hours, lowBound=0, cat="Continuous")
yb   = pulp.LpVariable.dicts("yb",   hours, cat="Binary")
ysb  = pulp.LpVariable.dicts("ysb",  hours, cat="Binary")
yg_i = pulp.LpVariable.dicts("yg_i", hours, cat="Binary")
yg_e = pulp.LpVariable.dicts("yg_e", hours, cat="Binary")

prob += pulp.lpSum([G_b[t]*Qg[t] - G_s[t]*Qge[t] + B_d*(Qsb[t] + Qb[t]) for t in hours])

for t in hours:
    prob += (Qg[t] + Qs[t] + Qb[t] == D_forecast[t] + Qge[t] + Qsb[t])
    prob += (Qs[t] + Qsb[t] + Qge[t] <= S_av_forecast[t])
    prob += (Qg[t] <= C_g * yg_i[t])
    prob += (Qge[t] <= C_g * yg_e[t])
    prob += (Qb[t] <= C_br * yb[t])
    prob += (Qsb[t] <= C_br * ysb[t])
    prob += (S[t] >= S_min)
    prob += (S[t] <= C_bl)
    prob += (ysb[t] + yb[t] <= 1)
    prob += (yg_i[t] + yg_e[t] <= 1)
    if t == 0:
        prob += (S[t] == S_init + eff_c * Qsb[t] - Qb[t] / eff_d)
    else:
        prob += (S[t] == S[t - 1] + eff_c * Qsb[t] - Qb[t] / eff_d)

solver = pulp.PULP_CBC_CMD(msg=0)
prob.solve(solver)

# Freeze dispatch
sched_Qs = [Qs[t].varValue for t in hours]
sched_Qb = [Qb[t].varValue for t in hours]
sched_Qsb = [Qsb[t].varValue for t in hours]
sched_Qg = [Qg[t].varValue for t in hours]
sched_Qge = [Qge[t].varValue for t in hours]
sched_S = [S[t].varValue for t in hours]

# =========================================================================
# 3. DEFINE SCENARIOS
# =========================================================================
scenarios = {
    "1_Perfect_Forecast": {"D": list(D_forecast), "S": list(S_av_forecast)},
    "2_Lower_Solar": {"D": list(D_forecast), "S": [s * 0.7 for s in S_av_forecast]},
    "3_Higher_Solar": {"D": list(D_forecast), "S": [s * 1.4 for s in S_av_forecast]},
    "4_Higher_Demand": {"D": [d * 1.3 if 17 <= i <= 23 else d for i, d in enumerate(D_forecast)], "S": list(S_av_forecast)},
    "5_Lower_Demand": {"D": [d * 0.8 for d in D_forecast], "S": list(S_av_forecast)},
    "6_Worst_Case": {"D": [d * 1.3 if 17 <= i <= 23 else d for i, d in enumerate(D_forecast)], "S": [s * 0.6 for s in S_av_forecast]},
}

# =========================================================================
# 4. EVALUATE AND PLOT SCENARIOS
# =========================================================================
markdown_content = ["# Forecast Mismatch Robustness Analysis\n\nThis document evaluates the fragility of the deterministic baseline model when real operating conditions deviate from perfect day-ahead forecasts. **The day-ahead dispatch schedule remains frozen.**\n"]

def evaluate_scenario(name, actual_D, actual_S):
    unmet_demand_total = 0
    excess_gen_total = 0
    unused_solar_total = 0
    infeasible_hours = 0
    
    unmet_arr = []
    excess_arr = []
    
    for t in hours:
        # Constrain used solar by actual physical availability
        realized_Qs = min(sched_Qs[t], actual_S[t])
        
        generation = sched_Qg[t] + realized_Qs + sched_Qb[t]
        consumption = actual_D[t] + sched_Qge[t] + sched_Qsb[t]
        
        mismatch = generation - consumption
        
        if mismatch < -0.01:
            unmet = -mismatch
            unmet_demand_total += unmet
            unmet_arr.append(unmet)
            excess_arr.append(0)
            infeasible_hours += 1
        elif mismatch > 0.01:
            excess = mismatch
            excess_gen_total += excess
            unmet_arr.append(0)
            excess_arr.append(excess)
            infeasible_hours += 1
        else:
            unmet_arr.append(0)
            excess_arr.append(0)
            
        unused_solar_total += max(0, actual_S[t] - realized_Qs)
        
    return unmet_demand_total, excess_gen_total, unused_solar_total, infeasible_hours, unmet_arr, excess_arr

artifacts_dir = r"C:\Users\Sasmitha\.gemini\antigravity\brain\b7b56080-25b3-412e-8644-21f32e1aba9b\artifacts"
os.makedirs(artifacts_dir, exist_ok=True)

for sc_name, data in scenarios.items():
    act_D = data["D"]
    act_S = data["S"]
    
    u_dem, e_gen, u_sol, inf_hrs, arr_u, arr_e = evaluate_scenario(sc_name, act_D, act_S)
    
    title_name = sc_name.replace("_", " ")
    
    markdown_content.append(f"## {title_name}")
    markdown_content.append(f"- **Total Unmet Demand**: {u_dem:.2f} kWh")
    markdown_content.append(f"- **Total Excess Generation**: {e_gen:.2f} kWh")
    markdown_content.append(f"- **Unused Solar Energy**: {u_sol:.2f} kWh")
    markdown_content.append(f"- **Infeasible Hours**: {inf_hrs} hours")
    
    if inf_hrs > 0:
        markdown_content.append("\n> [!WARNING]\n> **Infeasibility Detected**\n> The fixed deterministic schedule failed to satisfy physical constraints under these conditions, highlighting the lack of robustness.")
    else:
        markdown_content.append("\n> [!NOTE]\n> **Operation Feasible**\n> The schedule remained valid, though efficiency may have varied.")
        
    # Plotting
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(f"Mismatch Evaluation: {title_name}", fontsize=14, fontweight="bold")
    
    x = np.arange(T)
    
    # Plot 1: Forecast vs Actual
    ax1 = axes[0]
    ax1.plot(x, D_forecast, "k--", label="Forecast Demand", alpha=0.6)
    ax1.plot(x, act_D, "r-", label="Actual Demand", linewidth=2)
    ax1.plot(x, S_av_forecast, "y--", label="Forecast Solar", alpha=0.6)
    ax1.plot(x, act_S, "orange", label="Actual Solar", linewidth=2)
    ax1.set_ylabel("Power (kW)")
    ax1.set_title("Forecast vs Actual Conditions")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.3)
    
    # Plot 2: Violations
    ax2 = axes[1]
    ax2.bar(x, arr_u, color="red", alpha=0.7, label="Unmet Demand (Deficit)")
    ax2.bar(x, arr_e, color="blue", alpha=0.7, label="Excess Generation (Surplus)")
    ax2.set_ylabel("Mismatch Power (kW)")
    ax2.set_xlabel("Hour")
    ax2.set_title("Power Balance Violations (Scheduled vs Actual)")
    ax2.legend(loc="upper left")
    ax2.grid(alpha=0.3)
    ax2.axhline(0, color='k', linewidth=0.5)
    
    plt.tight_layout()
    plot_path = os.path.join(artifacts_dir, f"{sc_name}_mismatch.png")
    # Convert windows path backslashes to forward slashes for markdown
    md_img_path = plot_path.replace("\\", "/")
    plt.savefig(plot_path, dpi=120)
    plt.close()
    
    markdown_content.append(f"\n![{title_name} Mismatch Plot](file:///{md_img_path})\n")

# Discussion Section
markdown_content.append("""
## Discussion & Conclusion

This analysis clearly exposes the extreme fragility of a purely deterministic microgrid scheduling model when subjected to real-world uncertainty:

1. **Vulnerability to Solar Deficits**: When solar generation falls short of the forecast (Scenario 2 and 6), the pre-committed battery and grid schedules cannot adapt. This immediately translates into **unmet demand**, resulting in load shedding or blackout conditions.
2. **Inability to Capture Surpluses**: When demand is lower than expected or solar is higher, the fixed schedule forces the microgrid to curtail the excess generation rather than opportunistically charging the battery.
3. **Cascading Mismatches**: Because the power balance constraint `Qg + Qs + Qb = D + Qge + Qsb` is rigidly tied to forecast values, *any* deviation in `D` or `S_av` without adjusting control variables (`Qg`, `Qb`, `Qsb`) inherently violates the constraint.
4. **Architectural Necessity for Robustness**: A real-time controller or a more advanced formulation is mandatory. To resolve this, the next stage of the thesis should explore **Robust Optimization (RO)** or **Stochastic Programming (SP)** to schedule bounds rather than fixed setpoints, and introduce slack variables (load shedding, curtailment limits) to guarantee solver feasibility even under stress scenarios.
""")

with open(r"C:\Users\Sasmitha\.gemini\antigravity\brain\b7b56080-25b3-412e-8644-21f32e1aba9b\artifacts\forecast_mismatch_report.md", "w") as f:
    f.write("\n".join(markdown_content))

print("Evaluation complete. Artifact created.")

"""
===========================================================================
Microgrid Energy Management Optimization Model — Baseline (v1.0)
===========================================================================

Deterministic day-ahead scheduling model for a grid-connected microgrid
containing Solar PV, Battery Energy Storage (BESS), and utility grid.

Formulation : Mixed-Integer Linear Program (MILP)
Solver      : CBC (via PuLP)
Horizon     : 24 hours (Δt = 1 h)

This is the INITIAL BASELINE MODEL for an undergraduate research thesis.
It is intentionally kept in its simplest deterministic form so that its
limitations can be studied before introducing robust improvements.

Author      : [Your Name]
Date        : May 2026
===========================================================================
"""

# =========================================================================
# 1. IMPORTS
# =========================================================================
import pulp
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend (saves PNG without opening GUI)
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# =========================================================================
# 2. SYNTHETIC EXAMPLE DATA
# =========================================================================
# Time horizon
T = 24  # hours (0 → 23)
hours = list(range(T))

# --- Demand profile (kW) ------------------------------------------------
# Typical residential-commercial mixed load curve
D = [
    120, 110, 100,  95,  90, 100,   # 00:00 – 05:00  (overnight low)
    130, 160, 200, 220, 230, 240,   # 06:00 – 11:00  (morning ramp)
    250, 240, 230, 220, 210, 230,   # 12:00 – 17:00  (afternoon)
    260, 280, 270, 230, 180, 140,   # 18:00 – 23:00  (evening peak)
]

# --- Available solar generation (kW) ------------------------------------
# Bell-shaped PV output peaking at midday
S_av = [
      0,   0,   0,   0,   0,  10,   # 00:00 – 05:00
     40,  80, 150, 220, 270, 300,   # 06:00 – 11:00
    310, 290, 250, 200, 130,  60,   # 12:00 – 17:00
     10,   0,   0,   0,   0,   0,   # 18:00 – 23:00
]

# --- Grid electricity buying tariff ($/kWh) ------------------------------
# Time-of-use tariff: off-peak / shoulder / peak
G_b = [
    0.05, 0.05, 0.05, 0.05, 0.05, 0.05,   # 00–05  off-peak
    0.08, 0.10, 0.12, 0.12, 0.12, 0.12,   # 06–11  shoulder
    0.10, 0.10, 0.10, 0.12, 0.15, 0.18,   # 12–17  shoulder → peak
    0.22, 0.25, 0.22, 0.15, 0.10, 0.08,   # 18–23  peak → off-peak
]

# --- Grid electricity selling tariff ($/kWh) -----------------------------
# Feed-in tariff is typically lower than the buying price
G_s = [
    0.03, 0.03, 0.03, 0.03, 0.03, 0.03,
    0.04, 0.05, 0.06, 0.06, 0.06, 0.06,
    0.05, 0.05, 0.05, 0.06, 0.07, 0.08,
    0.10, 0.12, 0.10, 0.07, 0.05, 0.04,
]

# =========================================================================
# 3. CONSTANT PARAMETERS
# =========================================================================
B_d    = 0.02      # Battery degradation cost coefficient ($/kWh)
C_bl   = 500.0     # Maximum battery energy storage capacity (kWh)
C_br   = 200.0     # Maximum battery charge/discharge power (kW)
C_g    = 300.0     # Maximum utility grid power exchange (kW)
eff_c  = 0.95      # Battery charging efficiency
eff_d  = 0.95      # Battery discharging efficiency
S_init = 250.0     # Initial battery state of charge (kWh)
S_min  = 50.0      # Minimum allowable battery SOC (kWh)

# =========================================================================
# 4. PULP PROBLEM DEFINITION
# =========================================================================
prob = pulp.LpProblem("Microgrid_Day_Ahead_Scheduling", pulp.LpMinimize)

# =========================================================================
# 5. DECISION VARIABLES
# =========================================================================

# --- Continuous variables ------------------------------------------------
Qs  = pulp.LpVariable.dicts("Qs",  hours, lowBound=0, cat="Continuous")  # Solar utilised (kW)
Qb  = pulp.LpVariable.dicts("Qb",  hours, lowBound=0, cat="Continuous")  # Battery discharge (kW)
Qsb = pulp.LpVariable.dicts("Qsb", hours, lowBound=0, cat="Continuous")  # Battery charge (kW)
Qg  = pulp.LpVariable.dicts("Qg",  hours, lowBound=0, cat="Continuous")  # Grid import (kW)
Qge = pulp.LpVariable.dicts("Qge", hours, lowBound=0, cat="Continuous")  # Grid export (kW)
S   = pulp.LpVariable.dicts("S",   hours, lowBound=0, cat="Continuous")  # Battery SOC (kWh)

# --- Binary variables ----------------------------------------------------
yb   = pulp.LpVariable.dicts("yb",   hours, cat="Binary")  # Battery discharge mode
ysb  = pulp.LpVariable.dicts("ysb",  hours, cat="Binary")  # Battery charging mode
yg_i = pulp.LpVariable.dicts("yg_i", hours, cat="Binary")  # Grid import mode
yg_e = pulp.LpVariable.dicts("yg_e", hours, cat="Binary")  # Grid export mode

# =========================================================================
# 6. OBJECTIVE FUNCTION
# =========================================================================
# Minimize total operational cost:
#   J = Σ [ G_b[t]·Qg[t]  −  G_s[t]·Qge[t]  +  B_d·(Qsb[t] + Qb[t]) ]

prob += pulp.lpSum([
    G_b[t] * Qg[t]
    - G_s[t] * Qge[t]
    + B_d * (Qsb[t] + Qb[t])
    for t in hours
]), "Total_Operational_Cost"

# =========================================================================
# 7. CONSTRAINTS
# =========================================================================

for t in hours:
    # -----------------------------------------------------------------
    # Constraint 1 — Power Balance
    #   Qg[t] + Qs[t] + Qb[t] = D[t] + Qge[t] + Qsb[t]
    # -----------------------------------------------------------------
    prob += (
        Qg[t] + Qs[t] + Qb[t] == D[t] + Qge[t] + Qsb[t],
        f"Power_Balance_{t}"
    )

    # -----------------------------------------------------------------
    # Constraint 2 — Solar Availability
    #   Qs[t] + Qsb[t] + Qge[t] <= S_av[t]
    # -----------------------------------------------------------------
    prob += (
        Qs[t] + Qsb[t] + Qge[t] <= S_av[t],
        f"Solar_Availability_{t}"
    )

    # -----------------------------------------------------------------
    # Constraint 3 — Grid Capacity
    #   Qg[t]  <= C_g · yg_i[t]
    #   Qge[t] <= C_g · yg_e[t]
    # -----------------------------------------------------------------
    prob += (
        Qg[t] <= C_g * yg_i[t],
        f"Grid_Import_Capacity_{t}"
    )
    prob += (
        Qge[t] <= C_g * yg_e[t],
        f"Grid_Export_Capacity_{t}"
    )

    # -----------------------------------------------------------------
    # Constraint 4 — Battery Power Limits
    #   Qb[t]  <= C_br · yb[t]
    #   Qsb[t] <= C_br · ysb[t]
    # -----------------------------------------------------------------
    prob += (
        Qb[t] <= C_br * yb[t],
        f"Battery_Discharge_Limit_{t}"
    )
    prob += (
        Qsb[t] <= C_br * ysb[t],
        f"Battery_Charge_Limit_{t}"
    )

    # -----------------------------------------------------------------
    # Constraint 5 — Battery Capacity (SOC bounds)
    #   S_min <= S[t] <= C_bl
    # -----------------------------------------------------------------
    prob += (
        S[t] >= S_min,
        f"SOC_Lower_Bound_{t}"
    )
    prob += (
        S[t] <= C_bl,
        f"SOC_Upper_Bound_{t}"
    )

    # -----------------------------------------------------------------
    # Constraint 6 — Battery Logic (no simultaneous charge/discharge)
    #   ysb[t] + yb[t] <= 1
    # -----------------------------------------------------------------
    prob += (
        ysb[t] + yb[t] <= 1,
        f"Battery_Logic_{t}"
    )

    # -----------------------------------------------------------------
    # Constraint 7 — Grid Logic (no simultaneous import/export)
    #   yg_i[t] + yg_e[t] <= 1
    # -----------------------------------------------------------------
    prob += (
        yg_i[t] + yg_e[t] <= 1,
        f"Grid_Logic_{t}"
    )

    # -----------------------------------------------------------------
    # Constraint 8 — Battery SOC Update
    #   S[t] = S[t-1] + eff_c · Qsb[t] − Qb[t] / eff_d
    # -----------------------------------------------------------------
    if t == 0:
        prob += (
            S[t] == S_init + eff_c * Qsb[t] - Qb[t] / eff_d,
            f"SOC_Update_{t}"
        )
    else:
        prob += (
            S[t] == S[t - 1] + eff_c * Qsb[t] - Qb[t] / eff_d,
            f"SOC_Update_{t}"
        )

# =========================================================================
# 8. SOLVE
# =========================================================================
solver = pulp.PULP_CBC_CMD(msg=1)  # CBC solver with output messages
status = prob.solve(solver)

# =========================================================================
# 9. RESULTS — Status & Total Cost
# =========================================================================
print("=" * 72)
print("  MICROGRID DAY-AHEAD OPTIMIZATION — BASELINE MODEL RESULTS")
print("=" * 72)
print()
print(f"  Optimization Status : {pulp.LpStatus[status]}")
print(f"  Total Operational Cost : ${pulp.value(prob.objective):,.4f}")
print()

# =========================================================================
# 10. RESULTS — Hourly Dispatch Table
# =========================================================================
header = (
    f"{'Hour':>4s}  "
    f"{'Demand':>8s}  "
    f"{'Solar':>8s}  "
    f"{'Bat Chg':>8s}  "
    f"{'Bat Dis':>8s}  "
    f"{'Grid Im':>8s}  "
    f"{'Grid Ex':>8s}  "
    f"{'SOC':>8s}"
)
print("-" * len(header))
print(header)
print("-" * len(header))

for t in hours:
    print(
        f"{t:4d}  "
        f"{D[t]:8.2f}  "
        f"{Qs[t].varValue:8.2f}  "
        f"{Qsb[t].varValue:8.2f}  "
        f"{Qb[t].varValue:8.2f}  "
        f"{Qg[t].varValue:8.2f}  "
        f"{Qge[t].varValue:8.2f}  "
        f"{S[t].varValue:8.2f}"
    )

print("-" * len(header))
print()

# =========================================================================
# 11. VISUALIZATION (Optional — matplotlib)
# =========================================================================

def plot_dispatch_results():
    """Generate stacked-area and line plots of the dispatch schedule."""

    # Extract result arrays
    demand_arr    = np.array([D[t]                for t in hours])
    solar_arr     = np.array([Qs[t].varValue      for t in hours])
    bat_dis_arr   = np.array([Qb[t].varValue      for t in hours])
    grid_imp_arr  = np.array([Qg[t].varValue      for t in hours])
    bat_chg_arr   = np.array([Qsb[t].varValue     for t in hours])
    grid_exp_arr  = np.array([Qge[t].varValue     for t in hours])
    soc_arr       = np.array([S[t].varValue       for t in hours])
    solar_avail   = np.array(S_av)

    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    fig.suptitle(
        "Microgrid Day-Ahead Dispatch — Baseline Model",
        fontsize=15, fontweight="bold", y=0.97,
    )

    x = np.arange(T)

    # --- Plot 1: Generation stack vs demand ------------------------------
    ax1 = axes[0]
    ax1.bar(x, solar_arr,   width=0.8, label="Solar Used",        color="#F59E0B")
    ax1.bar(x, bat_dis_arr, width=0.8, bottom=solar_arr,
            label="Battery Discharge", color="#10B981")
    ax1.bar(x, grid_imp_arr, width=0.8,
            bottom=solar_arr + bat_dis_arr,
            label="Grid Import",       color="#6366F1")
    ax1.step(x, demand_arr, where="mid", color="#EF4444",
             linewidth=2.0, label="Demand", zorder=5)
    ax1.step(x, solar_avail, where="mid", color="#FBBF24",
             linewidth=1.2, linestyle="--", label="Solar Available", zorder=4)
    ax1.set_ylabel("Power (kW)")
    ax1.set_title("Generation Dispatch vs Demand")
    ax1.legend(loc="upper left", fontsize=8, ncol=3)
    ax1.grid(axis="y", alpha=0.3)
    ax1.set_xlim(-0.5, T - 0.5)

    # --- Plot 2: Battery & grid actions ----------------------------------
    ax2 = axes[1]
    ax2.bar(x,  bat_dis_arr, width=0.8, label="Bat Discharge (+)", color="#10B981")
    ax2.bar(x, -bat_chg_arr, width=0.8, label="Bat Charge (−)",    color="#F97316")
    ax2.bar(x,  grid_imp_arr, width=0.4, label="Grid Import (+)",  color="#6366F1", alpha=0.6)
    ax2.bar(x, -grid_exp_arr, width=0.4, label="Grid Export (−)",  color="#EC4899", alpha=0.6)
    ax2.axhline(0, color="grey", linewidth=0.8)
    ax2.set_ylabel("Power (kW)")
    ax2.set_title("Battery & Grid Actions")
    ax2.legend(loc="upper left", fontsize=8, ncol=4)
    ax2.grid(axis="y", alpha=0.3)

    # --- Plot 3: Battery SOC ---------------------------------------------
    ax3 = axes[2]
    ax3.fill_between(x, soc_arr, alpha=0.35, color="#3B82F6")
    ax3.plot(x, soc_arr, marker="o", markersize=4, color="#2563EB",
             linewidth=1.8, label="SOC")
    ax3.axhline(S_min, color="#EF4444", linestyle="--", linewidth=1,
                label=f"SOC Min ({S_min} kWh)")
    ax3.axhline(C_bl,  color="#10B981", linestyle="--", linewidth=1,
                label=f"SOC Max ({C_bl} kWh)")
    ax3.set_ylabel("Energy (kWh)")
    ax3.set_xlabel("Hour of Day")
    ax3.set_title("Battery State of Charge")
    ax3.legend(loc="upper right", fontsize=8)
    ax3.grid(axis="y", alpha=0.3)
    ax3.set_ylim(0, C_bl * 1.1)

    # X-axis formatting
    for ax in axes:
        ax.xaxis.set_major_locator(ticker.MultipleLocator(1))
        ax.set_xlim(-0.5, T - 0.5)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig("baseline_dispatch_results.png", dpi=150, bbox_inches="tight")
    print("  [+] Dispatch plot saved -> baseline_dispatch_results.png")
    plt.show()


# Run visualisation if the optimisation was successful
if pulp.LpStatus[status] == "Optimal":
    plot_dispatch_results()
else:
    print("  [!] Optimisation did not find an optimal solution.")
    print("      Skipping visualisation.")

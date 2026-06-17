import pulp

def add_constraints(prob, Qs, Qb, Qsb, Qg, Qge, S, yb, ysb, yg_i, yg_e, 
                   D_forecast, S_av_forecast, C_br, C_g, C_bl, S_min, S_init, eff_c, eff_d, hours):
    for t in hours:
        # 1. Power Balance
        prob += (Qg[t] + Qs[t] + Qb[t] == D_forecast[t], f"Power_Balance_{t}")
        # 2. Solar Availability
        prob += (Qs[t] + Qsb[t] + Qge[t] <= S_av_forecast[t], f"Solar_Availability_{t}")
        # 3. Grid Limits
        prob += (Qg[t] <= C_g * yg_i[t], f"Grid_Import_Limit_{t}")
        prob += (Qge[t] <= C_g * yg_e[t], f"Grid_Export_Limit_{t}")
        # 4. Battery Limits
        prob += (Qb[t] <= C_br * yb[t], f"Bat_Discharge_Limit_{t}")
        prob += (Qsb[t] <= C_br * ysb[t], f"Bat_Charge_Limit_{t}")
        # 5. SOC Limits
        prob += (S[t] >= S_min, f"SOC_Min_{t}")
        prob += (S[t] <= C_bl, f"SOC_Max_{t}")
        # 6. Battery Logic
        prob += (ysb[t] + yb[t] <= 1, f"Bat_Logic_{t}")
        # 7. Grid Logic
        prob += (yg_i[t] + yg_e[t] <= 1, f"Grid_Logic_{t}")
        # 8. SOC Dynamics
        if t == 0:
            prob += (S[t] == S_init + eff_c * Qsb[t] - Qb[t] / eff_d, f"SOC_Update_{t}")
        else:
            prob += (S[t] == S[t-1] + eff_c * Qsb[t] - Qb[t] / eff_d, f"SOC_Update_{t}")
    return prob

def run_rule_based(D_forecast, S_av_forecast, G_b, G_s, params):
    # Parameters
    C_bl = float(params.get("C_bl", 500.0))
    C_br = float(params.get("C_br", 200.0))
    C_g = float(params.get("C_g", 300.0))
    eff_c = float(params.get("eff_c", 0.95))
    eff_d = float(params.get("eff_d", 0.95))
    S_init = float(params.get("S_init", 250.0))
    S_min = float(params.get("S_min", 50.0))
    B_d = float(params.get("B_d", 0.02))

    T = len(D_forecast)
    
    Qs_list = []
    Qsb_list = []
    Qb_list = []
    Qg_list = []
    Qge_list = []
    S_list = []
    cost = 0.0
    
    S_current = S_init
    
    for t in range(T):
        D = D_forecast[t]
        PV = S_av_forecast[t]
        
        Qs = 0.0
        Qsb = 0.0
        Qb = 0.0
        Qg = 0.0
        Qge = 0.0
        
        # Priority 1: PV to Load
        Qs = min(PV, D)
        rem_PV = PV - Qs
        rem_D = D - Qs
        
        # Priority 2: PV to Battery
        if rem_PV > 0:
            chg_space = (C_bl - S_current) / eff_c
            Qsb = min(rem_PV, C_br, chg_space)
            if Qsb < 0: Qsb = 0.0
            rem_PV -= Qsb
            
        # Priority 3: PV to Grid
        if rem_PV > 0:
            Qge = min(rem_PV, C_g)
            
        # Priority 4: Battery to Load
        if rem_D > 0:
            dis_energy = (S_current - S_min) * eff_d
            Qb = min(rem_D, C_br, dis_energy)
            if Qb < 0: Qb = 0.0
            rem_D -= Qb
            
        # Priority 5: Grid to Load
        if rem_D > 0:
            Qg = min(rem_D, C_g)
            rem_D -= Qg
            
        # Update SOC
        S_current = S_current + (eff_c * Qsb) - (Qb / eff_d)
        
        # Update Cost
        hourly_cost = (G_b[t] * Qg) - (G_s[t] * Qge) + B_d * (Qsb + Qb)
        cost += hourly_cost
        
        Qs_list.append(Qs)
        Qsb_list.append(Qsb)
        Qb_list.append(Qb)
        Qg_list.append(Qg)
        Qge_list.append(Qge)
        S_list.append(S_current)
        
    return {
        "status": "Optimal",
        "Qs": Qs_list,
        "Qsb": Qsb_list,
        "Qb": Qb_list,
        "Qg": Qg_list,
        "Qge": Qge_list,
        "S": S_list,
        "cost": cost
    }

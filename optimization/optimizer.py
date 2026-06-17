import pulp
from objective_function import build_objective_function
from constraints import add_constraints

def run_day_ahead_optimization(D_forecast, S_av_forecast, G_b, G_s, params):
    hours = list(range(len(D_forecast)))
    prob = pulp.LpProblem("Day_Ahead_Microgrid_Optimization", pulp.LpMinimize)
    
    # Continuous
    Qs  = pulp.LpVariable.dicts("Qs",  hours, lowBound=0, cat="Continuous")
    Qb  = pulp.LpVariable.dicts("Qb",  hours, lowBound=0, cat="Continuous")
    Qsb = pulp.LpVariable.dicts("Qsb", hours, lowBound=0, cat="Continuous")
    Qg  = pulp.LpVariable.dicts("Qg",  hours, lowBound=0, cat="Continuous")
    Qge = pulp.LpVariable.dicts("Qge", hours, lowBound=0, cat="Continuous")
    S   = pulp.LpVariable.dicts("S",   hours, lowBound=0, cat="Continuous")
    
    # Binary
    yb   = pulp.LpVariable.dicts("yb",   hours, cat="Binary")
    ysb  = pulp.LpVariable.dicts("ysb",  hours, cat="Binary")
    yg_i = pulp.LpVariable.dicts("yg_i", hours, cat="Binary")
    yg_e = pulp.LpVariable.dicts("yg_e", hours, cat="Binary")
    
    prob = build_objective_function(prob, Qg, Qge, Qsb, Qb, G_b, G_s, params['B_d'], hours)
    prob = add_constraints(prob, Qs, Qb, Qsb, Qg, Qge, S, yb, ysb, yg_i, yg_e,
                           D_forecast, S_av_forecast, params['C_br'], params['C_g'], params['C_bl'],
                           params['S_min'], params['S_init'], params['eff_c'], params['eff_d'], hours)
    
    solver = pulp.PULP_CBC_CMD(msg=0)
    status = prob.solve(solver)
    
    if pulp.LpStatus[status] == "Optimal":
        return {
            "status": "Optimal", "cost": pulp.value(prob.objective),
            "Qs": [Qs[t].varValue for t in hours], "Qb": [Qb[t].varValue for t in hours],
            "Qsb": [Qsb[t].varValue for t in hours], "Qg": [Qg[t].varValue for t in hours],
            "Qge": [Qge[t].varValue for t in hours], "S": [S[t].varValue for t in hours],
            "solver_info": {
                "variables": len(prob.variables()),
                "constraints": len(prob.constraints),
                "solver_used": "CBC_CMD (PuLP Default)",
                "horizon": len(hours)
            }
        }
    return {"status": pulp.LpStatus[status], "cost": None}

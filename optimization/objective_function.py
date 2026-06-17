import pulp

def build_objective_function(prob, Qg, Qge, Qsb, Qb, G_b, G_s, B_d, hours):
    # J = Sum [ G_b[t]*Qg[t] - G_s[t]*Qge[t] + B_d*(Qsb[t] + Qb[t]) ]
    prob += pulp.lpSum([
        G_b[t] * Qg[t] - G_s[t] * Qge[t] + B_d * (Qsb[t] + Qb[t])
        for t in hours
    ]), "Total_Operational_Cost"
    return prob

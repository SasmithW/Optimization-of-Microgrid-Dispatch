import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import json

# Setup paths
st.set_page_config(page_title="Microgrid Dashboard", layout="wide", initial_sidebar_state="expanded")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'shared')))
try:
    from config_loader import get_data_paths, get_parameters, load_config, save_config, get_tariff_vectors
    paths = get_data_paths()
except Exception as e:
    st.error(f"Failed to load configuration: {e}")
    st.stop()

# Helper to format hours
def format_hour(h):
    return f"{int(h):02d}:00"

def load_data():
    data = {}
    if os.path.exists(paths["day_ahead_schedule"]):
        df_sched = pd.read_csv(paths["day_ahead_schedule"])
        if 'Timestamp' in df_sched.columns:
            df_sched['Timestamp'] = pd.to_datetime(df_sched['Timestamp'])
            df_sched.set_index('Timestamp', inplace=True)
        data["schedule"] = df_sched

    if "rule_based_schedule" in paths and os.path.exists(paths["rule_based_schedule"]):
        df_rule = pd.read_csv(paths["rule_based_schedule"])
        if 'Timestamp' in df_rule.columns:
            df_rule['Timestamp'] = pd.to_datetime(df_rule['Timestamp'])
            df_rule.set_index('Timestamp', inplace=True)
        data["rule_schedule"] = df_rule

    if os.path.exists(paths["actual_pv"]):
        df_act_pv = pd.read_csv(paths["actual_pv"])
        if 'Timestamp' in df_act_pv.columns:
            df_act_pv['Timestamp'] = pd.to_datetime(df_act_pv['Timestamp'])
            df_act_pv.set_index('Timestamp', inplace=True)
        data["actual_pv"] = df_act_pv

    if os.path.exists(paths["actual_load"]):
        df_act_load = pd.read_csv(paths["actual_load"])
        if 'Timestamp' in df_act_load.columns:
            df_act_load['Timestamp'] = pd.to_datetime(df_act_load['Timestamp'])
            df_act_load.set_index('Timestamp', inplace=True)
        data["actual_load"] = df_act_load
    return data

data = load_data()

st.sidebar.title("Microgrid Dashboard")
page = st.sidebar.radio("Navigation", [
    "1. Main Overview", 
    "2. Forecast vs Actual Analysis", 
    "3. Optimization Analysis", 
    "4. Hour-by-Hour Energy Flow",
    "5. System Parameters & Settings",
    "6. Optimization Model",
    "7. Optimization Source Code",
    "8. Rule-Based Model",
    "9. Optimization vs Rule-Based Comparison"
])

if page == "5. System Parameters & Settings":
    st.header("System Parameters & Settings")
    st.markdown("Modify physical and economic parameters here. Changes will update the backend config.")
    
    config = load_config()
    params = config.get("parameters", {})
    
    st.subheader("Microgrid Physical Limits")
    col1, col2 = st.columns(2)
    with col1:
        B_d = st.number_input("Battery Degradation Cost (B_d) ($/kWh)", value=float(params.get("B_d", 0.02)), step=0.01)
        C_bl = st.number_input("Max Battery Capacity (C_bl) (kWh)", value=float(params.get("C_bl", 500.0)), step=10.0)
        C_br = st.number_input("Max Battery Power Limit (C_br) (kW)", value=float(params.get("C_br", 200.0)), step=10.0)
        S_min = st.number_input("Min Battery SOC (S_min) (kWh)", value=float(params.get("S_min", 50.0)), step=10.0)
        S_init = st.number_input("Initial Battery SOC (S_init) (kWh)", value=float(params.get("S_init", 250.0)), step=10.0)
        
    with col2:
        C_g = st.number_input("Max Grid Capacity (C_g) (kW)", value=float(params.get("C_g", 300.0)), step=10.0)
        eff_c = st.number_input("Charging Efficiency (eff_c)", value=float(params.get("eff_c", 0.95)), step=0.01, max_value=1.0)
        eff_d = st.number_input("Discharging Efficiency (eff_d)", value=float(params.get("eff_d", 0.95)), step=0.01, max_value=1.0)

    st.markdown("---")
    st.header("Time-of-Use Tariff Configuration")
    st.markdown("Configure electricity tariff periods and pricing schedules used by the optimization model.")
    
    tariff_scenarios = config.get("tariff_scenarios", {})
    scenario_names = list(tariff_scenarios.keys())
    
    selected_scenario = st.selectbox("Load Predefined Tariff Scenario", ["(Custom)"] + scenario_names)
    
    if "current_tou_prices" not in st.session_state:
        st.session_state.current_tou_prices = config.get("tou_prices", {"Off-Peak": 0.12, "Mid-Peak": 0.22, "Peak": 0.36})
    if "current_tou_schedule" not in st.session_state:
        st.session_state.current_tou_schedule = config.get("tou_schedule", [])
    if "current_export_pct" not in st.session_state:
        st.session_state.current_export_pct = float(config.get("export_percentage", 50.0))
        
    if selected_scenario != "(Custom)":
        st.session_state.current_tou_prices = tariff_scenarios[selected_scenario]["tou_prices"]
        st.session_state.current_tou_schedule = tariff_scenarios[selected_scenario]["tou_schedule"]

    st.subheader("1. Tariff Prices")
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1:
        off_p = st.number_input("Off-Peak Price (G_b) ($/kWh)", value=st.session_state.current_tou_prices["Off-Peak"], step=0.01)
    with pc2:
        mid_p = st.number_input("Mid-Peak Price (G_b) ($/kWh)", value=st.session_state.current_tou_prices["Mid-Peak"], step=0.01)
    with pc3:
        peak_p = st.number_input("Peak Price (G_b) ($/kWh)", value=st.session_state.current_tou_prices["Peak"], step=0.01)
    with pc4:
        exp_pct = st.number_input("Export Percentage (G_s multiplier) (%)", value=st.session_state.current_export_pct, step=1.0)
        
    st.session_state.current_tou_prices = {"Off-Peak": off_p, "Mid-Peak": mid_p, "Peak": peak_p}
    st.session_state.current_export_pct = exp_pct
    
    st.subheader("2. Tariff Schedule (24-Hour Coverage Required)")
    df_sched = pd.DataFrame(st.session_state.current_tou_schedule)
    edited_df = st.data_editor(df_sched, num_rows="dynamic", use_container_width=True)
    
    new_schedule = edited_df.to_dict('records')
    st.session_state.current_tou_schedule = new_schedule
    
    # Validation & Stats
    validation_passed = True
    errors = []
    
    hour_map = [-1]*24
    for idx, row in enumerate(new_schedule):
        try:
            s_hr = int(row["Start"].split(":")[0])
            e_hr = int(row["End"].split(":")[0])
            if s_hr >= e_hr:
                errors.append(f"Row {idx+1}: Start time ({row['Start']}) must be earlier than End time ({row['End']}).")
                validation_passed = False
            for h in range(s_hr, e_hr):
                if 0 <= h < 24:
                    if hour_map[h] != -1:
                        errors.append(f"Overlap detected at hour {h:02d}:00.")
                        validation_passed = False
                    else:
                        hour_map[h] = row["Period"]
        except Exception:
            errors.append(f"Row {idx+1}: Invalid time format. Use HH:00.")
            validation_passed = False
            
    missing_hours = [h for h in range(24) if hour_map[h] == -1]
    if missing_hours:
        errors.append(f"Missing schedule coverage for hours: {[f'{h:02d}:00' for h in missing_hours]}")
        validation_passed = False
        
    if not validation_passed:
        for err in set(errors):
            st.error(err)
    else:
        st.success("Tariff schedule is valid! Full 24-hour coverage achieved without overlaps.")
        
        # Stats & Preview
        t_Gb, t_Gs = get_tariff_vectors(st.session_state.current_tou_prices, new_schedule, exp_pct)
        avg_tariff = sum(t_Gb)/24
        peak_to_off = peak_p / off_p if off_p > 0 else 0
        n_peak = hour_map.count("Peak")
        n_mid = hour_map.count("Mid-Peak")
        n_off = hour_map.count("Off-Peak")
        
        st.subheader("Tariff Statistics Summary")
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Daily Avg Tariff", f"${avg_tariff:.3f}/kWh")
        sc2.metric("Peak-to-Off-Peak Ratio", f"{peak_to_off:.1f}x")
        sc3.metric("Peak Hours", f"{n_peak} hrs")
        sc4.metric("Off-Peak Hours", f"{n_off} hrs")
        
        # Timeline
        st.subheader("24-Hour Tariff Timeline")
        timeline_df = pd.DataFrame([
            {"Period": hour_map[h], "Start": f"{h:02d}:00", "Price": t_Gb[h]} for h in range(24)
        ])
        fig_time = px.bar(timeline_df, x="Start", y="Price", color="Period", 
                          color_discrete_map={"Off-Peak": "green", "Mid-Peak": "orange", "Peak": "red"})
        fig_time.update_layout(xaxis_title="Hour", yaxis_title="Price ($/kWh)", barmode="group")
        st.plotly_chart(fig_time, use_container_width=True)
        
    st.markdown("---")
    submit = st.button("Save Configuration and Rerun Optimization", disabled=not validation_passed, type="primary")
    
    if submit:
        config["parameters"]["B_d"] = B_d
        config["parameters"]["C_bl"] = C_bl
        config["parameters"]["C_br"] = C_br
        config["parameters"]["C_g"] = C_g
        config["parameters"]["S_min"] = S_min
        config["parameters"]["S_init"] = S_init
        config["parameters"]["eff_c"] = eff_c
        config["parameters"]["eff_d"] = eff_d
        
        config["tou_prices"] = st.session_state.current_tou_prices
        config["tou_schedule"] = st.session_state.current_tou_schedule
        config["export_percentage"] = st.session_state.current_export_pct
        
        save_config(config)
        st.success("Configuration saved successfully!")
        
        with st.spinner("Re-running Optimization Model & Rule-Based EMS..."):
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'optimization')))
            import main as opt_main
            success, msg = opt_main.run_optimization_pipeline()
            if success:
                st.success(f"Pipelines complete! New Optimal Cost: ${msg:.2f}. Please refresh the page.")
            else:
                st.error(f"Optimization failed: {msg}")
    st.stop()

# IF NOT SETTINGS PAGE, REQUIRE DATA
if not data.get("schedule") is not None:
    st.warning("No optimization schedule found. Please generate the schedule first.")
    st.stop()

df = data["schedule"]
act_pv_df = data.get("actual_pv")
act_load_df = data.get("actual_load")

# Timestamp-based merge
if act_pv_df is not None and not act_pv_df.empty:
    pv_col = 'Actual_PV' if 'Actual_PV' in act_pv_df.columns else act_pv_df.columns[-1]
    # Join on index (which is now Timestamp)
    df = df.join(act_pv_df[[pv_col]].rename(columns={pv_col: 'Actual_PV_kW'}), how='left')
else:
    df['Actual_PV_kW'] = pd.NA

if act_load_df is not None and not act_load_df.empty:
    load_col = 'Actual_Load' if 'Actual_Load' in act_load_df.columns else act_load_df.columns[-1]
    df = df.join(act_load_df[[load_col]].rename(columns={load_col: 'Actual_Load_kW'}), how='left')
else:
    df['Actual_Load_kW'] = pd.NA

# Check if there is actual overlap
has_actual_pv = df['Actual_PV_kW'].notna().any()
has_actual_load = df['Actual_Load_kW'].notna().any()

# Derive Flow Vectors
df['Solar_to_Grid'] = df['Grid_Export_kW']
df['Solar_to_Bat'] = df['Bat_Charge_kW']
df['Solar_to_Load'] = df['Solar_Used_kW']

df['Bat_to_Load'] = df['Bat_Discharge_kW']
df['Grid_to_Load'] = df['Grid_Import_kW']

G_b, G_s = get_tariff_vectors()
params = get_parameters()
B_d = params.get('B_d', 0.02)
df['Hourly_Cost_$'] = (df['Grid_Import_kW'] * G_b) - (df['Grid_Export_kW'] * G_s) + B_d * (df['Bat_Charge_kW'] + df['Bat_Discharge_kW'])


if page == "1. Main Overview":
    st.header("Main Overview")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Forecasted PV", f"{df['Solar_Forecast_kW'].sum():,.2f} kWh")
    act_pv_sum = df['Actual_PV_kW'].sum(skipna=True) if has_actual_pv else 0.0
    act_load_sum = df['Actual_Load_kW'].sum(skipna=True) if has_actual_load else 0.0
    col2.metric("Total Actual PV", f"{act_pv_sum:,.2f} kWh" if has_actual_pv else "N/A")
    col3.metric("Total Forecasted Load", f"{df['Demand_Forecast_kW'].sum():,.2f} kWh")
    col4.metric("Total Actual Load", f"{act_load_sum:,.2f} kWh" if has_actual_load else "N/A")
    st.markdown("---")
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Total Grid Import", f"{df['Grid_Import_kW'].sum():,.2f} kWh")
    col6.metric("Total Grid Export", f"{df['Grid_Export_kW'].sum():,.2f} kWh")
    col7.metric("Final Battery SOC", f"{df['Scheduled_SOC_kWh'].iloc[-1]:.1f} kWh")
    col8.metric("Total Operating Cost", f"${df['Hourly_Cost_$'].sum():,.2f}")

elif page == "2. Forecast vs Actual Analysis":
    st.header("Forecast vs Actual Analysis")
    st.markdown("Immediate visualization of forecasting deviations and accuracy metrics.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("PV Analysis")
        if not has_actual_pv:
            st.warning("⚠️ No overlap between Actual PV data and current Forecast timestamps. Displaying Forecast only.")
        fig_pv = go.Figure()
        fig_pv.add_trace(go.Scatter(x=df.index, y=df['Solar_Forecast_kW'], name='Forecast PV', line=dict(dash='dash', color='orange')))
        if has_actual_pv:
            fig_pv.add_trace(go.Scatter(x=df.index, y=df['Actual_PV_kW'], name='Actual PV', line=dict(color='darkorange')))
        fig_pv.update_layout(xaxis_title="Time", yaxis_title="Power (kW)", xaxis_tickangle=-45)
        st.plotly_chart(fig_pv, use_container_width=True)
        
        if has_actual_pv:
            mae_pv = (df['Actual_PV_kW'] - df['Solar_Forecast_kW']).abs().mean()
            st.metric("PV Mean Absolute Error (MAE)", f"{mae_pv:.2f} kW")
        else:
            st.metric("PV Mean Absolute Error (MAE)", "N/A")

    with col2:
        st.subheader("Load Analysis")
        if not has_actual_load:
            st.warning("⚠️ No overlap between Actual Load data and current Forecast timestamps. Displaying Forecast only.")
        fig_load = go.Figure()
        fig_load.add_trace(go.Scatter(x=df.index, y=df['Demand_Forecast_kW'], name='Forecast Load', line=dict(dash='dash', color='red')))
        if has_actual_load:
            fig_load.add_trace(go.Scatter(x=df.index, y=df['Actual_Load_kW'], name='Actual Load', line=dict(color='darkred')))
        fig_load.update_layout(xaxis_title="Time", yaxis_title="Power (kW)", xaxis_tickangle=-45)
        st.plotly_chart(fig_load, use_container_width=True)
        
        if has_actual_load:
            mae_load = (df['Actual_Load_kW'] - df['Demand_Forecast_kW']).abs().mean()
            st.metric("Load Mean Absolute Error (MAE)", f"{mae_load:.2f} kW")
        else:
            st.metric("Load Mean Absolute Error (MAE)", "N/A")
        
    st.subheader("Data Table")
    st.dataframe(df[['Solar_Forecast_kW', 'Actual_PV_kW', 'Demand_Forecast_kW', 'Actual_Load_kW']].round(2), use_container_width=True)

elif page == "3. Optimization Analysis":
    st.header("Day-Ahead Optimization Analysis")
    
    st.subheader("A. Energy Dispatch (Serving Load)")
    st.markdown("This chart clearly demonstrates the exact sources serving the required load demand.")
    fig_dispatch = go.Figure()
    fig_dispatch.add_trace(go.Bar(x=df.index, y=df['Solar_to_Load'], name='Solar -> Load', marker_color='#F59E0B'))
    fig_dispatch.add_trace(go.Bar(x=df.index, y=df['Bat_to_Load'], name='Battery -> Load', marker_color='#10B981'))
    fig_dispatch.add_trace(go.Bar(x=df.index, y=df['Grid_to_Load'], name='Grid -> Load', marker_color='#6366F1'))
    fig_dispatch.add_trace(go.Scatter(x=df.index, y=df['Demand_Forecast_kW'], name='Demand Forecast', mode='lines', line=dict(color='red', width=3)))
    fig_dispatch.update_layout(xaxis_title="Hour", yaxis_title="Power (kW)", barmode='stack', xaxis_tickangle=-45)
    st.plotly_chart(fig_dispatch, use_container_width=True)
    
    st.subheader("B. Solar Utilization Breakdown")
    st.markdown("Where does the total available solar energy go?")
    fig_solar = go.Figure()
    fig_solar.add_trace(go.Bar(x=df.index, y=df['Solar_to_Load'], name='Solar -> Load', marker_color='#F59E0B'))
    fig_solar.add_trace(go.Bar(x=df.index, y=df['Solar_to_Bat'], name='Solar -> Battery Charge', marker_color='#8B5CF6'))
    fig_solar.add_trace(go.Bar(x=df.index, y=df['Solar_to_Grid'], name='Solar -> Grid Export', marker_color='#14B8A6'))
    fig_solar.add_trace(go.Scatter(x=df.index, y=df['Solar_Forecast_kW'], name='Total Solar Available', mode='lines', line=dict(color='orange', dash='dash')))
    fig_solar.update_layout(xaxis_title="Hour", yaxis_title="Power (kW)", barmode='stack', xaxis_tickangle=-45)
    st.plotly_chart(fig_solar, use_container_width=True)
    
    st.subheader("C. Battery Operations")
    fig_bat = go.Figure()
    fig_bat.add_trace(go.Bar(x=df.index, y=df['Bat_to_Load'], name='Discharge (+)', marker_color='#10B981'))
    fig_bat.add_trace(go.Bar(x=df.index, y=-df['Bat_Charge_kW'], name='Charge (-)', marker_color='#EF4444'))
    fig_bat.add_trace(go.Scatter(x=df.index, y=df['Scheduled_SOC_kWh'], name='State of Charge', mode='lines+markers', marker_color='blue', yaxis='y2'))
    fig_bat.update_layout(yaxis_title="Power (kW)", yaxis2=dict(title="Energy (kWh)", overlaying='y', side='right', range=[0, 550]), barmode='relative', xaxis_tickangle=-45)
    st.plotly_chart(fig_bat, use_container_width=True)

elif page == "4. Hour-by-Hour Energy Flow":
    st.header("Hour-by-Hour Energy Flow")
    
    hour_idx = st.slider("Select Hour to Inspect (0-23)", 0, 23, 12)
    row = df.iloc[hour_idx]
    
    st.subheader(f"Energy Flow Sankey Diagram - Hour {hour_idx:02d}:00")
    
    # Sankey Nodes: [0: Solar, 1: Grid Import, 2: Battery Dis, 3: Load, 4: Battery Chg, 5: Grid Export]
    labels = ["Solar PV", "Grid (Import)", "Battery (Discharge)", "Load Demand", "Battery (Charge)", "Grid (Export)"]
    colors = ["#F59E0B", "#6366F1", "#10B981", "#EF4444", "#8B5CF6", "#14B8A6"]
    
    source = []
    target = []
    value = []
    
    if row['Solar_to_Load'] > 0:
        source.append(0); target.append(3); value.append(row['Solar_to_Load'])
    if row['Solar_to_Bat'] > 0:
        source.append(0); target.append(4); value.append(row['Solar_to_Bat'])
    if row['Solar_to_Grid'] > 0:
        source.append(0); target.append(5); value.append(row['Solar_to_Grid'])
    if row['Grid_to_Load'] > 0:
        source.append(1); target.append(3); value.append(row['Grid_to_Load'])
    if row['Bat_to_Load'] > 0:
        source.append(2); target.append(3); value.append(row['Bat_to_Load'])
        
    if sum(value) > 0:
        fig = go.Figure(data=[go.Sankey(
            node=dict(pad=20, thickness=30, line=dict(color="black", width=0.5), label=labels, color=colors),
            link=dict(source=source, target=target, value=value)
        )])
        fig.update_layout(title_text=f"Energy Flow at {hour_idx:02d}:00", font_size=12, height=500)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No energy flow occurring in this hour.")
        
    st.subheader("Hourly Summary Data")
    st.dataframe(df[['Solar_to_Load', 'Solar_to_Bat', 'Solar_to_Grid', 'Grid_to_Load', 'Bat_to_Load', 'Scheduled_SOC_kWh', 'Hourly_Cost_$']].round(2), use_container_width=True)

elif page == "6. Optimization Model":
    st.header("Optimization Model Formulation")
    st.markdown("Complete Mathematical formulation of the Day-Ahead Microgrid Energy Management MILP.")
    
    st.subheader("1. Nomenclature")
    
    st.markdown("### Indices and Sets")
    st.markdown("""
| Symbol | Description |
| :--- | :--- |
| $t$ | Hourly time step index |
| $T$ | Optimization horizon ($t \in \{0, 1, ..., 23\}$) |
    """)

    nom_col1, nom_col2 = st.columns(2)
    
    with nom_col1:
        st.markdown("### Parameters (Constants)")
        st.markdown("""
| Symbol | Description | Unit |
| :--- | :--- | :--- |
| $D\_forecast[t]$ | Forecasted electrical load demand at hour $t$ | kW |
| $S\_av\_forecast[t]$ | Forecasted available solar PV generation at hour $t$ | kW |
| $G\_b[t]$ | Time-of-Use Grid Import Tariff at hour $t$ | \$/kWh |
| $G\_s[t]$ | Time-of-Use Grid Export Tariff at hour $t$ | \$/kWh |
| $B\_d$ | Battery degradation cost | \$/kWh |
| $C\_bl$ | Maximum battery energy capacity | kWh |
| $C\_br$ | Maximum battery inverter power limit | kW |
| $C\_g$ | Maximum grid connection capacity (PCC Limit) | kW |
| $S\_min$ | Minimum safe battery state-of-charge | kWh |
| $S\_init$ | Initial battery state-of-charge at $t=0$ | kWh |
| $eff\_c$ | Battery charging efficiency | \% |
| $eff\_d$ | Battery discharging efficiency | \% |
        """)

    with nom_col2:
        st.markdown("### Decision Variables")
        st.markdown("""
| Symbol | Description | Type | Unit |
| :--- | :--- | :--- | :--- |
| $Qg[t]$ | Grid Import Power | Continuous | kW |
| $Qge[t]$ | Grid Export Power | Continuous | kW |
| $Qs[t]$ | Solar Power directly serving the load | Continuous | kW |
| $Qsb[t]$ | Solar Power charging the battery | Continuous | kW |
| $Qb[t]$ | Battery Discharge Power | Continuous | kW |
| $S[t]$ | Battery State of Charge (SOC) | Continuous | kWh |
| $yg\_i[t]$ | Grid Import logic state | Binary | \{0,1\} |
| $yg\_e[t]$ | Grid Export logic state | Binary | \{0,1\} |
| $yb[t]$ | Battery Discharge logic state | Binary | \{0,1\} |
| $ysb[t]$ | Battery Charge logic state | Binary | \{0,1\} |
        """)
    
    st.markdown("---")
    st.subheader("2. Objective Function")
    st.markdown("Implemented in: `optimization/objective_function.py`")
    st.latex(r"\min J = \sum_{t \in T} \Big( G\_b[t] \cdot Qg[t] - G\_s[t] \cdot Qge[t] + B\_d \cdot (Qsb[t] + Qb[t]) \Big)")
    st.info("**Meaning:** Total Cost = (Grid Import Cost) - (Grid Export Revenue) + (Battery Wear Cost)")
    st.caption("**Purpose:** Minimizes the total daily operating expenses of the microgrid.")
    
    st.markdown("---")
    st.subheader("3. Equations and Constraints")
    st.markdown("Implemented in: `optimization/constraints.py`")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**1. Power Balance**")
        st.latex(r"Qg[t] + Qs[t] + Qb[t] = D\_forecast[t]")
        st.info("**Meaning:** Grid Import + Solar to Load + Battery Discharge = Load Demand")
        st.caption("**Purpose:** Ensures the load is perfectly met every hour without shortage.")
        
        st.markdown("**2. Solar Availability**")
        st.latex(r"Qs[t] + Qsb[t] + Qge[t] \leq S\_av\_forecast[t]")
        st.info("**Meaning:** Solar to Load + Solar to Battery + Solar to Grid $\leq$ Available PV")
        st.caption("**Purpose:** Restricts solar utilization to physically available irradiance.")
        
        st.markdown("**3. Battery State-of-Charge (SOC) Dynamics**")
        st.latex(r"S[t] = S[t-1] + eff\_c \cdot Qsb[t] - \frac{Qb[t]}{eff\_d}")
        st.info("**Meaning:** Current SOC = Previous SOC + (Charge $\times$ Eff) - (Discharge / Eff)")
        st.caption("**Purpose:** Tracks energy storage accurately while accounting for thermal losses.")
        
        st.markdown("**4. Minimum and Maximum SOC Constraints**")
        st.latex(r"S\_min \leq S[t] \leq C\_bl")
        st.info("**Meaning:** Minimum Safe Energy $\leq$ Current Battery Energy $\leq$ Maximum Capacity")
        st.caption("**Purpose:** Prevents overcharging and deep depletion to protect battery health.")

    with c2:
        st.markdown("**5. Grid Connection (PCC) Constraints**")
        st.latex(r"Qg[t] \leq C\_g \cdot yg\_i[t]")
        st.latex(r"Qge[t] \leq C\_g \cdot yg\_e[t]")
        st.info("**Meaning:** Import or Export Power $\leq$ Maximum Cable Capacity ($C_g$)")
        st.caption("**Purpose:** Restricts power transfer to the physical limits of the utility grid connection.")
        
        st.markdown("**6. Grid Import/Export Logic**")
        st.latex(r"yg\_i[t] + yg\_e[t] \leq 1")
        st.info("**Meaning:** You cannot import and export at the exact same time.")
        st.caption("**Purpose:** Enforces physical exclusivity using integer binary switching.")

        st.markdown("**7. Battery Charge/Discharge Power Limits**")
        st.latex(r"Qb[t] \leq C\_br \cdot yb[t]")
        st.latex(r"Qsb[t] \leq C\_br \cdot ysb[t]")
        st.info("**Meaning:** Charge or Discharge Power $\leq$ Maximum Inverter Power ($C_{br}$)")
        st.caption("**Purpose:** Restricts hourly power flow to battery inverter specifications.")

        st.markdown("**8. Battery Charge/Discharge Logic**")
        st.latex(r"yb[t] + ysb[t] \leq 1")
        st.info("**Meaning:** You cannot charge and discharge the battery simultaneously.")
        st.caption("**Purpose:** Enforces physical exclusivity of the battery inverter.")

elif page == "7. Optimization Source Code":
    st.header("Optimization Source Code")
    st.markdown("Read-only view of the active optimization model implementation.")

    def read_file(filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        return f"# File not found: {filepath}"

    opt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'optimization'))
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    st.subheader("A. Objective Function")
    st.code(read_file(os.path.join(opt_dir, 'objective_function.py')), language='python')

    st.subheader("B. Constraints")
    st.code(read_file(os.path.join(opt_dir, 'constraints.py')), language='python')

    st.subheader("C. Optimizer / Solver Setup")
    st.code(read_file(os.path.join(opt_dir, 'optimizer.py')), language='python')

    st.subheader("D. Configuration Parameters")
    st.code(read_file(os.path.join(root_dir, 'microgrid_config.json')), language='json')

elif page == "8. Rule-Based Model":
    st.header("Rule-Based Energy Management System (RB-EMS)")
    st.markdown("This section details the heuristic logic used by the conventional benchmark controller and its resulting dispatch decisions.")
    
    st.subheader("1. Heuristic Dispatch Rules")
    
    st.info("**Priority 1: PV to Load**\nThe controller first attempts to supply all current load demand directly using available Solar PV generation.")
    
    st.info("**Priority 2: PV to Battery**\nIf Solar PV exceeds the load, the excess is immediately used to charge the battery until it reaches its maximum capacity ($C_{bl}$), respecting charge rate limits.")
    
    st.info("**Priority 3: PV to Grid**\nOnly if the battery is completely full, any remaining excess Solar PV is exported to the external grid.")
    
    st.info("**Priority 4: Battery to Load**\nIf Solar PV is insufficient to meet the load, the controller discharges the battery to cover the deficit until it hits the minimum safe SOC ($S_{min}$).")
    
    st.info("**Priority 5: Grid to Load**\nIf the load still exceeds the combination of Solar PV and Battery discharge, the remaining deficit is imported from the grid.")
    
    st.markdown("---")
    st.subheader("2. Rule-Based Dispatch Results")
    if "rule_schedule" not in data:
        st.warning("Rule-based schedule data not found. Please run the optimization pipeline.")
    else:
        df_rule = data["rule_schedule"]
        
        # Derive flow vectors for rule-based dataframe
        df_rule['Solar_to_Grid'] = df_rule['Grid_Export_kW']
        df_rule['Solar_to_Bat'] = df_rule['Bat_Charge_kW']
        df_rule['Solar_to_Load'] = df_rule['Solar_Used_kW']
        df_rule['Bat_to_Load'] = df_rule['Bat_Discharge_kW']
        df_rule['Grid_to_Load'] = df_rule['Grid_Import_kW']
        
        fig_dispatch = go.Figure()
        fig_dispatch.add_trace(go.Bar(x=df_rule.index, y=df_rule['Solar_to_Load'], name='Solar -> Load', marker_color='#F59E0B'))
        fig_dispatch.add_trace(go.Bar(x=df_rule.index, y=df_rule['Bat_to_Load'], name='Battery -> Load', marker_color='#10B981'))
        fig_dispatch.add_trace(go.Bar(x=df_rule.index, y=df_rule['Grid_to_Load'], name='Grid -> Load', marker_color='#6366F1'))
        fig_dispatch.add_trace(go.Scatter(x=df_rule.index, y=df_rule['Demand_Forecast_kW'], name='Demand Forecast', mode='lines', line=dict(color='red', width=3)))
        fig_dispatch.update_layout(title="Rule-Based Energy Dispatch", xaxis_title="Hour", yaxis_title="Power (kW)", barmode='stack', xaxis_tickangle=-45)
        st.plotly_chart(fig_dispatch, use_container_width=True)
        
        st.subheader("Rule-Based Battery Operations")
        fig_bat = go.Figure()
        fig_bat.add_trace(go.Bar(x=df_rule.index, y=df_rule['Bat_to_Load'], name='Discharge (+)', marker_color='#10B981'))
        fig_bat.add_trace(go.Bar(x=df_rule.index, y=-df_rule['Bat_Charge_kW'], name='Charge (-)', marker_color='#EF4444'))
        fig_bat.add_trace(go.Scatter(x=df_rule.index, y=df_rule['Scheduled_SOC_kWh'], name='State of Charge', mode='lines+markers', marker_color='blue', yaxis='y2'))
        fig_bat.update_layout(yaxis_title="Power (kW)", yaxis2=dict(title="Energy (kWh)", overlaying='y', side='right', range=[0, 550]), barmode='relative', xaxis_tickangle=-45)
        st.plotly_chart(fig_bat, use_container_width=True)


elif page == "9. Optimization vs Rule-Based Comparison":
    st.header("Optimization vs Rule-Based Comparison")
    st.markdown("Benchmarking the intelligent MILP Optimization against a heuristic Rule-Based EMS.")
    
    if "rule_schedule" not in data:
        st.warning("Rule-based schedule data not found. Please run the optimization pipeline to generate both schedules.")
        st.stop()
        
    df_opt = data["schedule"]
    df_rule = data["rule_schedule"]
    
    # Calculate Metrics for both
    # Optimization
    opt_cost = df_opt['Hourly_Cost_$'].sum() if 'Hourly_Cost_$' in df_opt.columns else 0 # It will be recalculated below anyway
    opt_grid_import = df_opt['Grid_Import_kW'].sum()
    opt_grid_export = df_opt['Grid_Export_kW'].sum()
    opt_total_pv = df_opt['Solar_Forecast_kW'].sum()
    opt_pv_used = df_opt['Solar_Used_kW'].sum()
    opt_pv_to_bat = df_opt['Bat_Charge_kW'].sum() if 'Solar_to_Bat' not in df_opt.columns else df_opt['Solar_to_Bat'].sum()
    
    # Wait, the rule based doesn't have Hourly_Cost_$ precalculated in the dataframe. Let's recalculate it cleanly.
    G_b, G_s = get_tariff_vectors()
    params = get_parameters()
    B_d = params.get('B_d', 0.02)
    
    df_opt['Hourly_Cost'] = (df_opt['Grid_Import_kW'] * G_b) - (df_opt['Grid_Export_kW'] * G_s) + B_d * (df_opt['Bat_Charge_kW'] + df_opt['Bat_Discharge_kW'])
    df_rule['Hourly_Cost'] = (df_rule['Grid_Import_kW'] * G_b) - (df_rule['Grid_Export_kW'] * G_s) + B_d * (df_rule['Bat_Charge_kW'] + df_rule['Bat_Discharge_kW'])
    
    opt_cost = df_opt['Hourly_Cost'].sum()
    rule_cost = df_rule['Hourly_Cost'].sum()
    
    opt_grid_import = df_opt['Grid_Import_kW'].sum()
    rule_grid_import = df_rule['Grid_Import_kW'].sum()
    
    opt_pv_self_cons = df_opt['Solar_Used_kW'].sum() - df_opt['Grid_Export_kW'].sum() # PV locally consumed
    rule_pv_self_cons = df_rule['Solar_Used_kW'].sum() - df_rule['Grid_Export_kW'].sum()
    
    total_pv = df_opt['Solar_Forecast_kW'].sum()
    opt_ren_util = (df_opt['Solar_Used_kW'].sum() / total_pv * 100) if total_pv > 0 else 0
    rule_ren_util = (df_rule['Solar_Used_kW'].sum() / total_pv * 100) if total_pv > 0 else 0
    
    savings_pct = ((rule_cost - opt_cost) / rule_cost * 100) if rule_cost != 0 else 0
    grid_red_pct = ((rule_grid_import - opt_grid_import) / rule_grid_import * 100) if rule_grid_import != 0 else 0
    ren_imp = opt_ren_util - rule_ren_util
    
    # KPI Cards
    st.subheader("High-Level Benchmark")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Optimization Cost", f"${opt_cost:.2f}")
    c2.metric("Rule-Based Cost", f"${rule_cost:.2f}")
    c3.metric("Cost Savings", f"{savings_pct:.1f}%", f"${rule_cost - opt_cost:.2f} Saved")
    c4.metric("Grid Import Reduction", f"{grid_red_pct:.1f}%", f"{rule_grid_import - opt_grid_import:.1f} kWh")
    c5.metric("Ren. Util Improvement", f"+{ren_imp:.1f}%")
    
    st.markdown("---")
    st.subheader("Comparison Charts")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Battery SOC", "Grid Import", "Grid Export", "Battery Ops", "Hourly Cost"])
    
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_opt.index, y=df_opt['Scheduled_SOC_kWh'], name='Optimization SOC', mode='lines+markers', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=df_opt.index, y=df_rule['Scheduled_SOC_kWh'], name='Rule-Based SOC', mode='lines+markers', line=dict(color='red', dash='dash')))
        fig.update_layout(title="Battery SOC vs Time", yaxis_title="State of Charge (kWh)", xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
    with tab2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_opt.index, y=df_opt['Grid_Import_kW'], name='Optimization Import', mode='lines', fill='tozeroy', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=df_opt.index, y=df_rule['Grid_Import_kW'], name='Rule-Based Import', mode='lines', line=dict(color='red', dash='dash')))
        fig.update_layout(title="Grid Import vs Time", yaxis_title="Import (kW)", xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
    with tab3:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_opt.index, y=df_opt['Grid_Export_kW'], name='Optimization Export', mode='lines', fill='tozeroy', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=df_opt.index, y=df_rule['Grid_Export_kW'], name='Rule-Based Export', mode='lines', line=dict(color='red', dash='dash')))
        fig.update_layout(title="Grid Export vs Time", yaxis_title="Export (kW)", xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
    with tab4:
        fig = go.Figure()
        # Opt
        fig.add_trace(go.Bar(x=df_opt.index, y=df_opt['Bat_Discharge_kW'], name='Opt Discharge (+)', marker_color='blue'))
        fig.add_trace(go.Bar(x=df_opt.index, y=-df_opt['Bat_Charge_kW'], name='Opt Charge (-)', marker_color='lightblue'))
        # Rule
        fig.add_trace(go.Scatter(x=df_opt.index, y=df_rule['Bat_Discharge_kW'], name='Rule Discharge', mode='lines', line=dict(color='red')))
        fig.add_trace(go.Scatter(x=df_opt.index, y=-df_rule['Bat_Charge_kW'], name='Rule Charge', mode='lines', line=dict(color='darkred')))
        fig.update_layout(title="Battery Charge/Discharge vs Time", barmode='relative', yaxis_title="Power (kW)", xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
    with tab5:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_opt.index, y=df_opt['Hourly_Cost'], name='Optimization Cost', mode='lines+markers', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=df_opt.index, y=df_rule['Hourly_Cost'], name='Rule-Based Cost', mode='lines+markers', line=dict(color='red', dash='dash')))
        fig.update_layout(title="Hourly Operating Cost vs Time", yaxis_title="Cost ($)", xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Summary Comparison Table")
    
    def calc_metrics(df):
        cost = df['Hourly_Cost'].sum()
        g_imp = df['Grid_Import_kW'].sum()
        g_exp = df['Grid_Export_kW'].sum()
        exp_rev = (df['Grid_Export_kW'] * G_s).sum()
        ren_used_total = df['Solar_Used_kW'].sum() # Qs + Qsb + Qge
        ren_self = ren_used_total - df['Grid_Export_kW'].sum() # Qs + Qsb
        tp = df['Bat_Charge_kW'].sum() + df['Bat_Discharge_kW'].sum()
        fsoc = df['Scheduled_SOC_kWh'].iloc[-1]
        
        # Peak Hour Grid Import (Assumed peak is hours 16-21, i.e., index 16 to 21 based on tariffs G_b)
        peak_mask = [G_b[i] >= 0.15 for i in range(24)]
        peak_imp = sum([df['Grid_Import_kW'].iloc[i] for i in range(24) if peak_mask[i]])
        
        # Unmet Demand (Should be 0 due to Grid import covering it)
        # Check power balance: Qs + Qb + Qg = D + Qsb + Qge -> If Qg + Qb + Qs < D, unmet > 0
        supply = df['Solar_Used_kW'] + df['Bat_Discharge_kW'] + df['Grid_Import_kW']
        unmet = (df['Demand_Forecast_kW'] - supply).clip(lower=0).sum()
        
        return [
            f"${cost:.2f}",
            f"{g_imp:.1f} kWh",
            f"{g_exp:.1f} kWh",
            f"${exp_rev:.2f}",
            f"{(ren_used_total/total_pv*100) if total_pv>0 else 0:.1f}%",
            f"{(ren_self/ren_used_total*100) if ren_used_total>0 else 0:.1f}%",
            f"{tp:.1f} kWh",
            f"{peak_imp:.1f} kWh",
            f"{fsoc:.1f} kWh",
            f"{unmet:.1f} kWh"
        ]
        
    metrics_list = [
        "Total Cost", "Grid Import", "Grid Export", "Export Revenue", 
        "Renewable Utilization", "Renewable Self Consumption", "Battery Throughput",
        "Peak-Hour Grid Import", "Final SOC", "Unmet Demand"
    ]
    
    comp_df = pd.DataFrame({
        "Metric": metrics_list,
        "Rule-Based EMS": calc_metrics(df_rule),
        "Optimization EMS": calc_metrics(df_opt)
    })
    
    st.table(comp_df)

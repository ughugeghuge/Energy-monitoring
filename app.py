import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# =====================================================================
# PAGE CONFIGURATION & UI STYLING
# =====================================================================
st.set_page_config(page_title="Enterprise Energy & Pinch Analytics", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .metric-card {
        background-color: #ffffff;
        border-radius: 6px;
        padding: 16px;
        border-left: 4px solid #2c3e50;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
        margin-bottom: 10px;
    }
    .metric-title { color: #555555; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
    .metric-value { color: #111111; font-size: 26px; font-weight: 800; }
    .metric-sub { color: #888888; font-size: 11px; margin-top: 4px; }
    .sidebar-section { font-size: 14px; font-weight: 600; color: #2c3e50; margin-top: 15px; margin-bottom: 5px; border-bottom: 1px solid #ccc; padding-bottom: 3px;}
    
    .recommendation-box { 
        background-color: #f4f6f9; 
        border-left: 4px solid #3498db; 
        padding: 20px; 
        border-radius: 5px; 
        margin-top: 20px;
        color: #2c3e50;
        white-space: normal;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    .recommendation-box h4 { color: #1f4e79 !important; margin-top: 0; font-weight: 700;}
    .recommendation-box p { font-weight: 700; color: #2c3e50; margin-top: 15px; margin-bottom: 5px;}
    .recommendation-box li { color: #333333; margin-bottom: 10px; line-height: 1.5;}
    .recommendation-box b { color: #111111; }
    .footer-watermark { position: fixed; right: 15px; bottom: 10px; font-size: 12px; color: #aaa; font-style: italic; z-index: 100;}
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="footer-watermark">prepared by- Umesh Ghuge</div>', unsafe_allow_html=True)

# =====================================================================
# GLOBAL PARAMETERS & SIDEBAR UI
# =====================================================================
st.sidebar.markdown("<div class='sidebar-section'>GLOBAL SETTINGS</div>", unsafe_allow_html=True)

col_cur, col_unit = st.sidebar.columns(2)
currency_opt = col_cur.selectbox("Currency", ["INR (₹)", "USD ($)", "EUR (€)", "GBP (£)"], index=0)
curr_sym = currency_opt.split(" ")[1].strip("()")

therm_unit = col_unit.selectbox("Thermal Unit", ["kcal/hr", "kW"], index=0)

st.sidebar.markdown("<div class='sidebar-section'>ECONOMIC FACTORS</div>", unsafe_allow_html=True)
ELEC_RATE = st.sidebar.number_input(f"Electricity Tariff ({curr_sym}/kWh)", value=8.50 if "₹" in curr_sym else 0.12, step=0.5)
FUEL_RATE = st.sidebar.number_input(f"Hot Utility Cost ({curr_sym}/{therm_unit})", value=3.00 if "₹" in curr_sym else 0.04, step=0.1)
COOL_RATE = st.sidebar.number_input(f"Cold Utility Cost ({curr_sym}/{therm_unit})", value=0.50 if "₹" in curr_sym else 0.01, step=0.1)
OP_HOURS = st.sidebar.number_input("Annual Operating Hours", value=8000, step=100)

st.sidebar.markdown("<div class='sidebar-section'>AUDIT MODULES</div>", unsafe_allow_html=True)
module = st.sidebar.radio("Select Engineering System:", [
    "Pinch Analysis & Heat Integration",
    "HVAC & Chiller Systems",
    "Cooling Tower Analytics",
    "Compressed Air Systems",
    "Lighting Retrofit Economics",
    "Plant-Wide Energy Sankey"
], label_visibility="collapsed")

# =====================================================================
# CORE ALGORITHMS
# =====================================================================
def run_pinch_algorithm(df, dt_min, cp_col):
    df_temp = df.copy()
    df_temp['T_shift_s'] = np.where(df_temp['Type'] == 'Hot', df_temp['Ts (°C)'] - dt_min/2, df_temp['Ts (°C)'] + dt_min/2)
    df_temp['T_shift_t'] = np.where(df_temp['Type'] == 'Hot', df_temp['Tt (°C)'] - dt_min/2, df_temp['Tt (°C)'] + dt_min/2)
    
    all_shifted_temps = sorted(list(set(df_temp['T_shift_s']).union(set(df_temp['T_shift_t']))), reverse=True)
    
    cascade = [0.0]
    for i in range(len(all_shifted_temps)-1):
        t_upper = all_shifted_temps[i]
        t_lower = all_shifted_temps[i+1]
        cp_sum = sum(row[cp_col] if row['Type'] == 'Hot' else -row[cp_col] 
                     for _, row in df_temp.iterrows() 
                     if max(row['T_shift_s'], row['T_shift_t']) >= t_upper and min(row['T_shift_s'], row['T_shift_t']) <= t_lower)
        cascade.append(cascade[-1] + cp_sum * (t_upper - t_lower))
        
    min_heat = min(cascade)
    qh_min = 0.0 if min_heat >= 0 else abs(min_heat)
    gcc_heat = [c + qh_min for c in cascade]
    qc_min = gcc_heat[-1]
    
    pinch_idx = gcc_heat.index(0)
    pinch_temp_shifted = all_shifted_temps[pinch_idx]
    
    total_hot_avail = sum(row[cp_col] * abs(row['Ts (°C)'] - row['Tt (°C)']) for _, row in df_temp[df_temp['Type'] == 'Hot'].iterrows())
    total_cold_req = sum(row[cp_col] * abs(row['Ts (°C)'] - row['Tt (°C)']) for _, row in df_temp[df_temp['Type'] == 'Cold'].iterrows())
    q_recovered = total_cold_req - qh_min
    
    return qh_min, qc_min, pinch_temp_shifted, q_recovered, total_hot_avail, total_cold_req, gcc_heat, all_shifted_temps

# =====================================================================
# MODULE 1: PINCH ANALYSIS (HEAT INTEGRATION)
# =====================================================================
if module == "Pinch Analysis & Heat Integration":
    st.title("Pinch Analysis & Heat Recovery Targeting")
    st.markdown("Optimize heat exchanger networks by determining minimum utility targets and optimum ΔT_min using realistic Process Models[cite: 9].")

    col1, col2 = st.columns([1, 4])
    dt_min_current = col1.number_input("Design Approach Temp (ΔT_min °C)", value=20.0, step=1.0)
    
    st.markdown("### Process Streams Definition (Realistic Preheat Train)")
    
    default_streams = pd.DataFrame({
        "Stream ID": ["Light Naphtha", "Heavy Naphtha", "Kerosene", "Diesel", "Residue", "Crude Feed"],
        "Type": ["Hot", "Hot", "Hot", "Hot", "Hot", "Cold"],
        "Ts (°C)": [120.0, 160.0, 200.0, 250.0, 350.0, 25.0],
        "Tt (°C)": [40.0, 60.0, 80.0, 60.0, 100.0, 340.0],
        f"CP ({therm_unit}/°C)": [25.0, 30.0, 20.0, 40.0, 60.0, 120.0]
    })
    
    streams_df = st.data_editor(
        default_streams,
        column_config={"Type": st.column_config.SelectboxColumn(options=["Hot", "Cold"], required=True)},
        num_rows="dynamic", use_container_width=True
    )

    with st.expander("📐 View Mathematical Models & Capital Cost Parameters"):
        st.latex(r"Q_{interval} = \sum CP_{hot} \Delta T - \sum CP_{cold} \Delta T")
        st.latex(r"T_{shift} = T \pm \frac{\Delta T_{min}}{2}")
        st.latex(r"Total Cost = \left( Q_{HU} \cdot C_{HU} + Q_{CU} \cdot C_{CU} \right) \cdot \text{Hours} + CapEx_{annualized}")
        st.latex(r"Area \approx \frac{Q_{recovered}}{U \cdot \Delta T_{min}}")
        st.markdown("**Economic Parameters for Cost Optimization Curve:**")
        cc1, cc2, cc3 = st.columns(3)
        u_val = cc1.number_input(f"Avg Heat Transfer Coeff U ({therm_unit}/m²°C)", value=0.5)
        cost_m2 = cc2.number_input(f"Heat Exchanger Cost ({curr_sym}/m²)", value=5000.0)
        af = cc3.number_input("Annualization Factor (CapEx)", value=0.2)

    if st.button("Execute Rigorous Pinch Optimization", type="primary"):
        with st.spinner("Processing thermodynamic cascade and cost optimizations..."):
            cp_col = f"CP ({therm_unit}/°C)"
            
            # Run Base Case
            qh_min, qc_min, p_shift, q_rec, t_hot_avail, t_cold_req, gcc_heat, all_shifted_temps = run_pinch_algorithm(streams_df, dt_min_current, cp_col)
            pinch_hot = p_shift + dt_min_current/2
            pinch_cold = p_shift - dt_min_current/2

            current_opex = (qh_min * FUEL_RATE + qc_min * COOL_RATE) * OP_HOURS
            unintegrated_opex = (t_cold_req * FUEL_RATE + t_hot_avail * COOL_RATE) * OP_HOURS
            annual_savings = unintegrated_opex - current_opex

            mc1, mc2, mc3 = st.columns(3)
            mc1.markdown(f"<div class='metric-card' style='border-left-color:#e74c3c;'><div class='metric-title'>Target Hot Utility (QH)</div><div class='metric-value'>{qh_min:,.0f} {therm_unit}</div><div class='metric-sub'>Unintegrated Req: {t_cold_req:,.0f} {therm_unit}</div></div>", unsafe_allow_html=True)
            mc2.markdown(f"<div class='metric-card' style='border-left-color:#3498db;'><div class='metric-title'>Target Cold Utility (QC)</div><div class='metric-value'>{qc_min:,.0f} {therm_unit}</div><div class='metric-sub'>Unintegrated Req: {t_hot_avail:,.0f} {therm_unit}</div></div>", unsafe_allow_html=True)
            mc3.markdown(f"<div class='metric-card' style='border-left-color:#2ecc71;'><div class='metric-title'>Process Heat Recovered</div><div class='metric-value'>{q_rec:,.0f} {therm_unit}</div><div class='metric-sub'>Avoided OpEx: {curr_sym}{annual_savings:,.0f}/yr</div></div>", unsafe_allow_html=True)

            # --- GRAPH 1: Composite Curves (T-H) ---
            def get_composite(stream_type):
                sub_df = streams_df[streams_df['Type'] == stream_type]
                temps = sorted(list(set(sub_df['Ts (°C)']).union(set(sub_df['Tt (°C)']))))
                H_vals = [0.0]
                for i in range(len(temps)-1):
                    t1, t2 = temps[i], temps[i+1]
                    cp_sum = sum(r[cp_col] for _, r in sub_df.iterrows() if max(r['Ts (°C)'], r['Tt (°C)']) >= t2 and min(r['Ts (°C)'], r['Tt (°C)']) <= t1)
                    H_vals.append(H_vals[-1] + cp_sum * (t2 - t1))
                return temps, H_vals

            t_hot, h_hot = get_composite('Hot')
            t_cold, h_cold = get_composite('Cold')
            h_hot_aligned = [h + qc_min for h in h_hot] 
            
            fig_cc = go.Figure()
            fig_cc.add_trace(go.Scatter(x=h_hot_aligned, y=t_hot, mode='lines', name='Hot Composite Curve', line=dict(color='#e74c3c', width=3)))
            fig_cc.add_trace(go.Scatter(x=h_cold, y=t_cold, mode='lines', name='Cold Composite Curve', line=dict(color='#3498db', width=3)))
            
            h_pinch = h_hot_aligned[np.argmin(np.abs(np.array(t_hot) - pinch_hot))]
            fig_cc.add_annotation(x=h_pinch, y=pinch_hot, text=f"Pinch (ΔT = {dt_min_current}°C)", showarrow=True, arrowhead=2, arrowcolor="#2c3e50")
            fig_cc.update_layout(title="Temperature vs. Enthalpy (Composite Curves)[cite: 9]", xaxis_title=f"Enthalpy Ḣ ({therm_unit})", yaxis_title="Temperature T (°C)", template="plotly_white", height=450)
            st.plotly_chart(fig_cc, use_container_width=True)

            # --- GRAPH 2: Grand Composite Curve (GCC) ---
            fig_gcc = go.Figure()
            fig_gcc.add_trace(go.Scatter(x=gcc_heat, y=all_shifted_temps, mode='lines+markers', name='GCC', line=dict(color='#8e44ad', width=3)))
            fig_gcc.add_hline(y=pinch_temp_shifted, line_dash="dash", line_color="gray", annotation_text=f"Pinch ({pinch_temp_shifted}°C Shifted)")
            fig_gcc.update_layout(title="Grand Composite Curve (GCC)", xaxis_title=f"Net Heat Flow ({therm_unit})", yaxis_title="Shifted Temperature (°C)", template="plotly_white", height=450)
            st.plotly_chart(fig_gcc, use_container_width=True)

            # --- GRAPH 3: Cost Optimization vs Delta T_min ---
            dt_range = np.linspace(5, 40, 30)
            opex_list, capex_list, total_list = [], [], []
            
            for dt in dt_range:
                qh, qc, p_s, qr, _, _, _, _ = run_pinch_algorithm(streams_df, dt, cp_col)
                op_cost = (qh * FUEL_RATE + qc * COOL_RATE) * OP_HOURS
                area = qr / (u_val * dt) + (qh / (u_val * 30)) + (qc / (u_val * 20)) if dt > 0 else 0
                cap_cost = (area * cost_m2) * af
                
                opex_list.append(op_cost)
                capex_list.append(cap_cost)
                total_list.append(op_cost + cap_cost)

            opt_idx = np.argmin(total_list)
            dt_opt = dt_range[opt_idx]

            fig_cost = go.Figure()
            fig_cost.add_trace(go.Scatter(x=dt_range, y=total_list, mode='lines', name='Total Costs', line=dict(color='#2c3e50', width=3)))
            fig_cost.add_trace(go.Scatter(x=dt_range, y=opex_list, mode='lines', name='Operating Costs', line=dict(color='#e74c3c', width=2, dash='dash')))
            fig_cost.add_trace(go.Scatter(x=dt_range, y=capex_list, mode='lines', name='Capital Costs', line=dict(color='#3498db', width=2, dash='dash')))
            
            fig_cost.add_vline(x=dt_opt, line_dash="dot", line_color="green", annotation_text=f"Optimum ΔT_min = {dt_opt:.1f}°C")
            fig_cost.update_layout(title="Economic Optimization: Cost vs. ΔT_min[cite: 9]", xaxis_title="ΔT_min (°C)", yaxis_title=f"Annualized Cost ({curr_sym}/yr)", template="plotly_white", height=450)
            st.plotly_chart(fig_cost, use_container_width=True)

            st.markdown(f"""
            <div class='recommendation-box'>
                <h4 style='margin-top:0;'>📊 Expert Analytical Conclusions</h4>
                
                <p>1. The Significance of the Composite Curves</p>
                <ul>
                    <li>The <b>Temperature-Enthalpy (T-H) Composite Curve</b> visually maps the maximum possible internal heat recovery (Q_recovery)[cite: 9]. The region where the red and blue curves overlap horizontally represents process-to-process heat exchange that requires <b>zero external fuel</b>[cite: 9].</li>
                    <li>The horizontal gap at the top right of the curve indicates your absolute <b>Minimum Hot Utility Requirement (Q_HU)</b> of {qh_min:,.0f} {therm_unit}[cite: 9]. The gap at the bottom left is your <b>Minimum Cold Utility (Q_CU)</b> of {qc_min:,.0f} {therm_unit}[cite: 9].</li>
                </ul>

                <p>2. The Golden Rules of Pinch Violations</p>
                <ul>
                    <li>The Pinch Point occurs at exactly <b>{pinch_hot:.1f}°C for Hot streams</b> and <b>{pinch_cold:.1f}°C for Cold streams</b>. This defines the thermodynamic bottleneck of your plant.</li>
                    <li><b>Rule 1:</b> Do NOT transfer heat across the pinch. If an existing heat exchanger transfers X units of heat from a stream above {pinch_hot}°C to a stream below {pinch_cold}°C, your total plant utility consumption will increase by X for both hot and cold utilities.</li>
                    <li><b>Rule 2:</b> Do not use external Cooling Utilities above the pinch. Above the pinch is a heat sink; cooling should only be done by cold process streams.</li>
                    <li><b>Rule 3:</b> Do not use external Heating Utilities below the pinch. Below the pinch is a heat source; it possesses excess heat that must be rejected.</li>
                </ul>

                <p>3. Financial Impact & Optimization</p>
                <ul>
                    <li>The <b>Cost vs. ΔT_min Curve</b> resolves the fundamental trade-off in process design[cite: 9].</li>
                    <li>As ΔT_min increases, <b>Capital Costs</b> drop exponentially because higher driving forces require smaller heat exchanger areas[cite: 9]. However, <b>Operating Costs</b> rise linearly because less heat is recovered, forcing higher boiler and cooling tower loads[cite: 9].</li>
                    <li>The rigorous optimization engine has determined your global <b>Total Cost Minimum occurs at a ΔT_min of {dt_opt:.1f}°C</b>[cite: 9]. Adjusting your design approach from {dt_min_current}°C to {dt_opt:.1f}°C will minimize your annualized lifecycle costs.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

# =====================================================================
# MODULE 2: HVAC & CHILLERS
# =====================================================================
elif module == "HVAC & Chiller Systems":
    st.title("Advanced HVAC & Chiller Analytics")
    
    with st.expander("📐 View Mathematical Models & Formulas"):
        st.latex(r"Cooling Load (TR) = \frac{Flow (m^3/hr) \times \Delta T \times 4.187 \times 1000}{3600 \times 3.517}")
        st.latex(r"COP = \frac{Cooling Capacity (kW)}{Input Power (kW)} \quad | \quad Carnot COP = \frac{T_{evap}}{T_{cond} - T_{evap}}")

    c1, c2, c3, c4 = st.columns(4)
    flow = c1.number_input("Chilled Water Flow (m³/h)", value=150.0)
    t_in = c2.number_input("CHW Return Temp (°C)", value=12.0)
    t_out = c3.number_input("CHW Supply Temp (°C)", value=7.0)
    t_cond = c4.number_input("Condenser Water Temp (°C)", value=32.0)
    power = st.number_input("Compressor Input Power (kW)", value=120.0)
    
    tr = (flow * 1000 / 3600) * 4.187 * (t_in - t_out) / 3.517
    cop = (tr * 3.517) / power if power > 0 else 0
    kw_tr = power / tr if tr > 0 else 0
    
    carnot_cop = (t_out + 273.15) / ((t_cond + 273.15) - (t_out + 273.15)) if t_cond != t_out else 0
    carnot_eff = (cop / carnot_cop) * 100 if carnot_cop > 0 else 0
    
    mc1, mc2, mc3 = st.columns(3)
    mc1.markdown(f"<div class='metric-card'><div class='metric-title'>Operating Load</div><div class='metric-value'>{tr:.1f} TR</div><div class='metric-sub'>Specific Energy: {kw_tr:.3f} kW/TR</div></div>", unsafe_allow_html=True)
    mc2.markdown(f"<div class='metric-card'><div class='metric-title'>Operating COP</div><div class='metric-value'>{cop:.2f}</div><div class='metric-sub'>Theoretical Max: {carnot_cop:.2f}</div></div>", unsafe_allow_html=True)
    mc3.markdown(f"<div class='metric-card'><div class='metric-title'>Carnot Efficiency</div><div class='metric-value'>{carnot_eff:.1f} %</div><div class='metric-sub'>Deviation from ideal cycle</div></div>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class='recommendation-box'>
        <h4 style='margin-top:0;'>📊 Expert Analytical Conclusions</h4>
        <ul>
            <li><b>Current Baseline:</b> At {kw_tr:.2f} kW/TR, your chiller is operating at {carnot_eff:.1f}% of its theoretical Carnot potential. Typical modern variable-speed centrifugal chillers achieve 0.55 - 0.65 kW/TR.</li>
            <li><b>Actionable Step:</b> Clean condenser tubes. A fouling factor increase of just 0.0005 can increase compressor power by 10%.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# =====================================================================
# MODULE 3: COOLING TOWERS
# =====================================================================
elif module == "Cooling Tower Analytics":
    st.title("Cooling Tower & Heat Rejection Analytics")
    
    with st.expander("📐 View Mathematical Models & Formulas"):
        st.latex(r"Range = T_{hot} - T_{cold} \quad | \quad Approach = T_{cold} - T_{WBT}")
        st.latex(r"Effectiveness (\%) = \frac{Range}{Range + Approach} \times 100")

    c1, c2, c3, c4 = st.columns(4)
    t_in = c1.number_input("Hot Water Return (°C)", value=40.0)
    t_out = c2.number_input("Cold Water Supply (°C)", value=32.0)
    wbt = c3.number_input("Ambient WBT (°C)", value=28.0)
    flow = c4.number_input("Circulation Rate (m³/h)", value=1000.0)
    
    if t_out <= wbt:
        st.error("Cold Water Temp cannot be lower than or equal to Wet Bulb Temp (WBT).")
    else:
        rng = t_in - t_out
        app = t_out - wbt
        eff = (rng / (rng + app)) * 100
        evap = 0.00085 * 1.8 * flow * rng
        blowdown = evap / (3.0 - 1)
        makeup = evap + blowdown
        
        mc1, mc2, mc3 = st.columns(3)
        mc1.markdown(f"<div class='metric-card'><div class='metric-title'>Effectiveness</div><div class='metric-value'>{eff:.1f} %</div><div class='metric-sub'>Approach: {app:.1f} °C</div></div>", unsafe_allow_html=True)
        mc2.markdown(f"<div class='metric-card'><div class='metric-title'>Evaporative Loss</div><div class='metric-value'>{evap:.1f} m³/h</div><div class='metric-sub'>Pure water lost to atmosphere</div></div>", unsafe_allow_html=True)
        mc3.markdown(f"<div class='metric-card'><div class='metric-title'>Required Make-Up</div><div class='metric-value'>{makeup:.1f} m³/h</div><div class='metric-sub'>Evaporation + Blowdown (3 COC)</div></div>", unsafe_allow_html=True)

        st.markdown(f"""
        <div class='recommendation-box'>
            <h4 style='margin-top:0;'>📊 Expert Analytical Conclusions</h4>
            <ul>
                <li><b>Approach Analysis:</b> Your current approach is {app:.1f}°C. Industrial towers are designed for a 3-5°C approach. If your approach is higher than 5°C, inspect the fill media for scaling/fouling or verify fan blade pitch angles.</li>
                <li><b>Water Conservation:</b> You are consuming {makeup*OP_HOURS:,.0f} m³ of fresh water annually. Increasing your Cycles of Concentration (COC) through automated blowdown controllers and advanced polymers can significantly reduce this intake.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

# =====================================================================
# MODULE 4: COMPRESSED AIR
# =====================================================================
elif module == "Compressed Air Systems":
    st.title("Compressed Air Leakage Analytics")
    
    with st.expander("📐 View Mathematical Models & Formulas"):
        st.latex(r"Leakage (\%) = \frac{T_{load}}{T_{load} + T_{unload}} \times 100")
        st.latex(r"Leakage (CFM) = Capacity_{cfm} \times \frac{Leakage (\%)}{100}")

    c1, c2, c3, c4 = st.columns(4)
    cap_cfm = c1.number_input("Compressor Capacity (CFM)", value=500.0)
    power_kw = c2.number_input("Motor Power (kW)", value=75.0)
    t_on = c3.number_input("Load Time (secs)", value=15.0)
    t_off = c4.number_input("Unload Time (secs)", value=45.0)
    
    l_pct = (t_on / (t_on + t_off)) * 100
    spec_power = power_kw / cap_cfm
    p_lost = (cap_cfm * (l_pct / 100)) * spec_power
    annual_loss_cost = p_lost * OP_HOURS * ELEC_RATE
    
    mc1, mc2, mc3 = st.columns(3)
    mc1.markdown(f"<div class='metric-card'><div class='metric-title'>Specific Power</div><div class='metric-value'>{spec_power:.3f} kW/CFM</div><div class='metric-sub'>Benchmark: 0.15 - 0.18 kW/CFM</div></div>", unsafe_allow_html=True)
    mc2.markdown(f"<div class='metric-card'><div class='metric-title'>System Leakage</div><div class='metric-value'>{l_pct:.1f} %</div><div class='metric-sub'>BEE Standard: < 10%</div></div>", unsafe_allow_html=True)
    mc3.markdown(f"<div class='metric-card'><div class='metric-title'>Financial Bleed</div><div class='metric-value'>{curr_sym}{annual_loss_cost:,.0f}</div><div class='metric-sub'>Annual cost of leaks</div></div>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class='recommendation-box'>
        <h4 style='margin-top:0;'>📊 Expert Analytical Conclusions</h4>
        <ul>
            <li><b>Leakage Impact:</b> The network is leaking {l_pct:.1f}% of generated air, bleeding <b>{curr_sym}{annual_loss_cost:,.0f}</b> per year. Implement an ultrasonic leak detection survey immediately. Target reducing leakage to under 10%.</li>
            <li><b>Pressure Reduction:</b> For every 1 bar (14.5 psi) reduction in header pressure, compressor power consumption decreases by approximately 7%. Ensure point-of-use regulators are utilized rather than over-pressurizing the entire central header.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# =====================================================================
# MODULE 5: LIGHTING RETROFIT
# =====================================================================
elif module == "Lighting Retrofit Economics":
    st.title("Lighting Replacement Economics")
    
    with st.expander("📐 View Mathematical Models & Formulas"):
        st.latex(r"Annual Savings = (kW_{existing} - kW_{proposed}) \times Hours \times Tariff")
        st.latex(r"ROI (Months) = \frac{Total Capex}{Annual Savings} \times 12")

    c1, c2, c3 = st.columns(3)
    qty = c1.number_input("Total Fixtures Count", value=1000)
    old_w = c2.number_input("Legacy Fixture Draw (W)", value=40)
    new_w = c3.number_input("Proposed LED Draw (W)", value=15)
    
    c4, c5 = st.columns(2)
    led_cost = c4.number_input(f"Unit LED Capex ({curr_sym})", value=10.0)
    install_cost = c5.number_input(f"Unit Install Opex ({curr_sym})", value=2.0)
    
    old_kw = (qty * old_w) / 1000
    new_kw = (qty * new_w) / 1000
    saved_kw = old_kw - new_kw
    
    annual_savings = saved_kw * OP_HOURS * ELEC_RATE
    total_capex = qty * (led_cost + install_cost)
    roi_months = (total_capex / annual_savings) * 12 if annual_savings > 0 else 0
    
    mc1, mc2, mc3 = st.columns(3)
    mc1.markdown(f"<div class='metric-card'><div class='metric-title'>Demand Contraction</div><div class='metric-value'>{saved_kw:.1f} kW</div><div class='metric-sub'>From {old_kw:.1f}kW to {new_kw:.1f}kW</div></div>", unsafe_allow_html=True)
    mc2.markdown(f"<div class='metric-card'><div class='metric-title'>Total Capital Outlay</div><div class='metric-value'>{curr_sym}{total_capex:,.0f}</div><div class='metric-sub'>Including installation</div></div>", unsafe_allow_html=True)
    mc3.markdown(f"<div class='metric-card'><div class='metric-title'>Payback Period</div><div class='metric-value'>{roi_months:.1f} Mo</div><div class='metric-sub'>Annual savings: {curr_sym}{annual_savings:,.0f}</div></div>", unsafe_allow_html=True)

    st.markdown(f"""
    <div class='recommendation-box'>
        <h4 style='margin-top:0;'>📊 Expert Analytical Conclusions</h4>
        <ul>
            <li><b>Financial Viability:</b> With a simple payback period of {roi_months:.1f} months, this retrofit is highly attractive. Any ROI under 24 months is generally considered an immediate-action operational priority.</li>
            <li><b>Maintenance Offsets:</b> LEDs possess a lifespan of ~50,000 hours compared to legacy lifespans of 8,000-15,000 hours. This calculation does not yet include the avoided replacement/labor costs, meaning your actual ROI will be even faster.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# =====================================================================
# MODULE 6: COMBINED ANALYTICS
# =====================================================================
elif module == "Plant-Wide Energy Sankey":
    st.title("Macro Energy Flow & Optimization")
    st.markdown("Visualize whole-plant energy distribution using advanced Sankey diagrams.")
    
    st.markdown("### Sub-System Electrical Loads (kW)")
    c1, c2, c3, c4 = st.columns(4)
    chiller_kw = c1.number_input("HVAC/Chillers", value=800)
    comp_kw = c2.number_input("Compressed Air", value=300)
    light_kw = c3.number_input("Lighting", value=150)
    pump_kw = c4.number_input("Pumps & Fans", value=400)
    
    total_kw = chiller_kw + comp_kw + light_kw + pump_kw
    total_bill = total_kw * OP_HOURS * ELEC_RATE
    
    mc1, mc2, mc3 = st.columns(3)
    mc1.markdown(f"<div class='metric-card'><div class='metric-title'>Aggregate Load</div><div class='metric-value'>{total_kw:,.0f} kW</div></div>", unsafe_allow_html=True)
    mc2.markdown(f"<div class='metric-card'><div class='metric-title'>Annual Consumption</div><div class='metric-value'>{(total_kw * OP_HOURS)/1e6:.2f} GWh</div></div>", unsafe_allow_html=True)
    mc3.markdown(f"<div class='metric-card'><div class='metric-title'>Aggregate OpEx Bill</div><div class='metric-value'>{curr_sym}{total_bill:,.0f}</div></div>", unsafe_allow_html=True)
    
    chiller_loss = chiller_kw * 0.15
    comp_loss = comp_kw * 0.85 
    light_loss = light_kw * 0.60
    pump_loss = pump_kw * 0.30
    
    fig = go.Figure(data=[go.Sankey(
        node = dict(
          pad = 15, thickness = 20, line = dict(color = "black", width = 0.5),
          label = ["Grid Power", "HVAC/Chillers", "Compressed Air", "Lighting", "Pumps", "Useful Energy", "Friction & Heat Losses"],
          color = ["#2c3e50", "#3498db", "#9b59b6", "#f1c40f", "#2ecc71", "#1abc9c", "#e74c3c"]
        ),
        link = dict(
          source = [0, 0, 0, 0,  1, 1,  2, 2,  3, 3,  4, 4], 
          target = [1, 2, 3, 4,  5, 6,  5, 6,  5, 6,  5, 6],
          value =  [chiller_kw, comp_kw, light_kw, pump_kw, 
                    chiller_kw-chiller_loss, chiller_loss, comp_kw-comp_loss, comp_loss, light_kw-light_loss, light_loss, pump_kw-pump_loss, pump_loss]
      ))])

    fig.update_layout(title_text="Plant Electromechanical Energy Flow Mapping", font_size=12, height=450, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"""
    <div class='recommendation-box'>
        <h4 style='margin-top:0;'>📊 Expert Analytical Conclusions</h4>
        <ul>
            <li><b>Compressor Dominance:</b> Note the massive proportion of compressed air energy routed to "Losses" (Red line). Compressed air is an incredibly inefficient utility (~10-15% mechanical efficiency). Evaluate replacing pneumatic tools with direct electric drives where feasible.</li>
            <li><b>Base Load Optimization:</b> Your plant is drawing {total_kw} kW. Target a 5% baseline reduction via operational housekeeping (turning off idle equipment, repairing leaks, cleaning heat exchange surfaces), which will yield an immediate, zero-capex saving of <b>{curr_sym}{(total_bill*0.05):,.0f}</b> per year.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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
    .metric-title { color: #555; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
    .metric-value { color: #111; font-size: 26px; font-weight: 800; }
    .metric-sub { color: #888; font-size: 11px; margin-top: 4px; }
    .sidebar-section { font-size: 14px; font-weight: 600; color: #2c3e50; margin-top: 15px; margin-bottom: 5px; border-bottom: 1px solid #ccc; padding-bottom: 3px;}
    .footer-watermark { position: fixed; right: 15px; bottom: 10px; font-size: 12px; color: #aaa; font-style: italic; z-index: 100;}
    .recommendation-box { background-color: #f4f6f9; border-left: 4px solid #3498db; padding: 15px; border-radius: 5px; margin-top: 20px;}
    </style>
""", unsafe_allow_html=True)

# Footer Watermark
st.markdown('<div class="footer-watermark">prepared by- Umesh Ghuge</div>', unsafe_allow_html=True)

# =====================================================================
# GLOBAL PARAMETERS & SIDEBAR UI
# =====================================================================
st.sidebar.markdown("<div class='sidebar-section'>GLOBAL SETTINGS</div>", unsafe_allow_html=True)

col_cur, col_unit = st.sidebar.columns(2)
currency_opt = col_cur.selectbox("Currency", ["INR (₹)", "USD ($)", "EUR (€)", "GBP (£)"])
curr_sym = currency_opt.split(" ")[1].strip("()")

therm_unit = col_unit.selectbox("Thermal Unit", ["kW", "kcal/hr"])

st.sidebar.markdown("<div class='sidebar-section'>ECONOMIC FACTORS</div>", unsafe_allow_html=True)
ELEC_RATE = st.sidebar.number_input(f"Electricity Tariff ({curr_sym}/kWh)", value=8.50 if "₹" in curr_sym else 0.12, step=0.5)
FUEL_RATE = st.sidebar.number_input(f"Thermal Cost ({curr_sym}/{therm_unit})", value=3.00 if "₹" in curr_sym else 0.04, step=0.1)
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
# MODULE 1: PINCH ANALYSIS (HEAT INTEGRATION)
# =====================================================================
if module == "Pinch Analysis & Heat Integration":
    st.title("Pinch Analysis & Heat Recovery Targeting")
    st.markdown("Determine Minimum Utility Targets and generate Process Composite Curves to optimize thermodynamic networks.")

    col1, col2 = st.columns([1, 4])
    dt_min = col1.number_input("Min Approach Temp (ΔT_min °C)", value=10.0, step=1.0)
    
    st.markdown("### Process Streams Definition")
    default_streams = pd.DataFrame({
        "Stream ID": ["Hot 1", "Hot 2", "Cold 1", "Cold 2"],
        "Type": ["Hot", "Hot", "Cold", "Cold"],
        "Ts (°C)": [170.0, 150.0, 20.0, 80.0],
        "Tt (°C)": [60.0, 30.0, 135.0, 140.0],
        f"CP ({therm_unit}/°C)": [3.0, 1.5, 2.0, 4.0]
    })
    
    streams_df = st.data_editor(
        default_streams,
        column_config={"Type": st.column_config.SelectboxColumn(options=["Hot", "Cold"], required=True)},
        num_rows="dynamic", use_container_width=True
    )

    with st.expander("📐 View Mathematical Models & Formulas"):
        st.latex(r"Q_{interval} = \sum_{i} CP_i \times (T_{upper} - T_{lower})")
        st.latex(r"T_{hot, shift} = T_{hot} - \frac{\Delta T_{min}}{2} \quad | \quad T_{cold, shift} = T_{cold} + \frac{\Delta T_{min}}{2}")
        st.markdown("- **Problem Table Algorithm**: Shifts temperatures to a common basis, calculates net enthalpy surplus/deficit per temperature interval, and cascades heat downward to find the exact pinch point where heat flow is zero.")

    if st.button("Execute Pinch Algorithm", type="primary"):
        with st.spinner("Cascading heat flows..."):
            df = streams_df.copy()
            cp_col = f"CP ({therm_unit}/°C)"
            
            df['T_shift_s'] = np.where(df['Type'] == 'Hot', df['Ts (°C)'] - dt_min/2, df['Ts (°C)'] + dt_min/2)
            df['T_shift_t'] = np.where(df['Type'] == 'Hot', df['Tt (°C)'] - dt_min/2, df['Tt (°C)'] + dt_min/2)
            
            all_shifted_temps = sorted(list(set(df['T_shift_s']).union(set(df['T_shift_t']))), reverse=True)
            
            cascade = [0.0]
            for i in range(len(all_shifted_temps)-1):
                t_upper = all_shifted_temps[i]
                t_lower = all_shifted_temps[i+1]
                cp_sum = 0.0
                for _, row in df.iterrows():
                    high_t = max(row['T_shift_s'], row['T_shift_t'])
                    low_t = min(row['T_shift_s'], row['T_shift_t'])
                    if high_t >= t_upper and low_t <= t_lower:
                        cp_sum += row[cp_col] if row['Type'] == 'Hot' else -row[cp_col]
                q_interval = cp_sum * (t_upper - t_lower)
                cascade.append(cascade[-1] + q_interval)
                
            min_heat = min(cascade)
            qh_min = 0.0 if min_heat >= 0 else abs(min_heat)
            
            gcc_heat = [c + qh_min for c in cascade]
            qc_min = gcc_heat[-1]
            
            pinch_idx = gcc_heat.index(0)
            pinch_temp_shifted = all_shifted_temps[pinch_idx]
            pinch_hot = pinch_temp_shifted + dt_min/2
            pinch_cold = pinch_temp_shifted - dt_min/2

            mc1, mc2, mc3 = st.columns(3)
            mc1.markdown(f"<div class='metric-card' style='border-left-color:#e74c3c;'><div class='metric-title'>Min Hot Utility (QH)</div><div class='metric-value'>{qh_min:,.1f} {therm_unit}</div><div class='metric-sub'>Annual Cost: {curr_sym}{qh_min*OP_HOURS*FUEL_RATE:,.0f}</div></div>", unsafe_allow_html=True)
            mc2.markdown(f"<div class='metric-card' style='border-left-color:#3498db;'><div class='metric-title'>Min Cold Utility (QC)</div><div class='metric-value'>{qc_min:,.1f} {therm_unit}</div><div class='metric-sub'>Cooling below pinch</div></div>", unsafe_allow_html=True)
            mc3.markdown(f"<div class='metric-card' style='border-left-color:#9b59b6;'><div class='metric-title'>Pinch Temperature</div><div class='metric-value'>{pinch_hot:.1f}°C / {pinch_cold:.1f}°C</div><div class='metric-sub'>Hot Pinch / Cold Pinch</div></div>", unsafe_allow_html=True)

            # Composite Curves
            def get_composite(stream_type):
                sub_df = df[df['Type'] == stream_type]
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
            fig_cc.update_layout(title="Composite Curves (T-H Diagram)", xaxis_title=f"Enthalpy ({therm_unit})", yaxis_title="Actual Temperature (°C)", template="plotly_white", margin=dict(l=40, r=40, t=40, b=40))
            st.plotly_chart(fig_cc, use_container_width=True)

            # Grand Composite Curve
            fig_gcc = go.Figure()
            fig_gcc.add_trace(go.Scatter(x=gcc_heat, y=all_shifted_temps, mode='lines+markers', name='GCC', line=dict(color='#8e44ad', width=3), marker=dict(size=6)))
            fig_gcc.add_hline(y=pinch_temp_shifted, line_dash="dash", line_color="gray", annotation_text=f"Pinch ({pinch_temp_shifted}°C Shifted)")
            fig_gcc.update_layout(title="Grand Composite Curve (GCC)", xaxis_title=f"Net Heat Flow ({therm_unit})", yaxis_title="Shifted Temperature (°C)", template="plotly_white", margin=dict(l=40, r=40, t=40, b=40))
            st.plotly_chart(fig_gcc, use_container_width=True)

            st.markdown(f"""
            <div class='recommendation-box'>
                <h4 style='margin-top:0;'>📊 Expert Conclusions & Recommendations</h4>
                <ul>
                    <li><b>Utility Targets:</b> The absolute minimum energy required to run this process is <b>{qh_min:.1f} {therm_unit}</b> of heating and <b>{qc_min:.1f} {therm_unit}</b> of cooling. Achieving this requires a perfectly integrated Heat Exchanger Network (HEN).</li>
                    <li><b>Pinch Violation Warning:</b> Do <b>NOT</b> transfer heat across the pinch point ({pinch_hot}°C Hot / {pinch_cold}°C Cold). Any cross-pinch heat transfer will result in a double penalty, increasing both your hot and cold utility demands by the exact amount transferred.</li>
                    <li><b>Utility Selection (GCC):</b> Review the Grand Composite Curve (bottom graph) to select appropriate utility levels. If the curve opens widely at the top, you may be able to substitute expensive high-pressure steam with cheaper low-grade thermal utilities.</li>
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
        st.markdown("- **Specific Power**: Lower kW/TR indicates a more efficient chiller. Typical modern water-cooled chillers range from 0.55 to 0.65 kW/TR.")

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
    
    st.markdown("### 🎛️ Dynamic Setpoint Optimization")
    opt_t_out = st.slider("Optimize Chilled Water Supply Setpoint (°C)", min_value=float(t_out), max_value=float(t_out)+5.0, value=float(t_out)+1.5, step=0.5)
    
    eff_gain_pct = (opt_t_out - t_out) * 3.0
    new_kw_tr = kw_tr * (1 - eff_gain_pct/100)
    annual_savings = (kw_tr - new_kw_tr) * tr * OP_HOURS * ELEC_RATE
    
    fig = go.Figure()
    fig.add_trace(go.Indicator(mode="number+delta", value=new_kw_tr, title={"text": "Projected kW/TR"}, delta={'reference': kw_tr, 'relative': False, 'position': "bottom"}, domain={'row': 0, 'column': 0}))
    fig.add_trace(go.Indicator(mode="number", value=annual_savings, number={'prefix': curr_sym}, title={"text": "Annual Financial Savings"}, domain={'row': 0, 'column': 1}))
    fig.update_layout(grid={'rows': 1, 'columns': 2, 'pattern': "independent"}, height=250)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"""
    <div class='recommendation-box'>
        <h4 style='margin-top:0;'>📊 Expert Conclusions & Recommendations</h4>
        <ul>
            <li><b>Current Baseline:</b> At {kw_tr:.2f} kW/TR, your chiller is operating at {carnot_eff:.1f}% of its theoretical Carnot potential.</li>
            <li><b>Setpoint Adjustments:</b> Elevating the chilled water setpoint from {t_out}°C to {opt_t_out}°C yields an estimated {eff_gain_pct:.1f}% reduction in compressor work, saving <b>{curr_sym}{annual_savings:,.0f}</b> annually. Verify if air handling units (AHUs) can satisfy space cooling loads at the elevated supply temperature.</li>
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
        st.latex(r"Evaporation Loss = 0.00085 \times 1.8 \times Flow \times Range")
        st.markdown("- **Cycles of Concentration (COC)** dictates blowdown requirements. A higher COC saves water but requires superior chemical treatment.")

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
            <h4 style='margin-top:0;'>📊 Expert Conclusions & Recommendations</h4>
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
        st.markdown("- Conducted during non-production hours. The compressor only loads to replenish air lost to network leaks.")

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
        <h4 style='margin-top:0;'>📊 Expert Conclusions & Recommendations</h4>
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
        <h4 style='margin-top:0;'>📊 Expert Conclusions & Recommendations</h4>
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
    st.markdown("Visualize whole-plant energy distribution using advanced Sankey diagrams to identify primary thermodynamic and electrical bleeds.")
    
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
    
    # Realistic Energy Loss Assumptions based on BEE
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
        <h4 style='margin-top:0;'>📊 Expert Conclusions & Recommendations</h4>
        <ul>
            <li><b>Compressor Dominance:</b> Note the massive proportion of compressed air energy routed to "Losses" (Red line). Compressed air is an incredibly inefficient utility (~10-15% mechanical efficiency). Evaluate replacing pneumatic tools with direct electric drives where feasible.</li>
            <li><b>Base Load Optimization:</b> Your plant is drawing {total_kw} kW. Target a 5% baseline reduction via operational housekeeping (turning off idle equipment, repairing leaks, cleaning heat exchange surfaces), which will yield an immediate, zero-capex saving of <b>{curr_sym}{(total_bill*0.05):,.0f}</b> per year.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

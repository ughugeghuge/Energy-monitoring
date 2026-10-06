import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.interpolate import interp1d

# =====================================================================
# PAGE CONFIGURATION & UI STYLING
# =====================================================================
st.set_page_config(page_title="Enterprise Energy & Pinch Analytics", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .metric-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 20px;
        border-left: 6px solid #1f77b4;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-top: 1px solid #f0f0f0;
        border-right: 1px solid #f0f0f0;
        border-bottom: 1px solid #f0f0f0;
    }
    .metric-title { color: #7f8c8d; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
    .metric-value { color: #2c3e50; font-size: 28px; font-weight: 800; }
    .metric-sub { color: #95a5a6; font-size: 12px; margin-top: 5px; }
    </style>
""", unsafe_allow_html=True)

def add_plotly_watermark(fig):
    fig.add_annotation(
        text="prepared by- Umesh Ghuge", xref="paper", yref="paper",
        x=1.0, y=-0.15, showarrow=False, font=dict(size=10, color="lightgray", family="italic"),
        xanchor="right", yanchor="top"
    )
    return fig

# =====================================================================
# GLOBAL PARAMETERS
# =====================================================================
st.sidebar.title("Global Parameters")
ELEC_RATE = st.sidebar.number_input("Electricity Tariff ($/kWh or ₹/kWh)", value=0.12, step=0.01)
FUEL_RATE = st.sidebar.number_input("Thermal Energy Cost ($/kW or ₹/kW)", value=0.04, step=0.01)
OP_HOURS = st.sidebar.number_input("Annual Operating Hours", value=8000, step=100)

st.sidebar.markdown("---")
st.sidebar.title("Audit Modules")
module = st.sidebar.radio("Select Engineering System:", [
    "🔥 Pinch Analysis (Heat Integration)",
    "🏢 HVAC & Chiller Systems",
    "🏭 Cooling Towers",
    "💨 Compressed Air Systems",
    "💡 Lighting Retrofit Analytics",
    "📈 Plant Combined Analytics (Sankey)"
])

# =====================================================================
# MODULE 1: PINCH ANALYSIS (HEAT INTEGRATION)
# =====================================================================
if module == "🔥 Pinch Analysis (Heat Integration)":
    st.title("Pinch Analysis & Heat Recovery Targeting")
    st.markdown("Determine Minimum Hot Utility (QH), Minimum Cold Utility (QC), and generate Composite Curves for process heat integration based on rigorous thermodynamic cascading.")

    col1, col2 = st.columns([1, 4])
    dt_min = col1.number_input("Min Approach Temp (ΔT_min °C)", value=10.0, step=1.0, help="Minimum allowable temperature difference for heat transfer.")
    
    st.markdown("### Process Streams Definition")
    st.info("💡 **Tip:** Add streams via the `+` button. Enter Heat Capacity Flow Rate (CP) in kW/°C. (CP = Mass Flow × Specific Heat)")
    
    default_streams = pd.DataFrame({
        "Stream ID": ["Hot 1", "Hot 2", "Cold 1", "Cold 2"],
        "Type": ["Hot", "Hot", "Cold", "Cold"],
        "Ts (°C)": [170.0, 150.0, 20.0, 80.0],
        "Tt (°C)": [60.0, 30.0, 135.0, 140.0],
        "CP (kW/°C)": [3.0, 1.5, 2.0, 4.0]
    })
    
    streams_df = st.data_editor(
        default_streams,
        column_config={"Type": st.column_config.SelectboxColumn(options=["Hot", "Cold"], required=True)},
        num_rows="dynamic", use_container_width=True
    )

    if st.button("Execute Pinch Algorithm", type="primary"):
        with st.spinner("Cascading heat flows and compiling composite curves..."):
            df = streams_df.copy()
            
            # Shift Temperatures
            df['T_shift_s'] = np.where(df['Type'] == 'Hot', df['Ts'] - dt_min/2, df['Ts'] + dt_min/2)
            df['T_shift_t'] = np.where(df['Type'] == 'Hot', df['Tt'] - dt_min/2, df['Tt'] + dt_min/2)
            
            # Extract unique shifted temperatures
            all_shifted_temps = sorted(list(set(df['T_shift_s']).union(set(df['T_shift_t']))), reverse=True)
            
            # Problem Table Algorithm (Cascade)
            cascade = [0.0]
            for i in range(len(all_shifted_temps)-1):
                t_upper = all_shifted_temps[i]
                t_lower = all_shifted_temps[i+1]
                
                cp_sum = 0.0
                for _, row in df.iterrows():
                    high_t = max(row['T_shift_s'], row['T_shift_t'])
                    low_t = min(row['T_shift_s'], row['T_shift_t'])
                    if high_t >= t_upper and low_t <= t_lower:
                        cp_sum += row['CP'] if row['Type'] == 'Hot' else -row['CP']
                        
                q_interval = cp_sum * (t_upper - t_lower)
                cascade.append(cascade[-1] + q_interval)
                
            min_heat = min(cascade)
            qh_min = 0.0 if min_heat >= 0 else abs(min_heat)
            
            gcc_heat = [c + qh_min for c in cascade]
            qc_min = gcc_heat[-1]
            pinch_temp_shifted = all_shifted_temps[gcc_heat.index(0)]
            pinch_hot = pinch_temp_shifted + dt_min/2
            pinch_cold = pinch_temp_shifted - dt_min/2

            # Metrics
            mc1, mc2, mc3 = st.columns(3)
            mc1.markdown(f"<div class='metric-card' style='border-left-color:#e74c3c;'><div class='metric-title'>Minimum Hot Utility (QH)</div><div class='metric-value'>{qh_min:.1f} kW</div><div class='metric-sub'>Heating required above pinch</div></div>", unsafe_allow_html=True)
            mc2.markdown(f"<div class='metric-card' style='border-left-color:#3498db;'><div class='metric-title'>Minimum Cold Utility (QC)</div><div class='metric-value'>{qc_min:.1f} kW</div><div class='metric-sub'>Cooling required below pinch</div></div>", unsafe_allow_html=True)
            mc3.markdown(f"<div class='metric-card' style='border-left-color:#9b59b6;'><div class='metric-title'>Pinch Temperature</div><div class='metric-value'>{pinch_hot:.1f}°C / {pinch_cold:.1f}°C</div><div class='metric-sub'>Hot Pinch / Cold Pinch</div></div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- Grand Composite Curve (GCC) Plot ---
            fig_gcc = go.Figure()
            fig_gcc.add_trace(go.Scatter(x=gcc_heat, y=all_shifted_temps, mode='lines+markers', name='GCC', line=dict(color='#8e44ad', width=3)))
            fig_gcc.add_hline(y=pinch_temp_shifted, line_dash="dash", line_color="gray", annotation_text=f"Pinch ({pinch_temp_shifted}°C Shifted)")
            fig_gcc.update_layout(title="Grand Composite Curve (GCC)", xaxis_title="Net Heat Flow (kW)", yaxis_title="Shifted Temperature (°C)", height=500, template="plotly_white")
            fig_gcc = add_plotly_watermark(fig_gcc)
            
            # --- Composite Curves (CC) Algorithm ---
            def get_composite(stream_type):
                sub_df = df[df['Type'] == stream_type]
                temps = sorted(list(set(sub_df['Ts']).union(set(sub_df['Tt']))))
                H_vals = [0.0]
                for i in range(len(temps)-1):
                    t1, t2 = temps[i], temps[i+1]
                    cp_sum = sum(r['CP'] for _, r in sub_df.iterrows() if max(r['Ts'], r['Tt']) >= t2 and min(r['Ts'], r['Tt']) <= t1)
                    H_vals.append(H_vals[-1] + cp_sum * (t2 - t1))
                return temps, H_vals

            t_hot, h_hot = get_composite('Hot')
            t_cold, h_cold = get_composite('Cold')
            
            # Align Curves to satisfy minimum utility constraints
            h_hot_aligned = [h + qc_min for h in h_hot] 
            
            fig_cc = go.Figure()
            fig_cc.add_trace(go.Scatter(x=h_hot_aligned, y=t_hot, mode='lines', name='Hot Composite Curve', line=dict(color='#e74c3c', width=3)))
            fig_cc.add_trace(go.Scatter(x=h_cold, y=t_cold, mode='lines', name='Cold Composite Curve', line=dict(color='#3498db', width=3)))
            
            # Add Delta T Min Indicators
            fig_cc.update_layout(title="Hot & Cold Composite Curves (T-H Diagram)", xaxis_title="Enthalpy (kW)", yaxis_title="Actual Temperature (°C)", height=500, template="plotly_white")
            fig_cc = add_plotly_watermark(fig_cc)
            
            col_chart1, col_chart2 = st.columns(2)
            col_chart1.plotly_chart(fig_cc, use_container_width=True)
            col_chart2.plotly_chart(fig_gcc, use_container_width=True)

# =====================================================================
# MODULE 2: HVAC & CHILLERS
# =====================================================================
elif module == "🏢 HVAC & Chiller Systems":
    st.title("Advanced HVAC & Chiller Analytics")
    st.markdown("Evaluate Carnot efficiency, Integrated Part Load Value (IPLV), and specific power optimization.")
    
    c1, c2, c3, c4 = st.columns(4)
    flow = c1.number_input("Chilled Water Flow (m³/h)", value=150.0)
    t_in = c2.number_input("CHW Return Temp (°C)", value=12.0)
    t_out = c3.number_input("CHW Supply Temp (°C)", value=7.0)
    t_cond = c4.number_input("Condenser Water Temp (°C)", value=32.0, help="Used for Carnot theoretical max efficiency.")
    
    power = st.number_input("Compressor Input Power (kW)", value=120.0)
    
    # Thermodynamics
    tr = (flow * 1000 / 3600) * 4.187 * (t_in - t_out) / 3.517
    cop = (tr * 3.517) / power if power > 0 else 0
    kw_tr = power / tr if tr > 0 else 0
    
    carnot_cop = (t_out + 273.15) / ((t_cond + 273.15) - (t_out + 273.15))
    carnot_eff = (cop / carnot_cop) * 100 if carnot_cop > 0 else 0
    
    mc1, mc2, mc3 = st.columns(3)
    mc1.markdown(f"<div class='metric-card'><div class='metric-title'>Operating Load</div><div class='metric-value'>{tr:.1f} TR</div><div class='metric-sub'>Specific Energy: {kw_tr:.3f} kW/TR</div></div>", unsafe_allow_html=True)
    mc2.markdown(f"<div class='metric-card'><div class='metric-title'>Operating COP</div><div class='metric-value'>{cop:.2f}</div><div class='metric-sub'>Theoretical Max: {carnot_cop:.2f}</div></div>", unsafe_allow_html=True)
    mc3.markdown(f"<div class='metric-card'><div class='metric-title'>Carnot Efficiency</div><div class='metric-value'>{carnot_eff:.1f} %</div><div class='metric-sub'>Deviation from ideal cycle</div></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🎛️ Dynamic Setpoint Optimization Analytics")
    opt_t_out = st.slider("Optimize Chilled Water Supply Setpoint (°C)", min_value=float(t_out), max_value=float(t_out)+5.0, value=float(t_out)+1.5, step=0.5)
    
    # Approx 3% efficiency gain per 1°C elevation in CHWS
    eff_gain_pct = (opt_t_out - t_out) * 3.0
    new_kw_tr = kw_tr * (1 - eff_gain_pct/100)
    annual_savings = (kw_tr - new_kw_tr) * tr * OP_HOURS * ELEC_RATE
    
    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode = "number+delta", value = new_kw_tr,
        title = {"text": "Projected kW/TR"},
        delta = {'reference': kw_tr, 'relative': True, 'position': "bottom"},
        domain = {'row': 0, 'column': 0}))
    fig.add_trace(go.Indicator(
        mode = "number", value = annual_savings, number={'prefix': "$"},
        title = {"text": "Annual Financial Savings"},
        domain = {'row': 0, 'column': 1}))
    fig.update_layout(grid = {'rows': 1, 'columns': 2, 'pattern': "independent"}, height=250)
    st.plotly_chart(fig, use_container_width=True)

# =====================================================================
# MODULE 3: COOLING TOWERS
# =====================================================================
elif module == "🏭 Cooling Towers":
    st.title("Cooling Tower & Heat Rejection Analytics")
    st.markdown("Calculate critical approach boundaries, L/G ratios, and specific evaporation losses.")
    
    c1, c2, c3, c4 = st.columns(4)
    t_in = c1.number_input("Hot Water Return (°C)", value=40.0)
    t_out = c2.number_input("Cold Water Supply (°C)", value=32.0)
    wbt = c3.number_input("Ambient WBT (°C)", value=28.0)
    flow = c4.number_input("Circulation Rate (m³/h)", value=1000.0)
    
    fan_kw = st.number_input("Fan Motor Power (kW)", value=45.0)
    
    if t_out <= wbt:
        st.error("Cold Water Temp cannot be lower than or equal to Wet Bulb Temp (WBT).")
    else:
        rng = t_in - t_out
        app = t_out - wbt
        eff = (rng / (rng + app)) * 100
        evap = 0.00085 * 1.8 * flow * rng
        blowdown = evap / (3.0 - 1) # Assumes 3 COC
        makeup = evap + blowdown
        
        mc1, mc2, mc3 = st.columns(3)
        mc1.markdown(f"<div class='metric-card'><div class='metric-title'>Effectiveness & Approach</div><div class='metric-value'>{eff:.1f} %</div><div class='metric-sub'>Approach: {app:.1f} °C (Design typically 3-4°C)</div></div>", unsafe_allow_html=True)
        mc2.markdown(f"<div class='metric-card'><div class='metric-title'>Water Consumption</div><div class='metric-value'>{makeup:.1f} m³/h</div><div class='metric-sub'>Evaporation: {evap:.1f} m³/h | Blowdown: {blowdown:.1f} m³/h</div></div>", unsafe_allow_html=True)
        mc3.markdown(f"<div class='metric-card'><div class='metric-title'>Specific Fan Power</div><div class='metric-value'>{fan_kw/flow:.3f} kW/(m³/h)</div><div class='metric-sub'>BEE standard baseline</div></div>", unsafe_allow_html=True)

        fig = px.pie(values=[evap, blowdown, flow-makeup], names=['Evaporative Loss', 'Drift & Blowdown', 'Circulating Core'], title="Hydraulic Mass Balance", hole=0.5, color_discrete_sequence=['#3498db', '#e74c3c', '#bdc3c7'])
        fig = add_plotly_watermark(fig)
        st.plotly_chart(fig, use_container_width=True)

# =====================================================================
# MODULE 4: COMPRESSED AIR
# =====================================================================
elif module == "💨 Compressed Air Systems":
    st.title("Compressed Air Analytics & Specific Power")
    st.markdown("Assess network leakage losses, specific power boundaries, and pressure optimization curves.")
    
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
    mc1.markdown(f"<div class='metric-card'><div class='metric-title'>Specific Power Profile</div><div class='metric-value'>{spec_power:.3f} kW/CFM</div><div class='metric-sub'>Benchmark: 0.15 - 0.18 kW/CFM</div></div>", unsafe_allow_html=True)
    mc2.markdown(f"<div class='metric-card'><div class='metric-title'>Leakage Quantum</div><div class='metric-value'>{l_pct:.1f} %</div><div class='metric-sub'>BEE Accepted Norm: < 10%</div></div>", unsafe_allow_html=True)
    mc3.markdown(f"<div class='metric-card'><div class='metric-title'>Financial Bleed</div><div class='metric-value'>${annual_loss_cost:,.0f}</div><div class='metric-sub'>Annual cost of unrectified leaks</div></div>", unsafe_allow_html=True)
    
    st.markdown("### 🎛️ Pressure Setpoint Optimization")
    st.markdown("BEE Rule of Thumb: For every 1 bar (14.5 psi) reduction in generation pressure, power drops by ~6-8%.")
    pressure_drop = st.slider("Reduce Discharge Pressure by (bar)", min_value=0.0, max_value=2.0, value=0.5, step=0.1)
    
    pwr_save = power_kw * (pressure_drop * 0.07) # using 7% average
    mon_save = pwr_save * OP_HOURS * ELEC_RATE
    st.success(f"Optimizing discharge pressure saves an additional **${mon_save:,.2f}** annually.")

# =====================================================================
# MODULE 5: LIGHTING RETROFIT
# =====================================================================
elif module == "💡 Lighting Retrofit Analytics":
    st.title("Lighting Network Economics")
    st.markdown("Calculate deep ROI analysis for legacy-to-LED transitions including maintenance offsets.")
    
    c1, c2, c3 = st.columns(3)
    qty = c1.number_input("Total Fixtures Count", value=1000)
    old_w = c2.number_input("Legacy Fixture Draw (W)", value=40)
    new_w = c3.number_input("Proposed LED Draw (W)", value=15)
    
    c4, c5 = st.columns(2)
    led_cost = c4.number_input("Unit LED Capex ($/₹)", value=10.0)
    install_cost = c5.number_input("Unit Installation Opex ($/₹)", value=2.0)
    
    old_kw = (qty * old_w) / 1000
    new_kw = (qty * new_w) / 1000
    saved_kw = old_kw - new_kw
    
    annual_savings = saved_kw * OP_HOURS * ELEC_RATE
    total_capex = qty * (led_cost + install_cost)
    roi_months = (total_capex / annual_savings) * 12 if annual_savings > 0 else 0
    
    mc1, mc2, mc3 = st.columns(3)
    mc1.markdown(f"<div class='metric-card'><div class='metric-title'>Demand Contraction</div><div class='metric-value'>{saved_kw:.1f} kW</div><div class='metric-sub'>From {old_kw:.1f}kW to {new_kw:.1f}kW</div></div>", unsafe_allow_html=True)
    mc2.markdown(f"<div class='metric-card'><div class='metric-title'>Total Capital Outlay</div><div class='metric-value'>${total_capex:,.0f}</div><div class='metric-sub'>Including installation overhead</div></div>", unsafe_allow_html=True)
    mc3.markdown(f"<div class='metric-card'><div class='metric-title'>Simple Payback Period</div><div class='metric-value'>{roi_months:.1f} Mo</div><div class='metric-sub'>Rapid ROI investment grade</div></div>", unsafe_allow_html=True)

    fig = go.Figure(go.Waterfall(
        name="Energy", orientation="v", measure=["relative", "relative", "total"],
        x=["Current Basline", "LED Avoidance", "Optimized State"], textposition="outside",
        text=[f"{old_kw} kW", f"-{saved_kw} kW", f"{new_kw} kW"], y=[old_kw, -saved_kw, new_kw],
        connector={"line":{"color":"#7f8c8d"}},
        decreasing={"marker":{"color":"#2ecc71"}}, increasing={"marker":{"color":"#e74c3c"}}, totals={"marker":{"color":"#3498db"}}
    ))
    fig.update_layout(title="Load Contraction Waterfall", showlegend=False, height=450, template="plotly_white")
    fig = add_plotly_watermark(fig)
    st.plotly_chart(fig, use_container_width=True)

# =====================================================================
# MODULE 6: COMBINED ANALYTICS
# =====================================================================
elif module == "📈 Plant Combined Analytics (Sankey)":
    st.title("Macro Energy Flow & Optimization")
    st.markdown("Visualize whole-plant energy distribution using advanced Sankey diagrams to identify primary thermodynamic and electrical bleeds.")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Sub-System Electrical Loads (kW)**")
    chiller_kw = st.sidebar.slider("HVAC & Chillers", 100, 2000, 800)
    comp_kw = st.sidebar.slider("Compressed Air", 50, 1000, 300)
    light_kw = st.sidebar.slider("Lighting Network", 10, 500, 150)
    pump_kw = st.sidebar.slider("Process Pumping", 50, 1500, 400)
    
    total_kw = chiller_kw + comp_kw + light_kw + pump_kw
    total_bill = total_kw * OP_HOURS * ELEC_RATE
    
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='metric-card'><div class='metric-title'>Aggregate Plant Load</div><div class='metric-value'>{total_kw:,.0f} kW</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='metric-title'>Annual TWh Consumed</div><div class='metric-value'>{(total_kw * OP_HOURS)/1e6:.2f} GWh</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='metric-title'>Aggregate OpEx Bill</div><div class='metric-value'>${total_bill:,.0f}</div></div>", unsafe_allow_html=True)
    
    st.markdown("### Energy Flow Diagnostics (Sankey Diagram)")
    
    # Realistic Energy Loss Assumptions based on BEE
    chiller_loss = chiller_kw * 0.15
    comp_loss = comp_kw * 0.85 # Compressors generate mostly heat
    light_loss = light_kw * 0.60
    pump_loss = pump_kw * 0.30
    
    useful_chiller = chiller_kw - chiller_loss
    useful_comp = comp_kw - comp_loss
    useful_light = light_kw - light_loss
    useful_pump = pump_kw - pump_loss
    
    total_loss = chiller_loss + comp_loss + light_loss + pump_loss

    fig = go.Figure(data=[go.Sankey(
        node = dict(
          pad = 15, thickness = 20, line = dict(color = "black", width = 0.5),
          label = ["Grid Power", "HVAC/Chillers", "Compressed Air", "Lighting", "Pumps", "Useful Energy", "Thermodynamic/Friction Losses"],
          color = ["#2c3e50", "#3498db", "#9b59b6", "#f1c40f", "#2ecc71", "#1abc9c", "#e74c3c"]
        ),
        link = dict(
          source = [0, 0, 0, 0,  1, 1,  2, 2,  3, 3,  4, 4], # Grid to systems, systems to useful/loss
          target = [1, 2, 3, 4,  5, 6,  5, 6,  5, 6,  5, 6],
          value =  [chiller_kw, comp_kw, light_kw, pump_kw, 
                    useful_chiller, chiller_loss, useful_comp, comp_loss, useful_light, light_loss, useful_pump, pump_loss]
      ))])

    fig.update_layout(title_text="Plant Electromechanical Energy Flow Mapping", font_size=12, height=500, template="plotly_white")
    fig = add_plotly_watermark(fig)
    st.plotly_chart(fig, use_container_width=True)

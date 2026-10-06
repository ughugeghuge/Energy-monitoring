import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# =====================================================================
# PAGE CONFIGURATION & UI STYLING
# =====================================================================
st.set_page_config(page_title="Enterprise Energy Audit Suite", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for modern dashboard styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #1f77b4;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    .metric-title { color: #555; font-size: 14px; font-weight: 600; margin-bottom: 5px; }
    .metric-value { color: #111; font-size: 24px; font-weight: bold; }
    .bee-note { font-size: 12px; color: #7f8c8d; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# Global Economic Constants
st.sidebar.header("Global Parameters")
ELEC_RATE = st.sidebar.number_input("Electricity Rate ($/kWh or ₹/kWh)", value=0.12, step=0.01)
OP_HOURS = st.sidebar.number_input("Annual Operating Hours", value=8000, step=100)

# =====================================================================
# BEE CALCULATION ENGINES
# =====================================================================

def calc_chiller_performance(flow_m3_h, t_in, t_out, power_kw):
    """BEE Book 3: HVAC & Refrigeration System Performance"""
    cp_water = 4.187 # kJ/kg°C
    density_water = 1000 # kg/m3
    mass_flow_kg_s = (flow_m3_h * density_water) / 3600
    
    cooling_kw = mass_flow_kg_s * cp_water * (t_in - t_out)
    cooling_tr = cooling_kw / 3.517
    
    cop = cooling_kw / power_kw if power_kw > 0 else 0
    kw_per_tr = power_kw / cooling_tr if cooling_tr > 0 else 0
    
    return cooling_tr, cop, kw_per_tr

def calc_cooling_tower(t_in, t_out, wbt, flow_m3_h):
    """BEE Book 3: Cooling Tower Performance"""
    range_ct = t_in - t_out
    approach_ct = t_out - wbt
    effectiveness = (range_ct / (range_ct + approach_ct)) * 100 if (range_ct + approach_ct) > 0 else 0
    
    # Evaporation Loss = 0.00085 * 1.8 * Circulation Rate * Range (Empirical BEE formula)
    evap_loss_m3_h = 0.00085 * 1.8 * flow_m3_h * range_ct
    cycles_of_conc = 3.0 # Assumption for standard industrial CT
    blowdown_m3_h = evap_loss_m3_h / (cycles_of_conc - 1)
    makeup_m3_h = evap_loss_m3_h + blowdown_m3_h
    
    return range_ct, approach_ct, effectiveness, evap_loss_m3_h, makeup_m3_h

def calc_compressor_leakage(t_on, t_off, capacity_cfm, power_kw):
    """BEE Book 3: Compressed Air System Leakage Test"""
    leakage_percent = (t_on / (t_on + t_off)) * 100 if (t_on + t_off) > 0 else 0
    leakage_cfm = capacity_cfm * (leakage_percent / 100)
    spec_power = power_kw / capacity_cfm if capacity_cfm > 0 else 0
    power_lost_kw = leakage_cfm * spec_power
    return leakage_percent, leakage_cfm, power_lost_kw

def calc_lighting_retrofit(qty, old_w, new_w):
    """BEE Book 3: Lighting System Energy Saving"""
    old_kw = (qty * old_w) / 1000
    new_kw = (qty * new_w) / 1000
    saved_kw = old_kw - new_kw
    return old_kw, new_kw, saved_kw

# =====================================================================
# UI NAVIGATION
# =====================================================================
st.sidebar.markdown("---")
st.sidebar.title("Audit Modules")
module = st.sidebar.radio("Select System:", [
    "🏢 HVAC & Chiller Systems",
    "🏭 Cooling Towers",
    "💨 Compressed Air Systems",
    "💡 Lighting Retrofit Analytics",
    "📈 Plant Combined Analytics (What-If)"
])

# =====================================================================
# MODULE 1: HVAC & CHILLERS
# =====================================================================
if module == "🏢 HVAC & Chiller Systems":
    st.title("Chiller Performance & Energy Analytics")
    st.markdown("Assess specific energy consumption (kW/TR) and baseline performance against BEE benchmarks.")
    
    c1, c2, c3, c4 = st.columns(4)
    flow = c1.number_input("Chilled Water Flow (m³/h)", value=150.0)
    t_in = c2.number_input("Return Temp (°C)", value=12.0)
    t_out = c3.number_input("Supply Temp (°C)", value=7.0)
    power = c4.number_input("Compressor Power (kW)", value=120.0)
    
    tr, cop, kw_tr = calc_chiller_performance(flow, t_in, t_out, power)
    
    st.markdown("### Current Performance Profile")
    mc1, mc2, mc3 = st.columns(3)
    mc1.markdown(f"<div class='metric-card'><div class='metric-title'>Cooling Load (TR)</div><div class='metric-value'>{tr:.1f} TR</div></div>", unsafe_allow_html=True)
    mc2.markdown(f"<div class='metric-card'><div class='metric-title'>Coefficient of Performance (COP)</div><div class='metric-value'>{cop:.2f}</div></div>", unsafe_allow_html=True)
    mc3.markdown(f"<div class='metric-card'><div class='metric-title'>Specific Energy Consumption</div><div class='metric-value'>{kw_tr:.3f} kW/TR</div></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🎛️ What-If Analysis: Setpoint Optimization")
    st.markdown("Raising the chilled water setpoint typically improves chiller efficiency by ~2-3% per °C (BEE thumb rule).")
    
    target_kw_tr = st.slider("Target kW/TR Improvement", min_value=0.400, max_value=kw_tr, value=kw_tr*0.9, step=0.01)
    
    current_annual_cost = power * OP_HOURS * ELEC_RATE
    new_power = tr * target_kw_tr
    new_annual_cost = new_power * OP_HOURS * ELEC_RATE
    savings = current_annual_cost - new_annual_cost
    
    st.success(f"**Potential Annual Savings:** ${savings:,.2f} / ₹{savings:,.2f} by optimizing to {target_kw_tr:.3f} kW/TR.")
    
    fig = go.Figure(data=[
        go.Bar(name='Current Cost', x=['Annual Cost'], y=[current_annual_cost], marker_color='#E74C3C'),
        go.Bar(name='Optimized Cost', x=['Annual Cost'], y=[new_annual_cost], marker_color='#2ECC71')
    ])
    fig.update_layout(title_text="Cost Reduction Potential", barmode='group', height=400)
    st.plotly_chart(fig, use_container_width=True)

# =====================================================================
# MODULE 2: COOLING TOWERS
# =====================================================================
elif module == "🏭 Cooling Towers":
    st.title("Cooling Tower Thermal Efficacy")
    st.markdown("Evaluate approach, range, effectiveness, and water consumption dynamics.")
    
    c1, c2, c3, c4 = st.columns(4)
    t_in = c1.number_input("Hot Water In (°C)", value=40.0)
    t_out = c2.number_input("Cold Water Out (°C)", value=32.0)
    wbt = c3.number_input("Ambient WBT (°C)", value=28.0)
    flow = c4.number_input("Circulation Rate (m³/h)", value=1000.0)
    
    if t_out <= wbt:
        st.error("Cold Water Temp cannot be lower than or equal to Wet Bulb Temp (WBT).")
    else:
        rng, app, eff, evap, makeup = calc_cooling_tower(t_in, t_out, wbt, flow)
        
        colA, colB = st.columns([1, 1])
        with colA:
            st.markdown("### Thermodynamic Metrics")
            st.markdown(f"<div class='metric-card' style='border-left-color: #e67e22;'><div class='metric-title'>Range (ΔT)</div><div class='metric-value'>{rng:.1f} °C</div></div><br>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-card' style='border-left-color: #e67e22;'><div class='metric-title'>Approach</div><div class='metric-value'>{app:.1f} °C</div></div><br>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-card' style='border-left-color: #27ae60;'><div class='metric-title'>Effectiveness</div><div class='metric-value'>{eff:.1f} %</div></div>", unsafe_allow_html=True)
            
        with colB:
            st.markdown("### Water Balance Metrics")
            fig = px.pie(
                values=[evap, makeup-evap, flow-makeup], 
                names=['Evaporation Loss', 'Blowdown/Drift', 'Recirculated Water'],
                title=f"Water Distribution (Total: {flow} m³/h)",
                color_discrete_sequence=['#3498db', '#e74c3c', '#2ecc71']
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
            
        st.info(f"**Required Make-up Water:** {makeup:.2f} m³/h. (Assuming 3 Cycles of Concentration)")

# =====================================================================
# MODULE 3: COMPRESSED AIR
# =====================================================================
elif module == "💨 Compressed Air Systems":
    st.title("Compressed Air Leakage & Specific Power")
    st.markdown("Quantify energy losses due to network leaks using the Load/Unload test method.")
    
    c1, c2, c3, c4 = st.columns(4)
    cap_cfm = c1.number_input("Compressor Capacity (CFM)", value=500.0)
    power_kw = c2.number_input("Motor Power (kW)", value=75.0)
    t_on = c3.number_input("Load Time (T_on) secs", value=15.0)
    t_off = c4.number_input("Unload Time (T_off) secs", value=45.0)
    
    l_pct, l_cfm, p_lost = calc_compressor_leakage(t_on, t_off, cap_cfm, power_kw)
    spec_power = power_kw / cap_cfm
    
    mc1, mc2, mc3 = st.columns(3)
    mc1.markdown(f"<div class='metric-card' style='border-left-color: #9b59b6;'><div class='metric-title'>Specific Power</div><div class='metric-value'>{spec_power:.3f} kW/CFM</div></div>", unsafe_allow_html=True)
    mc2.markdown(f"<div class='metric-card' style='border-left-color: #e74c3c;'><div class='metric-title'>System Leakage</div><div class='metric-value'>{l_pct:.1f} %</div></div>", unsafe_allow_html=True)
    mc3.markdown(f"<div class='metric-card' style='border-left-color: #f1c40f;'><div class='metric-title'>Wasted Energy Rate</div><div class='metric-value'>{p_lost:.1f} kW</div></div>", unsafe_allow_html=True)
    
    annual_loss_cost = p_lost * OP_HOURS * ELEC_RATE
    
    st.markdown("---")
    st.error(f"🚨 **Financial Impact:** Network leaks are costing approximately **${annual_loss_cost:,.2f} / ₹{annual_loss_cost:,.2f}** annually.")
    
    st.markdown("### 🎛️ What-If Analysis: Leakage Rectification")
    target_leak = st.slider("Target Leakage Reduction (%)", min_value=0.0, max_value=float(l_pct), value=float(l_pct)*0.5)
    
    recovered_kw = (cap_cfm * ((l_pct - target_leak)/100)) * spec_power
    recovered_money = recovered_kw * OP_HOURS * ELEC_RATE
    
    st.success(f"Repairing leaks to target level saves **${recovered_money:,.2f}** annually.")

# =====================================================================
# MODULE 4: LIGHTING RETROFIT
# =====================================================================
elif module == "💡 Lighting Retrofit Analytics":
    st.title("Lighting Replacement Economics")
    st.markdown("Calculate ROI for transitioning legacy fixtures (CFL/Metal Halide) to High-Efficacy LEDs.")
    
    c1, c2, c3 = st.columns(3)
    qty = c1.number_input("Number of Fixtures", value=1000)
    old_w = c2.number_input("Existing Fixture Wattage (W)", value=40)
    new_w = c3.number_input("Proposed LED Wattage (W)", value=15)
    
    c4, c5 = st.columns(2)
    led_cost = c4.number_input("Cost per LED Fixture ($ or ₹)", value=10.0)
    install_cost = c5.number_input("Installation Cost per Fixture", value=2.0)
    
    old_kw, new_kw, saved_kw = calc_lighting_retrofit(qty, old_w, new_w)
    annual_savings = saved_kw * OP_HOURS * ELEC_RATE
    total_capex = qty * (led_cost + install_cost)
    roi_months = (total_capex / annual_savings) * 12 if annual_savings > 0 else 0
    
    st.markdown("### Retrofit Financials")
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Demand Reduction (kW)", f"{saved_kw:.1f} kW")
    mc2.metric("Annual Cost Savings", f"{annual_savings:,.0f}")
    mc3.metric("Simple Payback Period", f"{roi_months:.1f} Months")
    
    fig = go.Figure(go.Waterfall(
        name="20", orientation="v",
        measure=["relative", "relative", "total"],
        x=["Current Consumption", "Savings from LED", "New Consumption"],
        textposition="outside",
        text=[f"{old_kw} kW", f"-{saved_kw} kW", f"{new_kw} kW"],
        y=[old_kw, -saved_kw, new_kw],
        connector={"line":{"color":"rgb(63, 63, 63)"}},
    ))
    fig.update_layout(title="Demand Reduction Waterfall", showlegend=False, height=400)
    st.plotly_chart(fig, use_container_width=True)

# =====================================================================
# MODULE 5: COMBINED ANALYTICS
# =====================================================================
elif module == "📈 Plant Combined Analytics (What-If)":
    st.title("Global Plant Energy Profile")
    st.markdown("Synthesize multi-utility consumption to visualize total energy distribution and optimize plant-wide parameters.")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Global Inputs**")
    chiller_kw = st.sidebar.slider("Total HVAC/Chiller Load (kW)", 100, 2000, 800)
    comp_kw = st.sidebar.slider("Total Air Comp Load (kW)", 50, 1000, 300)
    light_kw = st.sidebar.slider("Total Lighting Load (kW)", 10, 500, 150)
    pump_kw = st.sidebar.slider("Total Pumping/Fans Load (kW)", 50, 1500, 400)
    
    total_kw = chiller_kw + comp_kw + light_kw + pump_kw
    total_annual_kwh = total_kw * OP_HOURS
    total_cost = total_annual_kwh * ELEC_RATE
    
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='metric-card'><div class='metric-title'>Total Connected Load</div><div class='metric-value'>{total_kw:,.0f} kW</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='metric-title'>Annual Consumption</div><div class='metric-value'>{total_annual_kwh:,.0f} kWh</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='metric-title'>Annual Energy Bill</div><div class='metric-value'>${total_cost:,.0f}</div></div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    colA, colB = st.columns(2)
    with colA:
        labels = ['HVAC & Chillers', 'Compressed Air', 'Lighting', 'Pumps & Fans']
        values = [chiller_kw, comp_kw, light_kw, pump_kw]
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker_colors=['#3498db', '#9b59b6', '#f1c40f', '#2ecc71'])])
        fig.update_layout(title_text="Plant Energy Distribution Breakdown")
        st.plotly_chart(fig, use_container_width=True)
        
    with colB:
        st.markdown("### 🎛️ Plant-Wide Sensitivity Analysis")
        st.markdown("Adjust operating parameters to view immediate financial impact.")
        
        sim_rate = st.slider("Simulate Tariff Change ($/kWh)", 0.05, 0.30, ELEC_RATE, 0.01)
        sim_eff = st.slider("Simulate Plant-Wide Efficiency Improvement (%)", 0.0, 20.0, 5.0, 0.5)
        
        new_kwh = total_annual_kwh * (1 - (sim_eff/100))
        new_bill = new_kwh * sim_rate
        variance = total_cost - new_bill
        
        st.info(f"**Projected Annual Bill:** ${new_bill:,.0f}")
        if variance > 0:
            st.success(f"**Net Savings:** ${variance:,.0f} per year.")
        else:
            st.error(f"**Net Cost Increase:** ${abs(variance):,.0f} per year.")
            
    st.markdown("<p class='bee-note'>Calculations adhere to BEE (Bureau of Energy Efficiency) Energy Auditing Guidelines.</p>", unsafe_allow_html=True)

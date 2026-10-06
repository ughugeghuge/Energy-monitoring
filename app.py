import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from iapws import IAPWS97
import matplotlib.pyplot as plt
import io
import pytz
from datetime import datetime
import textwrap

# =====================================================================
# PAGE CONFIGURATION & UI STYLING
# =====================================================================
st.set_page_config(page_title="Enterprise Energy & Pinch Analytics", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Metric Cards */
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
    
    /* Sidebar */
    .sidebar-section { font-size: 14px; font-weight: 600; color: #2c3e50; margin-top: 5px; margin-bottom: 5px; border-bottom: 1px solid #ccc; padding-bottom: 3px;}
    
    /* Headers & Insight Cards */
    .report-header {
        font-size: 20px;
        font-weight: 700;
        color: #2c3e50;
        border-bottom: 2px solid #3498db;
        padding-bottom: 8px;
        margin-top: 30px;
        margin-bottom: 20px;
    }
    .insight-card {
        background-color: #f8f9fa;
        border-top: 4px solid #3498db;
        border-radius: 6px;
        padding: 20px;
        height: 100%;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .insight-card h5 {
        color: #1f4e79;
        font-weight: 700;
        margin-top: 0;
        margin-bottom: 15px;
        font-size: 15px;
    }
    .insight-card p {
        color: #333333;
        font-size: 13.5px;
        line-height: 1.6;
        margin-bottom: 12px;
    }
    .insight-card b {
        color: #111111;
    }

    /* Watermark */
    .footer-watermark { position: fixed; right: 15px; bottom: 10px; font-size: 12px; color: #aaa; font-style: italic; z-index: 100;}
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="footer-watermark">prepared by- Umesh Ghuge</div>', unsafe_allow_html=True)

# =====================================================================
# GLOBAL PARAMETERS & SIDEBAR UI
# =====================================================================
st.sidebar.markdown("<div class='sidebar-section'>AUDIT MODULES</div>", unsafe_allow_html=True)
module = st.sidebar.radio("Select Engineering System:", [
    "1. Pinch Analysis & Heat Integration",
    "2. Heat Exchanger (HE) Analytics",
    "3. HVAC & Chiller Systems",
    "4. Cooling Tower Analytics",
    "5. Compressed Air Systems",
    "6. Lighting Retrofit Economics",
    "7. Plant-Wide Energy Sankey"
], label_visibility="collapsed")

st.sidebar.markdown("<br><br><br><br><br><br>", unsafe_allow_html=True)

with st.sidebar.expander("⚙️ Global Settings & Economics", expanded=False):
    col_cur, col_unit = st.columns(2)
    currency_opt = col_cur.selectbox("Currency", ["INR (₹)", "USD ($)", "EUR (€)", "GBP (£)"], index=0)
    curr_sym = currency_opt.split(" ")[1].strip("()")

    therm_unit = col_unit.selectbox("Thermal Unit", ["kcal/hr", "kW"], index=0)

    st.markdown("**Economic Factors**")
    ELEC_RATE = st.number_input(f"Electricity Tariff ({curr_sym}/kWh)", value=8.50 if "₹" in curr_sym else 0.12, step=0.5)
    STEAM_RATE = st.number_input(f"Steam Cost ({curr_sym}/kg)", value=2.00 if "₹" in curr_sym else 0.03, step=0.1)
    COOL_RATE = st.number_input(f"Cold Utility Cost ({curr_sym}/{therm_unit})", value=0.50 if "₹" in curr_sym else 0.01, step=0.1)
    OP_HOURS = st.number_input("Annual Operating Hours", value=8000, step=100)

# =====================================================================
# CORE ALGORITHMS & UTILITIES
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

def calc_steam_flow(q_val, unit, h_fg_kj):
    if unit == "kW":
        return (q_val * 3600.0) / h_fg_kj
    else: 
        h_fg_kcal = h_fg_kj / 4.184
        return q_val / h_fg_kcal

def format_insights_for_pdf(insights_raw, width=110):
    formatted = ""
    for section in insights_raw.split("\n\n"):
        lines = section.split("\n")
        formatted += lines[0] + "\n" 
        for line in lines[1:]:
            formatted += textwrap.fill(line, width=width) + "\n"
        formatted += "\n"
    return formatted

def build_pdf_footer(fig):
    ist_tz = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist_tz).strftime('%Y-%m-%d %H:%M:%S IST')
    fig.text(0.05, 0.02, f"Date: {current_time}", ha="left", va="bottom", fontsize=9, color="gray")
    fig.text(0.95, 0.02, "Prepared by Umesh Ghuge", ha="right", va="bottom", fontsize=9, color="gray", style='italic')

def generate_generic_pdf(title, df_inputs, metrics_text, insights_text, plot_func=None, **kwargs):
    fig = plt.figure(figsize=(10, 16))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.2, 3, 2])
    
    # 0. Table & Metrics
    ax0 = fig.add_subplot(gs[0])
    ax0.axis('off')
    ax0.text(0.5, 0.95, title.upper() + " REPORT", fontsize=16, weight='bold', ha='center', color='#1f4e79')
    
    if df_inputs is not None and not df_inputs.empty:
        table_data = [df_inputs.columns.to_list()] + df_inputs.values.tolist()
        table = ax0.table(cellText=table_data, loc='center', cellLoc='center', bbox=[0.05, 0.2, 0.9, 0.5])
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor('#E0E0E0')
            if row == 0:
                cell.set_facecolor('#2C3E50')
                cell.set_text_props(weight='bold', color='white')
            else:
                cell.set_facecolor('#F8F9FA' if row % 2 == 0 else '#FFFFFF')
                
    ax0.text(0.5, 0.05, metrics_text, fontsize=10, weight='bold', ha='center', color='#e74c3c')

    # 1. Plots
    if plot_func:
        ax1 = fig.add_subplot(gs[1])
        plot_func(ax1, **kwargs)

    # 2. Insights
    ax2 = fig.add_subplot(gs[2])
    ax2.axis('off')
    wrapped_insights = format_insights_for_pdf("EXPERT ANALYTICAL CONCLUSIONS\n\n" + insights_text, width=115)
    ax2.text(0.05, 0.95, wrapped_insights, fontsize=10, va='top', ha='left', family='sans-serif', color='#2c3e50',
             bbox=dict(boxstyle="round,pad=1.5", facecolor="#f4f6f9", edgecolor="#3498db", alpha=0.8))
    
    build_pdf_footer(fig)
    plt.tight_layout()
    pdf_buffer = io.BytesIO()
    fig.savefig(pdf_buffer, format="pdf", bbox_inches="tight")
    pdf_buffer.seek(0)
    plt.close(fig)
    return pdf_buffer

# =====================================================================
# MODULE 1: PINCH ANALYSIS (HEAT INTEGRATION)
# =====================================================================
if module == "1. Pinch Analysis & Heat Integration":
    st.title("Pinch Analysis & Heat Recovery Targeting")
    st.markdown("Optimize heat exchanger networks by determining minimum utility targets and optimum $\Delta T_{min}$ using thermodynamic cascading.")

    col1, col2 = st.columns([1, 4])
    dt_min_current = col1.number_input("Design Approach Temp (ΔT_min °C)", value=20.0, step=1.0)
    
    st.markdown("### Process Streams Definition")
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

    with st.expander("📐 View Mathematical Models & Economic Parameters"):
        st.latex(r"Q_{interval} = \sum CP_{hot} \Delta T - \sum CP_{cold} \Delta T")
        st.latex(r"Steam Mass Flow (\dot{m}) = \frac{Q_{HU}}{h_{fg}}")
        st.latex(r"Total Cost = \left( \dot{m}_{steam} \cdot C_{steam} + Q_{CU} \cdot C_{CU} \right) \cdot \text{Hours} + CapEx_{annualized}")
        
        st.markdown("**Utility & Capital Cost Parameters:**")
        cc1, cc2, cc3 = st.columns(3)
        steam_p = cc1.number_input("Utility Steam Pressure (bar g)", value=10.0, step=1.0)
        u_val = cc2.number_input(f"Avg Heat Transfer Coeff U ({therm_unit}/m²°C)", value=0.5)
        cost_m2 = cc3.number_input(f"Heat Exchanger Cost ({curr_sym}/m²)", value=5000.0)

    if st.button("Execute Rigorous Pinch Optimization", type="primary"):
        with st.spinner("Processing thermodynamic cascade and latent heat models..."):
            cp_col = f"CP ({therm_unit}/°C)"
            
            p_mpa = (steam_p * 0.1) + 0.101325
            try:
                sat_vap = IAPWS97(P=p_mpa, x=1)
                sat_liq = IAPWS97(P=p_mpa, x=0)
                h_fg_kj = sat_vap.h - sat_liq.h 
            except:
                h_fg_kj = 2000.0
                
            h_fg_display = h_fg_kj if therm_unit == "kW" else h_fg_kj / 4.184
            h_fg_unit = "kJ/kg" if therm_unit == "kW" else "kcal/kg"
            
            qh_min, qc_min, p_shift, q_rec, t_hot_avail, t_cold_req, gcc_heat, all_shifted_temps = run_pinch_algorithm(streams_df, dt_min_current, cp_col)
            pinch_hot = p_shift + dt_min_current/2
            pinch_cold = p_shift - dt_min_current/2

            steam_req_base = calc_steam_flow(qh_min, therm_unit, h_fg_kj)
            steam_req_unint = calc_steam_flow(t_cold_req, therm_unit, h_fg_kj)
            
            current_opex = (steam_req_base * STEAM_RATE + qc_min * COOL_RATE) * OP_HOURS
            unintegrated_opex = (steam_req_unint * STEAM_RATE + t_hot_avail * COOL_RATE) * OP_HOURS
            annual_savings = unintegrated_opex - current_opex

            mc1, mc2, mc3 = st.columns(3)
            mc1.markdown(f"<div class='metric-card' style='border-left-color:#e74c3c;'><div class='metric-title'>Target Hot Utility (QH)</div><div class='metric-value'>{qh_min:,.0f} {therm_unit}</div><div class='metric-sub'>Steam Req: {steam_req_base:,.0f} kg/hr</div></div>", unsafe_allow_html=True)
            mc2.markdown(f"<div class='metric-card' style='border-left-color:#3498db;'><div class='metric-title'>Target Cold Utility (QC)</div><div class='metric-value'>{qc_min:,.0f} {therm_unit}</div><div class='metric-sub'>Unintegrated Req: {t_hot_avail:,.0f} {therm_unit}</div></div>", unsafe_allow_html=True)
            mc3.markdown(f"<div class='metric-card' style='border-left-color:#2ecc71;'><div class='metric-title'>Process Heat Recovered</div><div class='metric-value'>{q_rec:,.0f} {therm_unit}</div><div class='metric-sub'>Avoided OpEx: {curr_sym}{annual_savings:,.0f}/yr</div></div>", unsafe_allow_html=True)

            # --- GRAPH 1: Composite Curves ---
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
            fig_cc.update_layout(title="Temperature vs. Enthalpy (Composite Curves)", xaxis_title=f"Enthalpy Ḣ ({therm_unit})", yaxis_title="Temperature T (°C)", template="plotly_white", height=500)
            st.plotly_chart(fig_cc, use_container_width=True)

            # --- GRAPH 2: Grand Composite Curve ---
            fig_gcc = go.Figure()
            fig_gcc.add_trace(go.Scatter(x=gcc_heat, y=all_shifted_temps, mode='lines+markers', name='GCC', line=dict(color='#8e44ad', width=3)))
            fig_gcc.add_hline(y=p_shift, line_dash="dash", line_color="gray", annotation_text=f"Pinch ({p_shift}°C Shifted)")
            fig_gcc.update_layout(title="Grand Composite Curve (GCC)", xaxis_title=f"Net Heat Flow ({therm_unit})", yaxis_title="Shifted Temperature (°C)", template="plotly_white", height=500)
            st.plotly_chart(fig_gcc, use_container_width=True)

            # --- GRAPH 3: Cost Optimization ---
            dt_range = np.linspace(5, 40, 30)
            opex_list, capex_list, total_list = [], [], []
            af = 0.2
            
            for dt in dt_range:
                qh, qc, p_s, qr, _, _, _, _ = run_pinch_algorithm(streams_df, dt, cp_col)
                s_req = calc_steam_flow(qh, therm_unit, h_fg_kj)
                op_cost = (s_req * STEAM_RATE + qc * COOL_RATE) * OP_HOURS
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
            fig_cost.update_layout(title="Economic Optimization: Cost vs. ΔT_min", xaxis_title="ΔT_min (°C)", yaxis_title=f"Annualized Cost ({curr_sym}/yr)", template="plotly_white", height=500)
            st.plotly_chart(fig_cost, use_container_width=True)

            # --- DYNAMIC EXPERT INSIGHTS (CSS Grid Layout) ---
            st.markdown("<div class='report-header'>📊 Expert Analytical Conclusions</div>", unsafe_allow_html=True)
            
            c_rpt1, c_rpt2, c_rpt3 = st.columns(3, gap="large")
            
            with c_rpt1:
                st.markdown(f"""
                <div class='insight-card'>
                    <h5>1. Utility Targets & Latent Heat</h5>
                    <p><b>Steam Dynamics:</b> At {steam_p} bar g, steam provides a latent heat of <b>{h_fg_display:,.0f} {h_fg_unit}</b>.</p>
                    <p><b>Minimum Utilities:</b> To satisfy the minimum heating target of {qh_min:,.0f} {therm_unit}, you must inject exactly <b>{steam_req_base:,.0f} kg/hr</b> of steam into the network.</p>
                    <p><b>Heat Recovery:</b> The overlapping horizontal region of the Composite Curves visually maps the maximum internal process-to-process heat exchange that requires zero external steam.</p>
                </div>
                """, unsafe_allow_html=True)

            with c_rpt2:
                st.markdown(f"""
                <div class='insight-card'>
                    <h5>2. The Golden Rules of the Pinch</h5>
                    <p><b>The Bottleneck:</b> The Pinch Point occurs at <b>{pinch_hot:.1f}°C</b> for Hot streams and <b>{pinch_cold:.1f}°C</b> for Cold streams.</p>
                    <p><b>Rule 1:</b> Do NOT transfer heat across the pinch. Transferring heat from above {pinch_hot:.1f}°C to below {pinch_cold:.1f}°C incurs a double penalty, increasing both your steam and cooling water bills simultaneously.</p>
                    <p><b>Rule 2 & 3:</b> Never use cooling utilities above the pinch, and never use steam below the pinch.</p>
                </div>
                """, unsafe_allow_html=True)

            with c_rpt3:
                st.markdown(f"""
                <div class='insight-card'>
                    <h5>3. Financial Optimization</h5>
                    <p><b>The Trade-Off:</b> As your design approach (ΔT_min) increases, Capital Costs drop exponentially (smaller heat exchangers). However, Operating Costs rise linearly (more steam required).</p>
                    <p><b>Optimum Target:</b> The cost optimization engine has identified the absolute Total Cost Minimum at <b>ΔT_min = {dt_opt:.1f}°C</b>.</p>
                    <p><b>Action:</b> Adjusting your design approach from {dt_min_current}°C to {dt_opt:.1f}°C will minimize your annualized lifecycle costs and yield maximum ROI.</p>
                </div>
                """, unsafe_allow_html=True)
            
            # PDF Export
            def draw_pinch_plots(fig, gs):
                ax1 = fig.add_subplot(gs[0])
                ax1.plot(h_hot_aligned, t_hot, color='#e74c3c', lw=2, label='Hot Composite')
                ax1.plot(h_cold, t_cold, color='#3498db', lw=2, label='Cold Composite')
                ax1.set_title("Composite Curves (T-H Diagram)", weight='bold')
                ax1.set_xlabel(f"Enthalpy ({therm_unit})")
                ax1.set_ylabel("Temperature (°C)")
                ax1.grid(True, linestyle='--', alpha=0.6)
                ax1.legend()

                ax2 = fig.add_subplot(gs[1])
                ax2.plot(gcc_heat, all_shifted_temps, color='#8e44ad', lw=2, marker='o', markersize=4)
                ax2.axhline(y=all_shifted_temps[gcc_heat.index(0)], color='gray', linestyle='--', label=f'Pinch Shifted')
                ax2.set_title("Grand Composite Curve (GCC)", weight='bold')
                ax2.set_xlabel(f"Net Heat Flow ({therm_unit})")
                ax2.set_ylabel("Shifted Temperature (°C)")
                ax2.grid(True, linestyle='--', alpha=0.6)
                ax2.legend()

                ax3 = fig.add_subplot(gs[2])
                ax3.plot(dt_range, total_list, color='#2c3e50', lw=2, label='Total Cost')
                ax3.plot(dt_range, opex_list, color='#e74c3c', lw=1.5, linestyle='--', label='Operating Cost')
                ax3.plot(dt_range, capex_list, color='#3498db', lw=1.5, linestyle='--', label='Capital Cost')
                ax3.axvline(x=dt_opt, color='green', linestyle=':', label=f'Optimum ΔT_min = {dt_opt:.1f}°C')
                ax3.set_title("Economic Optimization: Cost vs. ΔT_min", weight='bold')
                ax3.set_xlabel("ΔT_min (°C)")
                ax3.set_ylabel(f"Annualized Cost ({curr_sym}/yr)")
                ax3.grid(True, linestyle='--', alpha=0.6)
                ax3.legend()

            def generate_pinch_custom_pdf():
                fig = plt.figure(figsize=(10, 24))
                gs = fig.add_gridspec(5, 1, height_ratios=[1.2, 2, 2, 2, 2.2])
                
                ax0 = fig.add_subplot(gs[0])
                ax0.axis('off')
                ax0.text(0.5, 0.95, "PINCH ANALYSIS & HEAT INTEGRATION REPORT", fontsize=16, weight='bold', ha='center', color='#1f4e79')
                table_data = [streams_df.columns.to_list()] + streams_df.values.tolist()
                table = ax0.table(cellText=table_data, loc='center', cellLoc='center', bbox=[0.05, 0.2, 0.9, 0.6])
                table.auto_set_font_size(False)
                table.set_fontsize(8)
                for (row, col), cell in table.get_celld().items():
                    cell.set_edgecolor('#E0E0E0')
                    if row == 0:
                        cell.set_facecolor('#2C3E50'); cell.set_text_props(weight='bold', color='white')
                    else:
                        cell.set_facecolor('#F8F9FA' if row % 2 == 0 else '#FFFFFF')
                ax0.text(0.5, 0.05, f"TARGETS: Min Hot Utility: {qh_min:,.0f} {therm_unit} | Min Cold Utility: {qc_min:,.0f} {therm_unit} | Heat Recovered: {q_rec:,.0f} {therm_unit}", fontsize=10, weight='bold', ha='center', color='#e74c3c')

                draw_pinch_plots(fig, gs[1:4])

                ax4 = fig.add_subplot(gs[4])
                ax4.axis('off')
                t1 = f"The process Pinch Point is located at {pinch_hot:.1f}°C (Hot) and {pinch_cold:.1f}°C (Cold). The absolute minimum heating requirement is {qh_min:,.0f} {therm_unit}, which physically requires a steam demand of {steam_req_base:,.0f} kg/hr (releasing {h_fg_display:,.0f} {h_fg_unit} of latent heat). The minimum cold utility required to reject excess heat below the pinch is {qc_min:,.0f} {therm_unit}."
                t2 = f"Do not transfer heat from streams above {pinch_hot:.1f}°C to streams below {pinch_cold:.1f}°C. Any cross-pinch heat exchange will directly penalize the system, increasing both steam and cooling water consumption identically."
                t3 = f"The cost optimization engine calculates that the ideal balance between CapEx (heat exchanger area) and OpEx (steam & cooling water) occurs at a ΔT_min of {dt_opt:.1f}°C. Adjusting the network design from the current {dt_min_current}°C to {dt_opt:.1f}°C will minimize total annualized lifecycle costs."
                insights_text = f"1. Thermodynamic Bottleneck & Utilities:\n{t1}\n\n2. Pinch Violations:\n{t2}\n\n3. Economic Optimization:\n{t3}"
                
                wrapped = format_insights_for_pdf("EXPERT ANALYTICAL CONCLUSIONS\n\n" + insights_text, 115)
                ax4.text(0.05, 0.95, wrapped, fontsize=10, va='top', ha='left', family='sans-serif', color='#2c3e50', bbox=dict(boxstyle="round,pad=1.5", facecolor="#f4f6f9", edgecolor="#3498db", alpha=0.8))
                
                build_pdf_footer(fig)
                plt.tight_layout()
                pdf_buffer = io.BytesIO()
                fig.savefig(pdf_buffer, format="pdf", bbox_inches="tight")
                pdf_buffer.seek(0)
                plt.close(fig)
                return pdf_buffer

            st.download_button("📥 Download Pinch Analysis Report", data=generate_pinch_custom_pdf(), file_name="Pinch_Analysis_Report.pdf", mime="application/pdf")

# =====================================================================
# MODULE 2: HEAT EXCHANGER (HE) ANALYTICS
# =====================================================================
elif module == "2. Heat Exchanger (HE) Analytics":
    st.title("Heat Exchanger Design & Performance Analytics")
    st.markdown("Evaluate Log Mean Temperature Difference (LMTD), Heat Exchanger Area, Effectiveness ($\epsilon$), and Number of Transfer Units (NTU) based on rigorous fluid thermodynamics.")

    with st.expander("📐 View Mathematical Models & Formulas"):
        st.latex(r"Q = \dot{m}_{h} \cdot C_{p,h} \cdot (T_{h,i} - T_{h,o}) = \dot{m}_{c} \cdot C_{p,c} \cdot (T_{c,o} - T_{c,i})")
        st.latex(r"Q = U \cdot A \cdot LMTD \quad \text{where} \quad LMTD = \frac{\Delta T_1 - \Delta T_2}{\ln(\Delta T_1 / \Delta T_2)}")
        st.latex(r"Effectiveness (\epsilon) = \frac{Q_{actual}}{Q_{max}} = \frac{C_h(T_{h,i} - T_{h,o})}{C_{min}(T_{h,i} - T_{c,i})}")
        st.latex(r"NTU = \frac{U \cdot A}{C_{min}} \quad | \quad C_R = \frac{C_{min}}{C_{max}}")

    st.markdown("### 1. Process Temperatures")
    c1, c2, c3, c4 = st.columns(4)
    thi = c1.number_input("Hot Fluid Inlet (°C)", value=150.0)
    tho = c2.number_input("Hot Fluid Outlet (°C)", value=80.0)
    tci = c3.number_input("Cold Fluid Inlet (°C)", value=30.0)
    tco = c4.number_input("Cold Fluid Outlet (°C)", value=90.0)

    st.markdown("### 2. Fluid Thermodynamics & Flow Dynamics")
    c5, c6, c7, c8 = st.columns(4)
    m_hot = c5.number_input("Hot Fluid Mass Flow (kg/hr)", value=10000.0)
    
    cp_val = 4.187 if therm_unit == "kW" else 1.0
    cp_unit = "kJ/kg°C" if therm_unit == "kW" else "kcal/kg°C"
    
    cp_hot = c6.number_input(f"Hot Specific Heat ({cp_unit})", value=float(cp_val))
    cp_cold = c7.number_input(f"Cold Specific Heat ({cp_unit})", value=float(cp_val))
    flow_type = c8.selectbox("Flow Arrangement", ["Counter-Flow", "Parallel-Flow"])

    st.markdown("### 3. Heat Transfer Characteristics")
    cA, cB = st.columns(2)
    fluid_pair = cA.selectbox("Standard Application (Auto U-Value Reference)", [
        "Water to Water (Liquid)", 
        "Steam to Water (Condensing)", 
        "Light Oil to Water", 
        "Heavy Oil to Water", 
        "Gas to Water", 
        "Custom Input"
    ])
    
    u_dict_w_m2k = {
        "Water to Water (Liquid)": 1200.0,
        "Steam to Water (Condensing)": 2000.0,
        "Light Oil to Water": 450.0,
        "Heavy Oil to Water": 200.0,
        "Gas to Water": 50.0,
        "Custom Input": 800.0
    }
    
    default_u_wm2k = u_dict_w_m2k[fluid_pair]
    # Convert base W/m2K to kW/m2C or kcal/hr.m2C
    default_u = default_u_wm2k / 1000.0 if therm_unit == "kW" else default_u_wm2k * 0.8598
        
    u_val = cB.number_input(f"Overall Heat Transfer Coeff U ({therm_unit}/m²°C)", value=default_u, format="%.3f")

    if st.button("Evaluate Heat Exchanger Physics", type="primary"):
        # Rigorous Thermodynamic Validations
        if thi <= tho: 
            st.error("🚨 Thermodynamic Violation: Hot Inlet temperature must be strictly greater than Hot Outlet temperature.")
            st.stop()
        if tci >= tco: 
            st.error("🚨 Thermodynamic Violation: Cold Outlet temperature must be strictly greater than Cold Inlet temperature.")
            st.stop()
        if tho < tci: 
            st.error("🚨 Thermodynamic Violation: The hot fluid outlet cannot be cooler than the cold fluid inlet without a refrigeration cycle.")
            st.stop()
        if flow_type == "Parallel-Flow" and tho <= tco: 
            st.error("🚨 Temperature Cross Violation: In a Parallel-Flow arrangement, the Hot Fluid Outlet temperature must exit warmer than the Cold Fluid Outlet temperature. This violates the Second Law of Thermodynamics. Please switch to Counter-Flow or adjust your temperatures.")
            st.stop()

        # Calculate Heat Load (Q) & Required Cold Flow
        if therm_unit == "kW":
            q_load = (m_hot / 3600.0) * cp_hot * (thi - tho)
            m_cold = (q_load * 3600.0) / (cp_cold * (tco - tci))
        else:
            q_load = m_hot * cp_hot * (thi - tho)
            m_cold = q_load / (cp_cold * (tco - tci))

        # LMTD Calculation
        dt1 = (thi - tco) if flow_type == "Counter-Flow" else (thi - tci)
        dt2 = (tho - tci) if flow_type == "Counter-Flow" else (tho - tco)

        if abs(dt1 - dt2) < 0.01:
            lmtd = dt1
        else:
            lmtd = (dt1 - dt2) / np.log(dt1 / dt2)

        area = q_load / (u_val * lmtd) if u_val > 0 and lmtd > 0 else 0

        # Effectiveness & NTU
        if therm_unit == "kW":
            ch = (m_hot / 3600.0) * cp_hot
            cc = (m_cold / 3600.0) * cp_cold
        else:
            ch = m_hot * cp_hot
            cc = m_cold * cp_cold
            
        cmin = min(ch, cc)
        cmax = max(ch, cc)
        cr = cmin / cmax if cmax > 0 else 0
        qmax = cmin * (thi - tci)
        eff = (q_load / qmax) * 100 if qmax > 0 else 0
        ntu = (u_val * area) / cmin if cmin > 0 else 0

        mc1, mc2, mc3 = st.columns(3)
        mc1.markdown(f"<div class='metric-card' style='border-left-color:#3498db;'><div class='metric-title'>Calculated Heat Load</div><div class='metric-value'>{q_load:,.1f} {therm_unit}</div><div class='metric-sub'>Cold Fluid Flow Req: {m_cold:,.0f} kg/hr</div></div>", unsafe_allow_html=True)
        mc2.markdown(f"<div class='metric-card' style='border-left-color:#e74c3c;'><div class='metric-title'>Log Mean Temp Difference</div><div class='metric-value'>{lmtd:.1f} °C</div><div class='metric-sub'>ΔT1: {dt1:.1f}°C | ΔT2: {dt2:.1f}°C</div></div>", unsafe_allow_html=True)
        mc3.markdown(f"<div class='metric-card' style='border-left-color:#2ecc71;'><div class='metric-title'>Required Surface Area</div><div class='metric-value'>{area:.1f} m²</div><div class='metric-sub'>ε: {eff:.1f}% | NTU: {ntu:.2f}</div></div>", unsafe_allow_html=True)

        # Plot Temperature Profile
        x_dist = np.linspace(0, 100, 100)
        if flow_type == "Counter-Flow":
            t_hot_curve = thi - (thi - tho) * (x_dist/100)
            t_cold_curve = tco - (tco - tci) * (x_dist/100) 
        else:
            t_hot_curve = thi - (thi - tho) * (x_dist/100)
            t_cold_curve = tci + (tco - tci) * (x_dist/100)

        fig_he = go.Figure()
        fig_he.add_trace(go.Scatter(x=x_dist, y=t_hot_curve, mode='lines', name='Hot Fluid', line=dict(color='#e74c3c', width=3)))
        fig_he.add_trace(go.Scatter(x=x_dist, y=t_cold_curve, mode='lines', name='Cold Fluid', line=dict(color='#3498db', width=3)))
        fig_he.update_layout(title=f"Heat Exchanger Temperature Profile ({flow_type})", xaxis_title="Exchanger Length (%)", yaxis_title="Temperature (°C)", template="plotly_white", height=450)
        st.plotly_chart(fig_he, use_container_width=True)

        insights_text = f"1. Design Feasibility:\nWith an LMTD of {lmtd:.1f}°C, the calculated required heat transfer area is {area:.1f} m². Counter-flow arrangements generally maximize LMTD, thereby minimizing the physical footprint and capital cost of the exchanger network compared to parallel flows.\n\n2. Thermal Performance (ε-NTU):\nThe calculated effectiveness is {eff:.1f}% with an NTU of {ntu:.2f}. An effectiveness above 80% generally indicates a highly efficient, though potentially oversized, heat exchanger. The capacity ratio (C_min/C_max) is {cr:.2f}.\n\n3. Operational Degradation:\nIf the measured outlet temperatures in your live plant begin to deviate (e.g., Hot Outlet rises or Cold Outlet drops below these targets), this indicates fouling. Fouling reduces the Overall Heat Transfer Coefficient (U), forcing the LMTD to increase to compensate for the lost thermal performance."

        st.markdown("<div class='report-header'>📊 Expert Analytical Conclusions</div>", unsafe_allow_html=True)
        c_rpt1, c_rpt2, c_rpt3 = st.columns(3, gap="large")
        with c_rpt1:
            st.markdown(f"<div class='insight-card'><h5>1. Design Feasibility</h5><p>With an LMTD of <b>{lmtd:.1f}°C</b>, the calculated required heat transfer area is <b>{area:.1f} m²</b>. Counter-flow arrangements generally maximize LMTD, minimizing physical footprint and capital cost.</p></div>", unsafe_allow_html=True)
        with c_rpt2:
            st.markdown(f"<div class='insight-card'><h5>2. Thermal Performance</h5><p>Effectiveness is <b>{eff:.1f}%</b> (NTU: {ntu:.2f}). An effectiveness above 80% indicates a highly efficient unit. The capacity ratio ($C_{{min}}/C_{{max}}$) is {cr:.2f}.</p></div>", unsafe_allow_html=True)
        with c_rpt3:
            st.markdown(f"<div class='insight-card'><h5>3. Operational Degradation</h5><p>If measured outlet temperatures deviate over time, it indicates fouling. Fouling reduces the Overall Heat Transfer Coefficient (U), forcing LMTD to increase to compensate.</p></div>", unsafe_allow_html=True)

        # PDF Export
        df_he = pd.DataFrame({
            "Parameter": ["Hot Inlet", "Hot Outlet", "Cold Inlet", "Cold Outlet", "Hot Flow", "Cold Flow Req", "U Value"], 
            "Value": [f"{thi}°C", f"{tho}°C", f"{tci}°C", f"{tco}°C", f"{m_hot:,.0f} kg/hr", f"{m_cold:,.0f} kg/hr", f"{u_val} {therm_unit}/m²°C"]
        })
        metrics_str = f"Q: {q_load:,.1f} {therm_unit} | LMTD: {lmtd:.1f} °C | Area: {area:.1f} m² | Effectiveness: {eff:.1f} %"
        
        def plot_he(ax):
            ax.plot(x_dist, t_hot_curve, color='#e74c3c', lw=2, label='Hot Fluid')
            ax.plot(x_dist, t_cold_curve, color='#3498db', lw=2, label='Cold Fluid')
            ax.set_title(f"Temperature Profile ({flow_type})", weight='bold')
            ax.set_xlabel("Exchanger Length (%)")
            ax.set_ylabel("Temperature (°C)")
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.legend()
            
        pdf_report = generate_generic_pdf("Heat Exchanger Analytics", df_he, metrics_str, insights_text, plot_func=plot_he)
        st.download_button("📥 Download Heat Exchanger Report", data=pdf_report, file_name="HE_Analytics_Report.pdf", mime="application/pdf")

# =====================================================================
# MODULE 3: HVAC & CHILLERS
# =====================================================================
elif module == "3. HVAC & Chiller Systems":
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
    
    insights_text = f"1. Baseline Performance:\nAt {kw_tr:.2f} kW/TR, your chiller operates at {carnot_eff:.1f}% of its theoretical Carnot potential. Typical modern centrifugal chillers achieve 0.55 - 0.65 kW/TR.\n\n2. Actionable Optimization:\nClean condenser tubes immediately. A fouling factor increase of just 0.0005 can increase compressor power by 10%. Elevating chilled water supply setpoints by 1°C can yield a 3% reduction in compressor work."
    
    st.markdown("<div class='report-header'>📊 Expert Analytical Conclusions</div>", unsafe_allow_html=True)
    c_rpt1, c_rpt2 = st.columns(2, gap="large")
    with c_rpt1:
        st.markdown(f"<div class='insight-card'><h5>1. Baseline Performance</h5><p>At <b>{kw_tr:.2f} kW/TR</b>, your chiller operates at <b>{carnot_eff:.1f}%</b> of its theoretical Carnot potential. Typical modern centrifugal chillers achieve 0.55 - 0.65 kW/TR.</p></div>", unsafe_allow_html=True)
    with c_rpt2:
        st.markdown("<div class='insight-card'><h5>2. Actionable Optimization</h5><p>Clean condenser tubes immediately. A fouling factor increase of just 0.0005 can increase compressor power by 10%. Elevating chilled water supply setpoints by 1°C can yield a 3% reduction in compressor work.</p></div>", unsafe_allow_html=True)

    df_hvac = pd.DataFrame({"Parameter": ["Flow (m³/h)", "CHW Return", "CHW Supply", "Condenser Temp", "Power (kW)"], "Value": [flow, f"{t_in}°C", f"{t_out}°C", f"{t_cond}°C", power]})
    metrics_str = f"Load: {tr:.1f} TR | Specific Energy: {kw_tr:.3f} kW/TR | COP: {cop:.2f} | Carnot Eff: {carnot_eff:.1f}%"
    
    def plot_hvac(ax):
        labels = ['Current kW/TR', 'Target kW/TR (0.6)']
        vals = [kw_tr, 0.6]
        ax.bar(labels, vals, color=['#e74c3c', '#2ecc71'])
        ax.set_ylabel("Specific Power (kW/TR)")
        ax.set_title("Benchmarking Specific Power", weight='bold')
        ax.grid(axis='y', linestyle='--', alpha=0.6)
        
    pdf_report = generate_generic_pdf("HVAC & Chiller Analytics", df_hvac, metrics_str, insights_text, plot_func=plot_hvac)
    st.download_button("📥 Download HVAC Report", data=pdf_report, file_name="HVAC_Report.pdf", mime="application/pdf")

# =====================================================================
# MODULE 4: COOLING TOWERS
# =====================================================================
elif module == "4. Cooling Tower Analytics":
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

        insights_text = f"1. Approach Analysis:\nYour current approach is {app:.1f}°C. Industrial towers are designed for a 3-5°C approach. If your approach is higher, inspect fill media for scaling or verify fan blade pitch angles.\n\n2. Water Conservation:\nYou are consuming {makeup*OP_HOURS:,.0f} m³ of fresh water annually. Increasing your Cycles of Concentration (COC) through automated blowdown controllers can significantly reduce this intake."

        st.markdown("<div class='report-header'>📊 Expert Analytical Conclusions</div>", unsafe_allow_html=True)
        c_rpt1, c_rpt2 = st.columns(2, gap="large")
        with c_rpt1:
            st.markdown(f"<div class='insight-card'><h5>1. Approach Analysis</h5><p>Your current approach is <b>{app:.1f}°C</b>. Industrial towers are designed for a 3-5°C approach. If your approach is higher, inspect fill media for scaling or verify fan blade pitch angles.</p></div>", unsafe_allow_html=True)
        with c_rpt2:
            st.markdown(f"<div class='insight-card'><h5>2. Water Conservation</h5><p>You are consuming <b>{makeup*OP_HOURS:,.0f} m³</b> of fresh water annually. Increasing your Cycles of Concentration (COC) through automated blowdown controllers can significantly reduce this intake.</p></div>", unsafe_allow_html=True)

        df_ct = pd.DataFrame({"Parameter": ["Hot Return", "Cold Supply", "Ambient WBT", "Circulation Flow"], "Value": [f"{t_in}°C", f"{t_out}°C", f"{wbt}°C", f"{flow} m³/h"]})
        metrics_str = f"Effectiveness: {eff:.1f}% | Approach: {app:.1f}°C | Range: {rng:.1f}°C | Make-up Water: {makeup:.1f} m³/h"
        
        def plot_ct(ax):
            labels = ['Evaporation', 'Blowdown/Drift']
            sizes = [evap, blowdown]
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#3498db', '#e74c3c'])
            ax.axis('equal')
            ax.set_title("Water Loss Breakdown", weight='bold')

        pdf_report = generate_generic_pdf("Cooling Tower Analytics", df_ct, metrics_str, insights_text, plot_func=plot_ct)
        st.download_button("📥 Download Cooling Tower Report", data=pdf_report, file_name="CT_Report.pdf", mime="application/pdf")

# =====================================================================
# MODULE 5: COMPRESSED AIR
# =====================================================================
elif module == "5. Compressed Air Systems":
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
    
    insights_text = f"1. Leakage Impact:\nThe network is leaking {l_pct:.1f}% of generated air, bleeding {curr_sym}{annual_loss_cost:,.0f} per year. Implement an ultrasonic leak detection survey immediately. Target reducing leakage to under 10%.\n\n2. Pressure Reduction:\nFor every 1 bar reduction in header pressure, power decreases by ~7%. Ensure point-of-use regulators are utilized rather than over-pressurizing the entire central header."

    st.markdown("<div class='report-header'>📊 Expert Analytical Conclusions</div>", unsafe_allow_html=True)
    c_rpt1, c_rpt2 = st.columns(2, gap="large")
    with c_rpt1:
        st.markdown(f"<div class='insight-card'><h5>1. Leakage Impact</h5><p>The network is leaking <b>{l_pct:.1f}%</b> of generated air, bleeding <b>{curr_sym}{annual_loss_cost:,.0f}</b> per year. Implement an ultrasonic leak detection survey immediately. Target reducing leakage to under 10%.</p></div>", unsafe_allow_html=True)
    with c_rpt2:
        st.markdown("<div class='insight-card'><h5>2. Pressure Reduction</h5><p>For every 1 bar reduction in header pressure, power decreases by ~7%. Ensure point-of-use regulators are utilized rather than over-pressurizing the entire central header.</p></div>", unsafe_allow_html=True)

    df_air = pd.DataFrame({"Parameter": ["Capacity (CFM)", "Motor (kW)", "Load Time", "Unload Time"], "Value": [cap_cfm, power_kw, f"{t_on} s", f"{t_off} s"]})
    metrics_str = f"Specific Power: {spec_power:.3f} kW/CFM | Leakage: {l_pct:.1f}% | Wasted Cost: {curr_sym}{annual_loss_cost:,.0f}/yr"
    
    def plot_air(ax):
        labels = ['Useful Air', 'Leaked Air']
        sizes = [100 - l_pct, l_pct]
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#2ecc71', '#e74c3c'])
        ax.axis('equal')
        ax.set_title("Compressed Air Network Efficiency", weight='bold')

    pdf_report = generate_generic_pdf("Compressed Air Analytics", df_air, metrics_str, insights_text, plot_func=plot_air)
    st.download_button("📥 Download Compressed Air Report", data=pdf_report, file_name="Air_Report.pdf", mime="application/pdf")

# =====================================================================
# MODULE 6: LIGHTING RETROFIT
# =====================================================================
elif module == "6. Lighting Retrofit Economics":
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

    insights_text = f"1. Financial Viability:\nWith a simple payback period of {roi_months:.1f} months, this retrofit is highly attractive. Any ROI under 24 months is generally considered an immediate-action operational priority.\n\n2. Maintenance Offsets:\nLEDs possess a lifespan of ~50,000 hours compared to legacy lifespans of 8,000-15,000 hours. This calculation does not yet include avoided replacement labor costs, meaning your actual ROI will be even faster."

    st.markdown("<div class='report-header'>📊 Expert Analytical Conclusions</div>", unsafe_allow_html=True)
    c_rpt1, c_rpt2 = st.columns(2, gap="large")
    with c_rpt1:
        st.markdown(f"<div class='insight-card'><h5>1. Financial Viability</h5><p>With a simple payback period of <b>{roi_months:.1f} months</b>, this retrofit is highly attractive. Any ROI under 24 months is generally considered an immediate-action operational priority.</p></div>", unsafe_allow_html=True)
    with c_rpt2:
        st.markdown("<div class='insight-card'><h5>2. Maintenance Offsets</h5><p>LEDs possess a lifespan of ~50,000 hours compared to legacy lifespans of 8,000-15,000 hours. This calculation does not yet include avoided replacement labor costs, meaning your actual ROI will be even faster.</p></div>", unsafe_allow_html=True)

    df_light = pd.DataFrame({"Parameter": ["Fixtures Count", "Legacy Wattage", "LED Wattage", "Total Capex"], "Value": [qty, f"{old_w} W", f"{new_w} W", f"{curr_sym}{total_capex:,.0f}"]})
    metrics_str = f"Demand Reduction: {saved_kw:.1f} kW | Annual Savings: {curr_sym}{annual_savings:,.0f} | Payback: {roi_months:.1f} Months"
    
    def plot_light(ax):
        labels = ['Legacy Draw', 'LED Draw']
        vals = [old_kw, new_kw]
        ax.bar(labels, vals, color=['#e74c3c', '#2ecc71'])
        ax.set_ylabel("Power Demand (kW)")
        ax.set_title("Demand Reduction", weight='bold')
        ax.grid(axis='y', linestyle='--', alpha=0.6)

    pdf_report = generate_generic_pdf("Lighting Retrofit Economics", df_light, metrics_str, insights_text, plot_func=plot_light)
    st.download_button("📥 Download Lighting Report", data=pdf_report, file_name="Lighting_Report.pdf", mime="application/pdf")

# =====================================================================
# MODULE 7: COMBINED ANALYTICS
# =====================================================================
elif module == "7. Plant-Wide Energy Sankey":
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

    insights_text = f"1. Compressor Dominance:\nNote the massive proportion of compressed air energy routed to 'Losses'. Compressed air is an incredibly inefficient utility (~10-15% mechanical efficiency). Evaluate replacing pneumatic tools with direct electric drives where feasible.\n\n2. Base Load Optimization:\nYour plant is drawing {total_kw} kW. Target a 5% baseline reduction via operational housekeeping (turning off idle equipment, repairing leaks, cleaning heat exchange surfaces), which will yield an immediate, zero-capex saving of {curr_sym}{(total_bill*0.05):,.0f} per year."

    st.markdown("<div class='report-header'>📊 Expert Analytical Conclusions</div>", unsafe_allow_html=True)
    c_rpt1, c_rpt2 = st.columns(2, gap="large")
    with c_rpt1:
        st.markdown("<div class='insight-card'><h5>1. Compressor Dominance</h5><p>Note the massive proportion of compressed air energy routed to \"Losses\" (Red line). Compressed air is an incredibly inefficient utility (~10-15% mechanical efficiency). Evaluate replacing pneumatic tools with direct electric drives where feasible.</p></div>", unsafe_allow_html=True)
    with c_rpt2:
        st.markdown(f"<div class='insight-card'><h5>2. Base Load Optimization</h5><p>Your plant is drawing <b>{total_kw} kW</b>. Target a 5% baseline reduction via operational housekeeping (turning off idle equipment, repairing leaks, cleaning heat exchange surfaces), which will yield an immediate, zero-capex saving of <b>{curr_sym}{(total_bill*0.05):,.0f}</b> per year.</p></div>", unsafe_allow_html=True)

    df_plant = pd.DataFrame({"System": ["HVAC/Chillers", "Compressed Air", "Lighting", "Pumps & Fans"], "Load (kW)": [chiller_kw, comp_kw, light_kw, pump_kw]})
    metrics_str = f"Aggregate Load: {total_kw:,.0f} kW | Annual TWh: {(total_kw * OP_HOURS)/1e6:.2f} GWh | Total Bill: {curr_sym}{total_bill:,.0f}/yr"
    
    def plot_plant(ax):
        labels = ['Useful Energy', 'System Losses']
        useful = (chiller_kw-chiller_loss) + (comp_kw-comp_loss) + (light_kw-light_loss) + (pump_kw-pump_loss)
        losses = chiller_loss + comp_loss + light_loss + pump_loss
        ax.pie([useful, losses], labels=labels, autopct='%1.1f%%', startangle=90, colors=['#1abc9c', '#e74c3c'])
        ax.axis('equal')
        ax.set_title("Plant Base Load Efficiency", weight='bold')

    pdf_report = generate_generic_pdf("Plant-Wide Energy Profile", df_plant, metrics_str, insights_text, plot_func=plot_plant)
    st.download_button("📥 Download Plant Profile Report", data=pdf_report, file_name="Plant_Profile_Report.pdf", mime="application/pdf")

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_manager import DataManager
from components.timeframe_selector import timeframe_selector

st.set_page_config(layout="wide", page_title="FVI Sniper Pro")

# ==========================================
# SESSION STATE & DONNÉES PARTAGÉES
# ==========================================
if "data_manager" not in st.session_state:
    st.session_state.data_manager = DataManager(max_candles=500)

if "current_timeframe" not in st.session_state:
    st.session_state.current_timeframe = "1m"

# ==========================================
# TITRE
# ==========================================
st.title("💎 FVI Sniper Pro [Full Fill + Vol Imbalance]")
st.caption("Fair Value Gaps avec intensité de volume et détection de remplissage complet")

# ==========================================
# 1. PARAMÈTRES (SIDEBAR)
# ==========================================
with st.sidebar:
    # Sélecteur de timeframe
    current_tf = timeframe_selector("fvi_sniper_pro")
    
    st.markdown("---")
    st.header("🎯 Liquidity & Swings")
    left_bars = st.number_input("Pivot Lookback Left", value=10, min_value=3, max_value=50)
    right_bars = st.number_input("Pivot Lookback Right", value=3, min_value=1, max_value=20)
    
    st.markdown("---")
    st.header("📦 Fair Value Gaps")
    show_fvg = st.checkbox("Show FVG Boxes", value=True)
    fvg_width = st.number_input("FVG Width (Bars)", value=6, min_value=1, max_value=20)
    mitigate = st.checkbox("Gray out when FULLY filled", value=True)
    
    st.markdown("---")
    st.header("📊 Volume Strength")
    vol_len = st.number_input("Volume Avg Length", value=20, min_value=5, max_value=100)
    vol_mult = st.slider("High Volume Multiplier", min_value=1.0, max_value=3.0, value=1.5, step=0.1)
    
    st.markdown("---")
    st.header("🔬 Elasticity")
    z_length = st.number_input("Z-Score Length", value=82, min_value=20, max_value=500)
    z_thresh = st.slider("Z-Score Threshold", min_value=0.5, max_value=3.0, value=1.3, step=0.1)

# ==========================================
# 2. RÉCUPÉRATION DES DONNÉES
# ==========================================
df = st.session_state.data_manager.get_dataframe(st.session_state.current_timeframe)

min_required = max(left_bars + right_bars, z_length) + 50

if df.empty or len(df) < min_required:
    st.warning("⏳ Pas assez de données disponibles...")
    st.info(f"📊 Données actuelles: {len(df)} | Minimum: ~{min_required}")
    st.stop()

# ==========================================
# 3. CALCULS FVI SNIPER PRO
# ==========================================

# 1. Pivots (Liquidité)
def find_pivot_highs(highs, left, right):
    pivots = []
    for i in range(left, len(highs) - right):
        window = highs.iloc[i-left:i+right+1]
        if highs.iloc[i] == window.max():
            pivots.append((i, highs.iloc[i]))
    return pivots

def find_pivot_lows(lows, left, right):
    pivots = []
    for i in range(left, len(lows) - right):
        window = lows.iloc[i-left:i+right+1]
        if lows.iloc[i] == window.min():
            pivots.append((i, lows.iloc[i]))
    return pivots

pivot_highs = find_pivot_highs(df['high'], left_bars, right_bars)
pivot_lows = find_pivot_lows(df['low'], left_bars, right_bars)

last_liq_high = pivot_highs[-1][1] if pivot_highs else df['high'].max()
last_liq_low = pivot_lows[-1][1] if pivot_lows else df['low'].min()

# 2. Volume Analysis
df['vol_avg'] = df.get('volume', pd.Series([0]*len(df))).rolling(vol_len).mean()

# 3. FVG Detection avec Volume
fvg_boxes = []

for i in range(2, len(df)):
    # Bull FVG: low[i] > high[i-2]
    if df['low'].iloc[i] > df['high'].iloc[i-2]:
        vol_at_move = df['volume'].iloc[i-1] if 'volume' in df.columns else 0
        vol_avg_at_move = df['vol_avg'].iloc[i-1]
        is_high_vol = vol_at_move > (vol_avg_at_move * vol_mult)
        
        fvg_boxes.append({
            'start_bar': i-1,
            'end_bar': i + fvg_width,
            'top': df['low'].iloc[i],
            'bottom': df['high'].iloc[i-2],
            'is_bull': True,
            'high_vol': is_high_vol,
            'limit_level': df['high'].iloc[i-2],
            'mitigated': False
        })
    
    # Bear FVG: high[i] < low[i-2]
    elif df['high'].iloc[i] < df['low'].iloc[i-2]:
        vol_at_move = df['volume'].iloc[i-1] if 'volume' in df.columns else 0
        vol_avg_at_move = df['vol_avg'].iloc[i-1]
        is_high_vol = vol_at_move > (vol_avg_at_move * vol_mult)
        
        fvg_boxes.append({
            'start_bar': i-1,
            'end_bar': i + fvg_width,
            'top': df['low'].iloc[i-2],
            'bottom': df['high'].iloc[i],
            'is_bull': False,
            'high_vol': is_high_vol,
            'limit_level': df['low'].iloc[i-2],
            'mitigated': False
        })

# Vérifier mitigation (remplissage complet)
# CORRECTION: On vérifie SEULEMENT après la création (N+x), pas avant
if mitigate:
    for fvg in fvg_boxes:
        # Vérifier uniquement les bougies APRÈS la création du FVG
        start_check = fvg['start_bar'] + 1  # Commencer APRÈS la création
        
        for j in range(start_check, len(df)):
            if fvg['is_bull']:
                # Bull FVG rempli si le prix REVIENT en bas et touche la limite
                if df['low'].iloc[j] <= fvg['limit_level']:
                    fvg['mitigated'] = True
                    break
            else:
                # Bear FVG rempli si le prix REVIENT en haut et touche la limite
                if df['high'].iloc[j] >= fvg['limit_level']:
                    fvg['mitigated'] = True
                    break

# 4. Z-Score Elasticity
df['basis'] = df['close'].rolling(z_length).mean()
df['dev'] = df['close'].rolling(z_length).std()
df['z_score'] = (df['close'] - df['basis']) / df['dev']

# 5. Sweep Signals
df['sweep_high'] = df['high'] > last_liq_high
df['sweep_low'] = df['low'] < last_liq_low

df['extended_up'] = df['z_score'] > z_thresh
df['extended_down'] = df['z_score'] < -z_thresh

df['rejection_bear'] = (df['close'] < last_liq_high) & (df['close'] < df['open'])
df['rejection_bull'] = (df['close'] > last_liq_low) & (df['close'] > df['open'])

df['valid_short'] = df['sweep_high'] & df['extended_up'] & df['rejection_bear']
df['valid_long'] = df['sweep_low'] & df['extended_down'] & df['rejection_bull']

# ==========================================
# 4. MÉTRIQUES
# ==========================================
col1, col2, col3, col4 = st.columns(4)

total_fvg = len(fvg_boxes)
active_fvg = len([f for f in fvg_boxes if not f['mitigated']])
total_long = df['valid_long'].sum()
total_short = df['valid_short'].sum()

with col1:
    st.metric("FVG Total", total_fvg)

with col2:
    st.metric("FVG Actifs", active_fvg)

with col3:
    st.metric("Sweep LONG", total_long)

with col4:
    st.metric("Sweep SHORT", total_short)

# ==========================================
# 5. AFFICHAGE PLOTLY
# ==========================================

# Background si Z-score extrême
bg_color = 'rgba(0,0,0,0)'
last_z = df['z_score'].iloc[-1]
if last_z > 2.0:
    bg_color = 'rgba(164,50,199,0.05)'
elif last_z < -2.0:
    bg_color = 'rgba(52,169,211,0.05)'

fig = go.Figure()

# 1. Candlestick
fig.add_trace(go.Candlestick(
    x=df.index,
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    name="BTCUSDT",
    increasing_line_color='#26a69a',
    decreasing_line_color='#ef5350'
))

# 2. Liquidity Pivots
if pivot_highs:
    ph_indices = [p[0] for p in pivot_highs]
    ph_values = [p[1] for p in pivot_highs]
    fig.add_trace(go.Scatter(
        x=[df.index[i] for i in ph_indices],
        y=ph_values,
        mode='markers',
        marker=dict(size=6, color='#a167df', opacity=0.5, symbol='circle'),
        name='Liquidity High'
    ))

if pivot_lows:
    pl_indices = [p[0] for p in pivot_lows]
    pl_values = [p[1] for p in pivot_lows]
    fig.add_trace(go.Scatter(
        x=[df.index[i] for i in pl_indices],
        y=pl_values,
        mode='markers',
        marker=dict(size=6, color='#70dcea', opacity=0.5, symbol='circle'),
        name='Liquidity Low'
    ))

# 3. FVG Boxes
if show_fvg:
    for fvg in fvg_boxes:
        if fvg['mitigated']:
            # Gris si rempli
            fill_color = 'rgba(128,128,128,0.1)'
        else:
            # Selon volume et direction
            if fvg['is_bull']:
                alpha = 0.6 if fvg['high_vol'] else 0.2
                fill_color = f'rgba(0,255,0,{alpha})'
            else:
                alpha = 0.6 if fvg['high_vol'] else 0.2
                fill_color = f'rgba(255,0,0,{alpha})'
        
        fig.add_shape(
            type="rect",
            x0=df.index[fvg['start_bar']],
            y0=fvg['bottom'],
            x1=df.index[min(fvg['end_bar'], len(df)-1)],
            y1=fvg['top'],
            fillcolor=fill_color,
            line=dict(width=0),
            layer='below'
        )

# 4. Sweep Signals
long_signals = df[df['valid_long']]
short_signals = df[df['valid_short']]

if not long_signals.empty:
    fig.add_trace(go.Scatter(
        x=long_signals.index,
        y=long_signals['low'] * 0.997,
        mode='markers+text',
        marker=dict(size=15, color='#58dfe1', symbol='triangle-up', line=dict(width=1, color='white')),
        text='SWEEP<br>LONG',
        textposition='bottom center',
        textfont=dict(color='white', size=8),
        name='Sweep Long'
    ))

if not short_signals.empty:
    fig.add_trace(go.Scatter(
        x=short_signals.index,
        y=short_signals['high'] * 1.003,
        mode='markers+text',
        marker=dict(size=15, color='#ab65dc', symbol='triangle-down', line=dict(width=1, color='white')),
        text='SWEEP<br>SHORT',
        textposition='top center',
        textfont=dict(color='white', size=8),
        name='Sweep Short'
    ))

# Configuration
fig.update_layout(
    height=800,
    paper_bgcolor=bg_color,
    plot_bgcolor='#1e222d',
    xaxis_rangeslider_visible=False,
    xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)', color='white'),
    yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)', color='white', side='right', tickformat=',.2f', tickprefix='$'),
    font=dict(color='white'),
    hovermode='x unified',
    hoverlabel=dict(bgcolor='rgba(0,0,0,0.8)', font_size=12, font_family="monospace"),
    margin=dict(l=20, r=100, t=40, b=40),
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(0,0,0,0.5)')
)

st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 6. ANALYSE FVG
# ==========================================
st.subheader("📦 Analyse des Fair Value Gaps")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**🟢 Bullish FVG**")
    bull_fvg = [f for f in fvg_boxes if f['is_bull']]
    bull_active = [f for f in bull_fvg if not f['mitigated']]
    st.write(f"Total: {len(bull_fvg)}")
    st.write(f"Actifs: {len(bull_active)}")
    st.write(f"High Vol: {len([f for f in bull_fvg if f['high_vol']])}")

with col2:
    st.markdown("**🔴 Bearish FVG**")
    bear_fvg = [f for f in fvg_boxes if not f['is_bull']]
    bear_active = [f for f in bear_fvg if not f['mitigated']]
    st.write(f"Total: {len(bear_fvg)}")
    st.write(f"Actifs: {len(bear_active)}")
    st.write(f"High Vol: {len([f for f in bear_fvg if f['high_vol']])}")

st.markdown("---")
st.subheader("💡 Comprendre les FVG")

st.markdown(f"""
**Fair Value Gap (FVG)** = Zone où le prix a "sauté" sans transaction.

**Bullish FVG** : low[0] > high[2]
- Zone verte entre high[2] et low[0]
- Le prix a explosé à la hausse
- Zone d'**imbalance** = support potentiel

**Bearish FVG** : high[0] < low[2]
- Zone rouge entre high[0] et low[2]
- Le prix a chuté rapidement
- Zone d'**imbalance** = résistance potentielle

**Intensité de Volume:**
- 🟢/🔴 **Foncé** : Volume > {vol_mult}x moyenne (FORT)
- 🟢/🔴 **Clair** : Volume normal (FAIBLE)

**Mitigation:**
- ⚪ **Gris** : FVG rempli complètement → Zone épuisée
- Prix a revisité et "comblé" le gap

**Stratégie:**
1. FVG + High Vol = Zone forte, probable support/résistance
2. FVG actif = Zone à surveiller pour entrées
3. FVG rempli (gris) = Zone épuisée, moins pertinente

**Z-Score actuel: {last_z:.2f}**
{"🔴 Surétiré haut" if last_z > 2.0 else "🟢 Surétiré bas" if last_z < -2.0 else "⚪ Normal"}
""")

# Footer
st.markdown("---")
st.caption(f"🔄 Timeframe: {st.session_state.current_timeframe} | 📊 Bougies: {len(df)} | 🔴 Données temps réel")
st.caption(f"⚙️ FVG: {total_fvg} total, {active_fvg} actifs | Vol Mult: {vol_mult}x")

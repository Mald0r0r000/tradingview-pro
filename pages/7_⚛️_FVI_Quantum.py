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

st.set_page_config(layout="wide", page_title="FVI Quantum State")

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
st.title("⚛️ FVI Quantum State [Entropy Filter]")
st.caption("Détection de singularité - Le Move 42 : Compression → Explosion")

# ==========================================
# 1. PARAMÈTRES (SIDEBAR)
# ==========================================
with st.sidebar:
    # Sélecteur de timeframe
    current_tf = timeframe_selector("fvi_quantum")
    
    st.markdown("---")
    st.header("1️⃣ Structure (Position)")
    
    left_bars = st.number_input("Pivot Lookback Left", value=10, min_value=3, max_value=50)
    right_bars = st.number_input("Pivot Lookback Right", value=3, min_value=1, max_value=20)
    
    st.markdown("---")
    st.header("2️⃣ Quantum State (Entropy)")
    
    use_filter = st.checkbox("Filtrer par Entropie (Move 42)", value=True, help="Exige que le marché soit calme avant le mouvement")
    comp_len = st.number_input("Lookback Compression", value=20, min_value=10, max_value=100)
    comp_thresh = st.slider("Seuil Compression", min_value=0.5, max_value=1.5, value=0.8, step=0.05, help="< 1.0 = marché comprimé")
    
    st.markdown("---")
    st.header("3️⃣ Trigger")
    
    vol_mult = st.slider("Volume Spike Factor", min_value=1.0, max_value=3.0, value=1.5, step=0.1)
    fvg_size = st.slider("Min FVG Size %", min_value=0.05, max_value=1.0, value=0.1, step=0.05)
    
    st.markdown("---")
    st.header("🎨 Couleurs")
    color_barrier_high = st.color_picker("Barrier High", "#ff0000")
    color_barrier_low = st.color_picker("Barrier Low", "#00ff00")

# ==========================================
# 2. RÉCUPÉRATION DES DONNÉES
# ==========================================
df = st.session_state.data_manager.get_dataframe(st.session_state.current_timeframe)

min_required = max(left_bars + right_bars, 120)

if df.empty or len(df) < min_required:
    st.warning("⏳ Pas assez de données disponibles. Attendez que plus de bougies arrivent...")
    st.info(f"📊 Données actuelles: {len(df)} bougies | Minimum requis: ~{min_required}")
    st.stop()

# ==========================================
# 3. CALCULS QUANTUM STATE
# ==========================================

# 1. STRUCTURE - Pivot High/Low (Quantum Barriers)
def find_pivot_highs(highs, left, right):
    """Trouve les pivot highs"""
    pivots = []
    for i in range(left, len(highs) - right):
        window = highs.iloc[i-left:i+right+1]
        if highs.iloc[i] == window.max():
            pivots.append((i, highs.iloc[i]))
    return pivots

def find_pivot_lows(lows, left, right):
    """Trouve les pivot lows"""
    pivots = []
    for i in range(left, len(lows) - right):
        window = lows.iloc[i-left:i+right+1]
        if lows.iloc[i] == window.min():
            pivots.append((i, lows.iloc[i]))
    return pivots

with st.spinner("🔄 Calcul des barrières quantiques..."):
    pivot_highs = find_pivot_highs(df['high'], left_bars, right_bars)
    pivot_lows = find_pivot_lows(df['low'], left_bars, right_bars)
    
    # Dernières barrières
    swing_high = pivot_highs[-1][1] if pivot_highs else df['high'].max()
    swing_low = pivot_lows[-1][1] if pivot_lows else df['low'].min()

# 2. ENTROPY (Bollinger Bands Width Compression)
df['bb_basis'] = df['close'].rolling(20).mean()
df['bb_dev'] = df['close'].rolling(20).std()
df['bb_width'] = (df['bb_dev'] * 2) / df['bb_basis']

# Moyenne historique de la largeur (état normal)
df['avg_width'] = df['bb_width'].rolling(100).mean()

# Compression state
df['compression_state'] = df['bb_width'] / df['avg_width']

# État AVANT le mouvement (5 bougies avant)
df['pre_move_state'] = df['compression_state'].shift(5)

# Low entropy = marché comprimé (calme avant la tempête)
df['is_low_entropy'] = df['pre_move_state'] < comp_thresh

# 3. VOLUME SPIKE
df['vol_ma'] = df.get('volume', pd.Series([0]*len(df))).rolling(20).mean()
df['is_vol_spike'] = df.get('volume', pd.Series([0]*len(df))) > (df['vol_ma'] * vol_mult)

# 4. FVG Detection (Fair Value Gaps)
df['bull_fvg'] = (df['low'] > df['high'].shift(2)) & ((df['low'] - df['high'].shift(2)) / df['close'] > fvg_size / 100)
df['bear_fvg'] = (df['high'] < df['low'].shift(2)) & ((df['low'].shift(2) - df['high']) / df['close'] > fvg_size / 100)

# 5. SWEEP Detection
df['sweep_up'] = (df['high'] > swing_high) & (df['close'] < swing_high)
df['sweep_down'] = (df['low'] < swing_low) & (df['close'] > swing_low)

# 6. QUANTUM DECISION
df['condition_valid'] = df['is_low_entropy'] if use_filter else True

# 7. FINAL SIGNALS
df['signal_sell'] = (
    df['sweep_up'] & 
    df['is_vol_spike'] & 
    df['condition_valid'] & 
    (df['bear_fvg'] | (df['close'] < df['open']))
)

df['signal_buy'] = (
    df['sweep_down'] & 
    df['is_vol_spike'] & 
    df['condition_valid'] & 
    (df['bull_fvg'] | (df['close'] > df['open']))
)

# ==========================================
# 4. MÉTRIQUES
# ==========================================
col1, col2, col3, col4 = st.columns(4)

total_buy = df['signal_buy'].sum()
total_sell = df['signal_sell'].sum()
low_entropy_count = df['is_low_entropy'].sum()
current_compression = df['compression_state'].iloc[-1]

with col1:
    st.metric("Compression Actuelle", f"{current_compression:.2f}")

with col2:
    if df['is_low_entropy'].iloc[-1]:
        st.metric("État Quantique", "🔵 LOW ENTROPY", delta="Potentiel")
    else:
        st.metric("État Quantique", "⚪ NORMAL", delta="Standard")

with col3:
    st.metric("Quantum BUY", total_buy)

with col4:
    st.metric("Quantum SELL", total_sell)

# ==========================================
# 5. AFFICHAGE PLOTLY
# ==========================================

# Background color si low entropy actuel
bg_color = 'rgba(0,0,255,0.03)' if df['is_low_entropy'].iloc[-1] else 'rgba(0,0,0,0)'

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

# 2. Quantum Barriers (Pivot Points)
if pivot_highs:
    pivot_high_indices = [p[0] for p in pivot_highs]
    pivot_high_values = [p[1] for p in pivot_highs]
    
    fig.add_trace(go.Scatter(
        x=[df.index[i] for i in pivot_high_indices],
        y=pivot_high_values,
        mode='markers',
        marker=dict(size=8, color=color_barrier_high, opacity=0.6, symbol='circle'),
        name='Quantum Barrier High',
        hovertemplate='Barrier High: $%{y:,.2f}<extra></extra>'
    ))

if pivot_lows:
    pivot_low_indices = [p[0] for p in pivot_lows]
    pivot_low_values = [p[1] for p in pivot_lows]
    
    fig.add_trace(go.Scatter(
        x=[df.index[i] for i in pivot_low_indices],
        y=pivot_low_values,
        mode='markers',
        marker=dict(size=8, color=color_barrier_low, opacity=0.6, symbol='circle'),
        name='Quantum Barrier Low',
        hovertemplate='Barrier Low: $%{y:,.2f}<extra></extra>'
    ))

# 3. Low Entropy States (petits carrés en bas)
low_entropy_df = df[df['is_low_entropy']]
if not low_entropy_df.empty and use_filter:
    fig.add_trace(go.Scatter(
        x=low_entropy_df.index,
        y=low_entropy_df['low'] * 0.995,
        mode='markers',
        marker=dict(size=4, color='blue', opacity=0.7, symbol='square'),
        name='Low Entropy State',
        hovertemplate='Low Entropy<br>Compression: ' + low_entropy_df['compression_state'].round(3).astype(str) + '<extra></extra>'
    ))

# 4. Quantum Signals
buy_signals = df[df['signal_buy']]
sell_signals = df[df['signal_sell']]

if not buy_signals.empty:
    fig.add_trace(go.Scatter(
        x=buy_signals.index,
        y=buy_signals['low'] * 0.997,
        mode='markers+text',
        marker=dict(
            size=18,
            color='lime',
            symbol='diamond',
            line=dict(width=2, color='white')
        ),
        text='Q-BUY',
        textposition='bottom center',
        textfont=dict(color='white', size=9),
        name='Quantum BUY',
        hovertemplate='<b>⚛️ QUANTUM BUY</b><br>Prix: $%{y:,.2f}<br>Entropy: LOW<extra></extra>'
    ))

if not sell_signals.empty:
    fig.add_trace(go.Scatter(
        x=sell_signals.index,
        y=sell_signals['high'] * 1.003,
        mode='markers+text',
        marker=dict(
            size=18,
            color='fuchsia',
            symbol='diamond',
            line=dict(width=2, color='white')
        ),
        text='Q-SELL',
        textposition='top center',
        textfont=dict(color='white', size=9),
        name='Quantum SELL',
        hovertemplate='<b>⚛️ QUANTUM SELL</b><br>Prix: $%{y:,.2f}<br>Entropy: LOW<extra></extra>'
    ))

# Configuration
fig.update_layout(
    height=800,
    paper_bgcolor=bg_color,
    plot_bgcolor='#1e222d',
    xaxis_rangeslider_visible=False,
    xaxis=dict(
        showgrid=True,
        gridcolor='rgba(128,128,128,0.1)',
        color='white'
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor='rgba(128,128,128,0.1)',
        color='white',
        side='right',
        tickformat=',.2f',
        tickprefix='$'
    ),
    font=dict(color='white'),
    hovermode='x unified',
    hoverlabel=dict(
        bgcolor='rgba(0,0,0,0.8)',
        font_size=12,
        font_family="monospace"
    ),
    margin=dict(l=20, r=100, t=40, b=40),
    legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=0.01,
        bgcolor='rgba(0,0,0,0.5)'
    )
)

st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 6. ANALYSE DÉTAILLÉE
# ==========================================
st.subheader("⚛️ Analyse Quantique")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**📊 État du Système**")
    st.write(f"Compression actuelle: {current_compression:.3f}")
    st.write(f"Seuil Low Entropy: < {comp_thresh}")
    st.write(f"Zones Low Entropy: {low_entropy_count} bougies")
    
    if current_compression < comp_thresh:
        st.success("🔵 **Le marché est COMPRIMÉ** - Potentiel d'explosion imminente")
    elif current_compression < 1.0:
        st.info("⚪ Volatilité en dessous de la normale")
    else:
        st.warning("🔴 Volatilité élevée - Marché actif")

with col2:
    st.markdown("**🎯 Signaux Récents**")
    
    recent_signals = df[df['signal_buy'] | df['signal_sell']].tail(5)
    
    if not recent_signals.empty:
        for idx, row in recent_signals.iterrows():
            signal_type = "🟢 Q-BUY" if row['signal_buy'] else "🔴 Q-SELL"
            st.write(f"{signal_type} @ ${row['close']:,.2f}")
    else:
        st.info("Aucun signal quantum récent")

# Explication
st.markdown("---")
st.subheader("💡 Comprendre le Quantum State")

st.markdown(f"""
**⚛️ Le Concept du "Move 42"**

Ce n'est pas un simple sweep. C'est une **SINGULARITÉ**.

**Phase 1 : COMPRESSION (Low Entropy)**
- La volatilité se contracte (BB Width < moyenne)
- Le marché devient anormalement **CALME**
- Les traders s'endorment, les stops s'accumulent
- Compression < {comp_thresh} = État de potentiel maximal

**Phase 2 : SINGULARITÉ (Le Sweep)**
- Le prix sweep une barrière quantique (pivot)
- **EXPLOSION** de volume (>{vol_mult}x la moyenne)
- Rejection immédiate (bougie opposée ou FVG)

**Phase 3 : L'EXPANSION**
- Le marché explose dans la direction opposée
- Les stops sont balayés massivement
- Mean reversion violente

**🎯 Pourquoi "Quantum" ?**
En physique quantique, un système comprimé dans un état de basse entropie libère une énergie massive quand il se décompresse. C'est exactement ce qui se passe ici : **Compression → Singularité → Expansion**.

**Actuel: Compression = {current_compression:.3f}**
{"🔵 LOW ENTROPY - Marché en position de spring" if current_compression < comp_thresh else "⚪ État normal"}
""")

# Footer
st.markdown("---")
st.caption(f"🔄 Timeframe: {st.session_state.current_timeframe} | 📊 Bougies: {len(df)} | 🔴 Données temps réel via Bitget WebSocket")
st.caption(f"⚙️ Paramètres: Pivots L{left_bars}/R{right_bars}, Compression<{comp_thresh}, Vol>{vol_mult}x")

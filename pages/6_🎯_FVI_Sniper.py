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

st.set_page_config(layout="wide", page_title="FVI Sniper")

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
st.title("🎯 FVI Sniper Prototype [Liquidity + Elasticity]")
st.caption("Détection de Sweep de Liquidité avec filtre d'élasticité du prix")

# ==========================================
# 1. PARAMÈTRES (SIDEBAR)
# ==========================================
with st.sidebar:
    # Sélecteur de timeframe
    current_tf = timeframe_selector("fvi_sniper")
    
    st.markdown("---")
    st.header("⚙️ Configuration Sniper")
    
    lookback_liq = st.number_input(
        "Liquidity Lookback (Bars)", 
        value=20, 
        min_value=5, 
        max_value=100,
        help="Période pour identifier les zones de liquidité"
    )
    
    z_length = st.number_input(
        "Elasticity Baseline (Bars)", 
        value=200, 
        min_value=50, 
        max_value=500,
        help="Période pour calculer le Z-score"
    )
    
    vol_mult = st.slider(
        "Volume Anomaly Factor", 
        min_value=1.0, 
        max_value=3.0, 
        value=1.2, 
        step=0.1,
        help="Multiplicateur pour détecter un spike de volume"
    )
    
    z_threshold = st.slider(
        "Z-Score Threshold",
        min_value=0.5,
        max_value=3.0,
        value=1.0,
        step=0.1,
        help="Seuil pour considérer le prix comme 'tendu'"
    )
    
    st.markdown("---")
    show_lines = st.checkbox("Afficher lignes de liquidité", value=True)
    
    st.markdown("---")
    st.header("🎨 Couleurs")
    color_liq_high = st.color_picker("Liquidity High", "#ff0000")
    color_liq_low = st.color_picker("Liquidity Low", "#00ff00")

# ==========================================
# 2. RÉCUPÉRATION DES DONNÉES
# ==========================================
df = st.session_state.data_manager.get_dataframe(st.session_state.current_timeframe)

if df.empty or len(df) < z_length + lookback_liq:
    st.warning("⏳ Pas assez de données disponibles. Attendez que plus de bougies arrivent...")
    st.info(f"📊 Données actuelles: {len(df)} bougies | Minimum requis: ~{z_length + lookback_liq}")
    st.stop()

# ==========================================
# 3. CALCULS SNIPER
# ==========================================

# 1. Elasticity (Z-Score)
df['basis'] = df['close'].rolling(z_length).mean()
df['dev'] = df['close'].rolling(z_length).std()
df['z_score'] = (df['close'] - df['basis']) / df['dev']

# 2. Liquidity Zones
df['liq_high'] = df['high'].rolling(lookback_liq).max().shift(1)
df['liq_low'] = df['low'].rolling(lookback_liq).min().shift(1)

# 3. Volume Filter
df['vol_ma'] = df.get('volume', pd.Series([0]*len(df))).rolling(20).mean()
df['is_vol_spike'] = df.get('volume', pd.Series([0]*len(df))) > (df['vol_ma'] * vol_mult)

# 4. Sweep Detection
df['sweep_high'] = df['high'] > df['liq_high']
df['sweep_low'] = df['low'] < df['liq_low']

# 5. Rejection
df['rejection_bear'] = df['close'] < df['open']  # Bougie rouge
df['rejection_bull'] = df['close'] > df['open']  # Bougie verte

# 6. Elasticity Filter
df['is_extended_up'] = df['z_score'] > z_threshold
df['is_extended_down'] = df['z_score'] < -z_threshold

# 7. Final Signals
df['signal_sell'] = (
    df['sweep_high'] & 
    df['rejection_bear'] & 
    df['is_vol_spike'] & 
    df['is_extended_up']
)

df['signal_buy'] = (
    df['sweep_low'] & 
    df['rejection_bull'] & 
    df['is_vol_spike'] & 
    df['is_extended_down']
)

# ==========================================
# 4. MÉTRIQUES
# ==========================================
col1, col2, col3, col4 = st.columns(4)

total_buy_signals = df['signal_buy'].sum()
total_sell_signals = df['signal_sell'].sum()
last_z = df['z_score'].iloc[-1]

with col1:
    st.metric("Z-Score", f"{last_z:.2f}")

with col2:
    st.metric("Signaux Achat", total_buy_signals)

with col3:
    st.metric("Signaux Vente", total_sell_signals)

with col4:
    if last_z > 2.5:
        st.metric("État", "🔴 SURÉTIRÉ", delta="Haut")
    elif last_z < -2.5:
        st.metric("État", "🟢 SURÉTIRÉ", delta="Bas")
    else:
        st.metric("État", "⚪ NORMAL", delta="Équilibré")

# ==========================================
# 5. AFFICHAGE PLOTLY
# ==========================================

# Déterminer la couleur de fond
bg_color = 'rgba(0,0,0,0)'
if last_z > 2.5:
    bg_color = 'rgba(255,0,0,0.05)'
elif last_z < -2.5:
    bg_color = 'rgba(0,255,0,0.05)'

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

# 2. Liquidity Lines
if show_lines:
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['liq_high'],
        name='Liquidity High',
        mode='markers',
        marker=dict(size=3, color=color_liq_high, opacity=0.5, symbol='circle'),
        hovertemplate='Liq High: $%{y:,.2f}<extra></extra>'
    ))
    
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['liq_low'],
        name='Liquidity Low',
        mode='markers',
        marker=dict(size=3, color=color_liq_low, opacity=0.5, symbol='circle'),
        hovertemplate='Liq Low: $%{y:,.2f}<extra></extra>'
    ))

# 3. Sniper Signals
buy_signals = df[df['signal_buy']]
sell_signals = df[df['signal_sell']]

if not buy_signals.empty:
    fig.add_trace(go.Scatter(
        x=buy_signals.index,
        y=buy_signals['low'] * 0.998,  # Juste en dessous
        mode='markers+text',
        marker=dict(
            size=15,
            color='lime',
            symbol='triangle-up',
            line=dict(width=1, color='white')
        ),
        text='SNIPE',
        textposition='bottom center',
        textfont=dict(color='white', size=10),
        name='Sniper Buy',
        hovertemplate='<b>🎯 SNIPER BUY</b><br>Prix: $%{y:,.2f}<br>Z-Score: ' + buy_signals['z_score'].round(2).astype(str) + '<extra></extra>'
    ))

if not sell_signals.empty:
    fig.add_trace(go.Scatter(
        x=sell_signals.index,
        y=sell_signals['high'] * 1.002,  # Juste au-dessus
        mode='markers+text',
        marker=dict(
            size=15,
            color='red',
            symbol='triangle-down',
            line=dict(width=1, color='white')
        ),
        text='SNIPE',
        textposition='top center',
        textfont=dict(color='white', size=10),
        name='Sniper Sell',
        hovertemplate='<b>🎯 SNIPER SELL</b><br>Prix: $%{y:,.2f}<br>Z-Score: ' + sell_signals['z_score'].round(2).astype(str) + '<extra></extra>'
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
        color='white',
        side='bottom'
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor='rgba(128,128,128,0.1)',
        color='white',
        side='right',
        tickformat=',.2f',
        tickprefix='$',
        fixedrange=False,
        autorange=True
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
# 6. SIGNAUX RÉCENTS
# ==========================================
st.subheader("🎯 Signaux de Trading Récents")

recent_signals = df[df['signal_buy'] | df['signal_sell']].tail(10)

if not recent_signals.empty:
    signals_display = pd.DataFrame({
        'Type': recent_signals.apply(lambda x: '🟢 BUY' if x['signal_buy'] else '🔴 SELL', axis=1),
        'Prix': recent_signals['close'].apply(lambda x: f"${x:,.2f}"),
        'Z-Score': recent_signals['z_score'].apply(lambda x: f"{x:.2f}"),
        'Volume Factor': (recent_signals['volume'] / recent_signals['vol_ma']).apply(lambda x: f"{x:.2f}x"),
    })
    st.dataframe(signals_display, use_container_width=True)
else:
    st.info("Aucun signal de sweep détecté récemment")

# ==========================================
# 7. INTERPRÉTATION
# ==========================================
st.markdown("---")
st.subheader("💡 Comprendre le Sniper")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**🎯 Logique du Sweep**")
    st.markdown("""
    Un **Sweep** se produit quand :
    1. Le prix **casse** une zone de liquidité (High/Low récent)
    2. Mais **rejette** immédiatement (bougie opposée)
    3. Avec un **volume anormal** (spike)
    4. Et le prix est **tendu** (Z-score extrême)
    
    → Les stops sont **balayés** puis le prix reverse !
    """)

with col2:
    st.markdown("**📊 Élasticité (Z-Score)**")
    st.markdown(f"""
    Z-Score = (Prix - Moyenne) / Écart-type
    
    **Actuel : {last_z:.2f}**
    
    - Z > +2.5 : 🔴 Surétiré haut (probable retour)
    - Z < -2.5 : 🟢 Surétiré bas (probable rebond)
    - |Z| < 1 : ⚪ Zone normale
    
    Plus le Z-score est extrême, plus le reverse est violent.
    """)

st.markdown("---")
st.subheader("📈 Stratégie de Trading")

st.markdown(f"""
**🟢 SIGNAL BUY (Sweep bas):**
1. Prix **sweep** le Liquidity Low ({df['liq_low'].iloc[-1]:,.2f})
2. Bougie **verte** (close > open) = Rejection haussière
3. Volume > {vol_mult}x la moyenne
4. Z-Score < -{z_threshold} = Prix tendu à la baisse

→ **Entrée** : Au signal | **Stop** : Sous le low | **TP** : Basis ou Mean Reversion

**🔴 SIGNAL SELL (Sweep haut):**
1. Prix **sweep** le Liquidity High ({df['liq_high'].iloc[-1]:,.2f})
2. Bougie **rouge** (close < open) = Rejection baissière  
3. Volume > {vol_mult}x la moyenne
4. Z-Score > +{z_threshold} = Prix tendu à la hausse

→ **Entrée** : Au signal | **Stop** : Au-dessus du high | **TP** : Basis ou Mean Reversion
""")

# Footer
st.markdown("---")
st.caption(f"🔄 Timeframe: {st.session_state.current_timeframe} | 📊 Bougies: {len(df)} | 🔴 Données temps réel via Bitget WebSocket")
st.caption(f"⚙️ Paramètres: Liq Lookback={lookback_liq}, Z-Length={z_length}, Vol Mult={vol_mult}x")

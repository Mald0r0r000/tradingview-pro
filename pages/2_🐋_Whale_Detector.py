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

st.set_page_config(layout="wide", page_title="Whale Detector")

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
st.title("🐋 Big Trades Whale Detector")
st.caption("Détection d'anomalies de volume - Identifier les gros ordres institutionnels")

# ==========================================
# 1. PARAMÈTRES (SIDEBAR)
# ==========================================
with st.sidebar:
    # Sélecteur de timeframe
    current_tf = timeframe_selector("whale_detector")
    
    st.markdown("---")
    st.header("⚙️ Configuration Whale Detector")
    
    lookback = st.number_input(
        "Lookback Period", 
        value=5, 
        min_value=5, 
        max_value=50,
        help="Période pour calculer la moyenne et l'écart-type"
    )
    
    sensitivity = st.slider(
        "Sensibilité (Sigma)", 
        min_value=1.0, 
        max_value=5.0, 
        value=3.0, 
        step=0.1,
        help="2.0 = Signifikant, 4.0 = Extrem"
    )
    
    st.markdown("---")
    st.header("🎨 Couleurs")
    col1, col2 = st.columns(2)
    with col1:
        color_buy = st.color_picker("Big Buy", "#00ff00")
    with col2:
        color_sell = st.color_picker("Big Sell", "#ff0000")

# ==========================================
# 2. RÉCUPÉRATION DES DONNÉES
# ==========================================
df = st.session_state.data_manager.get_dataframe(st.session_state.current_timeframe)

if df.empty or len(df) < lookback + 10:
    st.warning("⏳ Pas assez de données disponibles. Attendez que plus de bougies arrivent...")
    st.info(f"📊 Données actuelles: {len(df)} bougies | Minimum requis: ~{lookback + 10}")
    st.stop()

# ==========================================
# 3. CALCULS (WHALE DETECTION)
# ==========================================

def detect_whale_trades(df, lookback, sensitivity):
    """
    Détecte les big trades (whale) basé sur les anomalies de volume
    """
    # Calcul du range de chaque bougie
    df['range'] = df['high'] - df['low']
    
    # Volume d'achat intrabar (estimé par la position du close)
    # Si close est proche de high = plus de buying
    df['buy_vol'] = np.where(
        df['range'] == 0, 
        0, 
        ((df['close'] - df['low']) / df['range']) * df.get('volume', 0)
    )
    
    # Volume de vente intrabar (estimé par la distance du close au high)
    # Si close est proche de low = plus de selling
    df['sell_vol'] = np.where(
        df['range'] == 0,
        0,
        ((df['high'] - df['close']) / df['range']) * df.get('volume', 0)
    )
    
    # Moyennes et écarts-types (avec shift pour éviter le look-ahead bias)
    df['avg_buy'] = df['buy_vol'].rolling(lookback).mean().shift(1)
    df['std_buy'] = df['buy_vol'].rolling(lookback).std().shift(1)
    
    df['avg_sell'] = df['sell_vol'].rolling(lookback).mean().shift(1)
    df['std_sell'] = df['sell_vol'].rolling(lookback).std().shift(1)
    
    # Seuils de détection
    df['thresh_buy'] = df['avg_buy'] + df['std_buy'] * sensitivity
    df['thresh_sell'] = df['avg_sell'] + df['std_sell'] * sensitivity
    
    # Détection des différents niveaux
    # Tier 1 (Small)
    df['is_buy_t1'] = df['buy_vol'] > df['thresh_buy']
    df['is_sell_t1'] = df['sell_vol'] > df['thresh_sell']
    
    # Tier 2 (Medium)
    df['thresh_buy_t2'] = df['avg_buy'] + df['std_buy'] * (sensitivity + 1.5)
    df['thresh_sell_t2'] = df['avg_sell'] + df['std_sell'] * (sensitivity + 1.5)
    df['is_buy_t2'] = df['buy_vol'] > df['thresh_buy_t2']
    df['is_sell_t2'] = df['sell_vol'] > df['thresh_sell_t2']
    
    # Tier 3 (Large)
    df['thresh_buy_t3'] = df['avg_buy'] + df['std_buy'] * (sensitivity + 3.0)
    df['thresh_sell_t3'] = df['avg_sell'] + df['std_sell'] * (sensitivity + 3.0)
    df['is_buy_t3'] = df['buy_vol'] > df['thresh_buy_t3']
    df['is_sell_t3'] = df['sell_vol'] > df['thresh_sell_t3']
    
    # Position estimée du trade
    # Achats = proche du low → moyenne entre close et low
    df['pos_buy'] = (df['close'] + df['low']) / 2
    # Ventes = proche du high → moyenne entre close et high
    df['pos_sell'] = (df['close'] + df['high']) / 2
    
    return df

# Exécuter la détection
with st.spinner("🔄 Analyse des volumes..."):
    df = detect_whale_trades(df, lookback, sensitivity)

# ==========================================
# 4. MÉTRIQUES
# ==========================================
col1, col2, col3, col4 = st.columns(4)

total_buy_whales = df[df['is_buy_t1']].shape[0]
total_sell_whales = df[df['is_sell_t1']].shape[0]
big_buy_waves = df[df['is_buy_t3']].shape[0]
big_sell_waves = df[df['is_sell_t3']].shape[0]

with col1:
    st.metric("Total Big Buys", total_buy_whales, delta=f"+{big_buy_waves} Large")

with col2:
    st.metric("Total Big Sells", total_sell_whales, delta=f"+{big_sell_waves} Large")

with col3:
    ratio = total_buy_whales / max(total_sell_whales, 1)
    st.metric("Buy/Sell Ratio", f"{ratio:.2f}x")

with col4:
    last_price = df['close'].iloc[-1]
    st.metric("Prix Actuel", f"${last_price:,.2f}")

# ==========================================
# 5. AFFICHAGE PLOTLY
# ==========================================

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

# 2. Big Buys (3 tailles)
# Small (Tier 1 only)
buy_t1_only = df[(df['is_buy_t1']) & (~df['is_buy_t2'])]
if not buy_t1_only.empty:
    fig.add_trace(go.Scatter(
        x=buy_t1_only.index,
        y=buy_t1_only['pos_buy'],
        mode='markers',
        marker=dict(
            size=8,
            color=color_buy,
            symbol='circle',
            line=dict(width=1, color='white')
        ),
        name='Big Buy (S)',
        hovertemplate='<b>Big Buy Small</b><br>Prix: $%{y:,.2f}<extra></extra>'
    ))

# Medium (Tier 2, not 3)
buy_t2_only = df[(df['is_buy_t2']) & (~df['is_buy_t3'])]
if not buy_t2_only.empty:
    fig.add_trace(go.Scatter(
        x=buy_t2_only.index,
        y=buy_t2_only['pos_buy'],
        mode='markers',
        marker=dict(
            size=12,
            color=color_buy,
            symbol='circle',
            line=dict(width=1, color='white')
        ),
        name='Big Buy (M)',
        hovertemplate='<b>Big Buy Medium</b><br>Prix: $%{y:,.2f}<extra></extra>'
    ))

# Large (Tier 3)
buy_t3 = df[df['is_buy_t3']]
if not buy_t3.empty:
    fig.add_trace(go.Scatter(
        x=buy_t3.index,
        y=buy_t3['pos_buy'],
        mode='markers',
        marker=dict(
            size=16,
            color=color_buy,
            symbol='circle',
            line=dict(width=2, color='white')
        ),
        name='Big Buy (L)',
        hovertemplate='<b>🐋 WHALE BUY 🐋</b><br>Prix: $%{y:,.2f}<extra></extra>'
    ))

# 3. Big Sells (3 tailles)
# Small
sell_t1_only = df[(df['is_sell_t1']) & (~df['is_sell_t2'])]
if not sell_t1_only.empty:
    fig.add_trace(go.Scatter(
        x=sell_t1_only.index,
        y=sell_t1_only['pos_sell'],
        mode='markers',
        marker=dict(
            size=8,
            color=color_sell,
            symbol='circle',
            line=dict(width=1, color='white')
        ),
        name='Big Sell (S)',
        hovertemplate='<b>Big Sell Small</b><br>Prix: $%{y:,.2f}<extra></extra>'
    ))

# Medium
sell_t2_only = df[(df['is_sell_t2']) & (~df['is_sell_t3'])]
if not sell_t2_only.empty:
    fig.add_trace(go.Scatter(
        x=sell_t2_only.index,
        y=sell_t2_only['pos_sell'],
        mode='markers',
        marker=dict(
            size=12,
            color=color_sell,
            symbol='circle',
            line=dict(width=1, color='white')
        ),
        name='Big Sell (M)',
        hovertemplate='<b>Big Sell Medium</b><br>Prix: $%{y:,.2f}<extra></extra>'
    ))

# Large
sell_t3 = df[df['is_sell_t3']]
if not sell_t3.empty:
    fig.add_trace(go.Scatter(
        x=sell_t3.index,
        y=sell_t3['pos_sell'],
        mode='markers',
        marker=dict(
            size=16,
            color=color_sell,
            symbol='circle',
            line=dict(width=2, color='white')
        ),
        name='Big Sell (L)',
        hovertemplate='<b>🐋 WHALE SELL 🐋</b><br>Prix: $%{y:,.2f}<extra></extra>'
    ))

# Configuration du layout
fig.update_layout(
    height=800,
    paper_bgcolor='#0e1117',
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
    hovermode='closest',
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
st.subheader("📊 Analyse des Whale Trades")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**🟢 Big Buys par Taille**")
    st.write(f"Large (🐋): {big_buy_waves}")
    st.write(f"Medium: {df[(df['is_buy_t2']) & (~df['is_buy_t3'])].shape[0]}")
    st.write(f"Small: {df[(df['is_buy_t1']) & (~df['is_buy_t2'])].shape[0]}")
    
    if big_buy_waves > 0:
        st.success(f"⚡ {big_buy_waves} whale buy(s) détecté(s) - Pression acheteuse institutionnelle")

with col2:
    st.markdown("**🔴 Big Sells par Taille**")
    st.write(f"Large (🐋): {big_sell_waves}")
    st.write(f"Medium: {df[(df['is_sell_t2']) & (~df['is_sell_t3'])].shape[0]}")
    st.write(f"Small: {df[(df['is_sell_t1']) & (~df['is_sell_t2'])].shape[0]}")
    
    if big_sell_waves > 0:
        st.warning(f"⚡ {big_sell_waves} whale sell(s) détecté(s) - Pression vendeuse institutionnelle")

# Interprétation
st.markdown("---")
st.subheader("💡 Interprétation")

if ratio > 1.5:
    st.success("🟢 **Sentiment Bullish** - Plus de big buys que de big sells. Les institutions accumulent.")
elif ratio < 0.67:
    st.error("🔴 **Sentiment Bearish** - Plus de big sells que de big buys. Les institutions distribuent.")
else:
    st.info("⚖️ **Sentiment Neutre** - Équilibre entre achats et ventes institutionnels.")

# Footer
st.markdown("---")
st.caption(f"🔄 Timeframe: {st.session_state.current_timeframe} | 📊 Bougies analysées: {len(df)} | 🔴 Données temps réel via Bitget WebSocket")
st.caption(f"⚙️ Paramètres: Lookback={lookback}, Sensibilité={sensitivity}σ")

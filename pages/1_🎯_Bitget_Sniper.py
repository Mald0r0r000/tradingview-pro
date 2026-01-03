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

st.set_page_config(layout="wide", page_title="Bitget Sniper + GEX")

# ==========================================
# SESSION STATE & DONNÉES PARTAGÉES
# ==========================================
# Récupérer le data_manager depuis la session state globale (partagée entre pages)
if "data_manager" not in st.session_state:
    st.session_state.data_manager = DataManager(max_candles=500)

if "current_timeframe" not in st.session_state:
    st.session_state.current_timeframe = "1m"

# ==========================================
# TITRE
# ==========================================
st.title("🎯 Bitget Sniper + GEX [Ultimate]")
st.caption("Analyse des liquidations et niveaux GEX avec données temps réel")

# ==========================================
# 1. PARAMÈTRES (SIDEBAR)
# ==========================================
with st.sidebar:
    st.header("📊 GEX Levels (Daily)")
    st.caption("Mettez à jour ces niveaux quotidiennement")
    call_wall = st.number_input("Call Wall", value=100000.0, format="%.2f")
    put_wall = st.number_input("Put Wall", value=85000.0, format="%.2f")
    zero_gamma = st.number_input("Zero Gamma", value=88764.28, format="%.2f")
    
    st.markdown("---")
    st.header("⚙️ Liquidation Tiers")
    len_short = st.number_input("Tier 1 (Scalping)", value=3, min_value=1, max_value=50)
    len_mid = st.number_input("Tier 2 (Intraday)", value=30, min_value=1, max_value=200)
    len_long = st.number_input("Tier 3 (Swing)", value=90, min_value=1, max_value=500)
    
    st.markdown("---")
    st.header("🔢 Leviers à Afficher")
    show_125x = st.checkbox("125x", value=True)
    show_100x = st.checkbox("100x", value=True)
    show_50x = st.checkbox("50x", value=True)
    show_25x = st.checkbox("25x", value=False)
    
    st.markdown("---")
    st.header("🎨 Couleurs")
    col1, col2 = st.columns(2)
    with col1:
        color_longs = st.color_picker("Liq Longs", "#9d72ff")
    with col2:
        color_shorts = st.color_picker("Liq Shorts", "#69d5ce")

# ==========================================
# 2. RÉCUPÉRATION DES DONNÉES
# ==========================================
df = st.session_state.data_manager.get_dataframe(st.session_state.current_timeframe)

if df.empty or len(df) < max(len_short, len_mid, len_long) * 2:
    st.warning("⏳ Pas assez de données disponibles. Attendez que plus de bougies arrivent du WebSocket...")
    st.info(f"📊 Données actuelles: {len(df)} bougies | Minimum requis: ~{max(len_short, len_mid, len_long) * 2}")
    st.stop()

# ==========================================
# 3. LOGIQUE CALCUL LIQUIDATIONS
# ==========================================

def calculate_liquidation_price(price, leverage, is_long):
    """Calcule le prix de liquidation selon la logique Bitget"""
    mm_factor = 0.8
    if leverage >= 100:
        mm_factor = 0.50
    elif leverage >= 50:
        mm_factor = 0.60
    elif leverage >= 20:
        mm_factor = 0.80
    
    movement = (price / leverage) * mm_factor
    return price - movement if is_long else price + movement

def find_pivot_highs(highs, lookback):
    """Trouve les pivot highs"""
    pivots = []
    for i in range(lookback, len(highs) - lookback):
        window = highs.iloc[i-lookback:i+lookback+1]
        if highs.iloc[i] == window.max():
            pivots.append((i, highs.iloc[i]))
    return pivots

def find_pivot_lows(lows, lookback):
    """Trouve les pivot lows"""
    pivots = []
    for i in range(lookback, len(lows) - lookback):
        window = lows.iloc[i-lookback:i+lookback+1]
        if lows.iloc[i] == window.min():
            pivots.append((i, lows.iloc[i]))
    return pivots

def create_liquidation_lines(df, pivots, leverages, is_long):
    """Crée les lignes de liquidation avec logique Pac-Man"""
    lines = []
    
    for pivot_idx, pivot_price in pivots:
        for lev in leverages:
            liq_price = calculate_liquidation_price(pivot_price, lev, is_long)
            
            # Trouver quand la ligne est touchée (Pac-Man)
            end_idx = len(df) - 1
            
            subset = df.iloc[pivot_idx+1:]
            if is_long:
                # Liq de Long touchée si LOW <= prix liq
                hits = subset[subset['low'] <= liq_price]
            else:
                # Liq de Short touchée si HIGH >= prix liq
                hits = subset[subset['high'] >= liq_price]
            
            if not hits.empty:
                end_idx = hits.index[0]
            
            lines.append({
                'start_idx': pivot_idx,
                'end_idx': end_idx,
                'price': liq_price,
                'leverage': lev,
                'is_long': is_long,
                'active': end_idx == len(df) - 1
            })
    
    return lines

# Préparation des leviers actifs
active_leverages = []
if show_125x: active_leverages.append(125)
if show_100x: active_leverages.append(100)
if show_50x: active_leverages.append(50)
if show_25x: active_leverages.append(25)

if not active_leverages:
    st.warning("⚠️ Veuillez activer au moins un levier dans la sidebar")
    st.stop()

# Calcul des pivots et des lignes pour les 3 tiers
with st.spinner("🔄 Calcul des liquidations..."):
    all_lines = []
    
    # Tier 1 (Court)
    ph_short = find_pivot_highs(df['high'], len_short)
    pl_short = find_pivot_lows(df['low'], len_short)
    all_lines.extend(create_liquidation_lines(df, ph_short, active_leverages, False))
    all_lines.extend(create_liquidation_lines(df, pl_short, active_leverages, True))
    
    # Tier 2 (Moyen)
    ph_mid = find_pivot_highs(df['high'], len_mid)
    pl_mid = find_pivot_lows(df['low'], len_mid)
    all_lines.extend(create_liquidation_lines(df, ph_mid, active_leverages, False))
    all_lines.extend(create_liquidation_lines(df, pl_mid, active_leverages, True))
    
    # Tier 3 (Long)
    ph_long = find_pivot_highs(df['high'], len_long)
    pl_long = find_pivot_lows(df['low'], len_long)
    all_lines.extend(create_liquidation_lines(df, ph_long, active_leverages, False))
    all_lines.extend(create_liquidation_lines(df, pl_long, active_leverages, True))

# ==========================================
# 4. MÉTRIQUES
# ==========================================
col1, col2, col3, col4 = st.columns(4)
last_price = df['close'].iloc[-1]

with col1:
    st.metric("Prix Actuel", f"${last_price:,.2f}")

with col2:
    distance_cw = ((call_wall - last_price) / last_price) * 100
    st.metric("Distance Call Wall", f"{distance_cw:.2f}%")

with col3:
    distance_pw = ((last_price - put_wall) / last_price) * 100
    st.metric("Distance Put Wall", f"{distance_pw:.2f}%")

with col4:
    total_lines = len([l for l in all_lines if l['active']])
    st.metric("Lignes Actives", total_lines)

# ==========================================
# 5. AFFICHAGE PLOTLY
# ==========================================

# Déterminer la couleur de fond selon GEX
bg_color_gex = "rgba(0, 50, 0, 0.05)" if last_price > zero_gamma else "rgba(50, 0, 0, 0.05)"

fig = go.Figure()

# 1. Candlestick avec hover data détaillé
fig.add_trace(go.Candlestick(
    x=df.index,
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    name="BTCUSDT",
    increasing_line_color='#26a69a',
    decreasing_line_color='#ef5350',
    hovertext=[
        f"O: {o:.2f}<br>H: {h:.2f}<br>L: {l:.2f}<br>C: {c:.2f}<br>V: {v:.0f}" 
        for o, h, l, c, v in zip(df['open'], df['high'], df['low'], df['close'], df.get('volume', [0]*len(df)))
    ],
    hoverinfo='text+x'
))

# 2. GEX Walls
fig.add_hline(
    y=call_wall,
    line_width=3,
    line_color="#9757df",
    line_dash="solid",
    annotation_text=f"Call Wall: ${call_wall:,.2f}",
    annotation_position="right"
)
fig.add_hline(
    y=put_wall,
    line_width=3,
    line_color="#5bc4c2",
    line_dash="solid",
    annotation_text=f"Put Wall: ${put_wall:,.2f}",
    annotation_position="right"
)
fig.add_hline(
    y=zero_gamma,
    line_width=2,
    line_color="#dde0e3",
    line_dash="dash",
    annotation_text=f"Zero Gamma: ${zero_gamma:,.2f}",
    annotation_position="right"
)

# 3. Lignes de Liquidation avec Hover Interactif
for line in all_lines:
    # Couleur
    base_color = color_longs if line['is_long'] else color_shorts
    
    # Style selon levier
    if line['leverage'] == 125:
        dash = "dot"
        width = 1
    elif line['leverage'] == 100:
        dash = "dot"
        width = 2
    elif line['leverage'] == 50:
        dash = "dash"
        width = 1
    else:  # 25x
        dash = "solid"
        width = 2
    
    # Opacité selon statut
    opacity = 0.7 if line['active'] else 0.3
    
    # Dessiner la ligne (shape)
    fig.add_shape(
        type="line",
        x0=line['start_idx'],
        y0=line['price'],
        x1=line['end_idx'],
        y1=line['price'],
        line=dict(color=base_color, width=width, dash=dash),
        opacity=opacity
    )
    
    # Ajouter une trace invisible pour le hover (au milieu de la ligne)
    mid_x = (line['start_idx'] + line['end_idx']) / 2
    
    # Texte du hover
    direction = "LONG 🟢" if line['is_long'] else "SHORT 🔴"
    status_text = "✅ ACTIVE" if line['active'] else "❌ TOUCHÉE"
    hover_text = (
        f"<b>{direction} Liquidation {line['leverage']}x</b><br>"
        f"Prix: <b>${line['price']:,.2f}</b><br>"
        f"Statut: {status_text}<br>"
        f"Zone: {'Entrée/SL' if line['is_long'] else 'TP'}"
    )
    
    fig.add_trace(go.Scatter(
        x=[mid_x],
        y=[line['price']],
        mode='markers',
        marker=dict(size=8, color=base_color, opacity=0),  # Invisible
        hovertext=hover_text,
        hoverinfo='text',
        showlegend=False,
        name=''
    ))

# Configuration du layout
fig.update_layout(
    height=800,
    paper_bgcolor=bg_color_gex,
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
        side='right',  # Axe des prix à droite
        tickformat=',.2f',  # Format avec virgules et 2 décimales
        tickprefix='$',  # Préfixe dollar
        fixedrange=False,  # Permet le zoom
        autorange=True
    ),
    font=dict(color='white'),
    hovermode='x unified',
    hoverlabel=dict(
        bgcolor='rgba(0,0,0,0.8)',
        font_size=12,
        font_family="monospace"
    ),
    margin=dict(l=20, r=100, t=40, b=40)  # Plus de marge à droite pour l'axe Y
)

st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 6. STATISTIQUES
# ==========================================
st.subheader("📈 Statistiques des Liquidations")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Lignes Actives par Levier**")
    for lev in sorted(active_leverages, reverse=True):
        count = len([l for l in all_lines if l['leverage'] == lev and l['active']])
        st.write(f"{lev}x: {count} lignes")

with col2:
    st.markdown("**Longs vs Shorts**")
    longs_active = len([l for l in all_lines if l['is_long'] and l['active']])
    shorts_active = len([l for l in all_lines if not l['is_long'] and l['active']])
    st.write(f"Longs: {longs_active}")
    st.write(f"Shorts: {shorts_active}")

with col3:
    st.markdown("**Zone GEX**")
    if last_price > zero_gamma:
        st.success("🟢 Au-dessus du Zero Gamma (Positif)")
    else:
        st.error("🔴 En-dessous du Zero Gamma (Négatif)")
    
    st.write(f"Distance: {abs((last_price - zero_gamma) / last_price * 100):.2f}%")

# Footer
st.markdown("---")
st.caption(f"🔄 Timeframe: {st.session_state.current_timeframe} | 📊 Bougies: {len(df)} | 🔴 Données temps réel via Bitget WebSocket")

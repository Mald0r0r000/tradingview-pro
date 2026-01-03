import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import sys
import os

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_manager import DataManager

st.set_page_config(layout="wide", page_title="Directional RVOL")

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
st.title("💎 Gemini - Directional RVOL & Order Flow")
st.caption("Détection d'absorption de volume - Identifier les Limit Orders institutionnels")

# ==========================================
# 1. PARAMÈTRES (SIDEBAR)
# ==========================================
with st.sidebar:
    st.header("⚙️ Configuration RVOL")
    
    rvol_threshold = st.slider(
        "Seuil RVOL (multiplier)", 
        min_value=1.0, 
        max_value=5.0, 
        value=2.0, 
        step=0.1,
        help="Un RVOL de 2.0x signifie que le volume est 2x supérieur à la normale"
    )
    
    lookback_avg = st.number_input(
        "Moyenne Historique (périodes)", 
        value=20, 
        min_value=10, 
        max_value=100,
        help="Nombre de périodes pour calculer le volume moyen"
    )
    
    st.markdown("---")
    st.header("🎨 Couleurs")
    col1, col2 = st.columns(2)
    with col1:
        color_buy_high = st.color_picker("Buy Anormal", "#00e676")
        color_buy_low = st.color_picker("Buy Normal", "#00695c")
    with col2:
        color_sell_high = st.color_picker("Sell Anormal", "#ff1744")
        color_sell_low = st.color_picker("Sell Normal", "#b71c1c")

# ==========================================
# 2. RÉCUPÉRATION DES DONNÉES
# ==========================================
df = st.session_state.data_manager.get_dataframe(st.session_state.current_timeframe)

if df.empty or len(df) < lookback_avg + 10:
    st.warning("⏳ Pas assez de données disponibles. Attendez que plus de bougies arrivent...")
    st.info(f"📊 Données actuelles: {len(df)} bougies | Minimum requis: ~{lookback_avg + 10}")
    st.stop()

# ==========================================
# 3. CALCULS (DIRECTIONAL RVOL)
# ==========================================

def calculate_directional_rvol(df, lookback, threshold):
    """
    Calcule le RVOL directionnel et détecte les absorptions
    """
    # Séparation historique buy/sell basée sur la direction de la bougie
    df['hist_buy_vol'] = np.where(df['close'] > df['open'], df.get('volume', 0), 0)
    df['hist_sell_vol'] = np.where(df['close'] < df['open'], df.get('volume', 0), 0)
    
    # Moyennes historiques (ce qui est "normal")
    df['avg_buy_vol'] = df['hist_buy_vol'].rolling(lookback).mean()
    df['avg_sell_vol'] = df['hist_sell_vol'].rolling(lookback).mean()
    
    # Protection contre division par zéro
    df['avg_buy_vol'] = df['avg_buy_vol'].replace(0, 1)
    df['avg_sell_vol'] = df['avg_sell_vol'].replace(0, 1)
    
    # Volume actuel (approximation: même logique que historique)
    df['curr_buy_vol'] = df['hist_buy_vol']
    df['curr_sell_vol'] = df['hist_sell_vol']
    
    # RVOL Directionnel (Relative Volume)
    df['rvol_buy'] = df['curr_buy_vol'] / df['avg_buy_vol']
    df['rvol_sell'] = df['curr_sell_vol'] / df['avg_sell_vol']
    
    # Delta Net (pour contexte)
    df['net_delta'] = df['curr_buy_vol'] - df['curr_sell_vol']
    
    # Couleurs selon le RVOL
    df['buy_color'] = np.where(
        df['rvol_buy'] > threshold,
        color_buy_high,
        color_buy_low
    )
    df['sell_color'] = np.where(
        df['rvol_sell'] > threshold,
        color_sell_high,
        color_sell_low
    )
    
    # DÉTECTION DES ABSORPTIONS
    # Absorption Buy: RVOL Buy élevé mais prix baisse (vendeurs absorbent les achats)
    df['absorption_buy'] = (df['rvol_buy'] > threshold) & (df['close'] < df['open'])
    
    # Absorption Sell: RVOL Sell élevé mais prix monte (acheteurs absorbent les ventes)
    df['absorption_sell'] = (df['rvol_sell'] > threshold) & (df['close'] > df['open'])
    
    return df

# Exécuter le calcul
with st.spinner("🔄 Calcul du RVOL directionnel..."):
    df = calculate_directional_rvol(df, lookback_avg, rvol_threshold)

# ==========================================
# 4. MÉTRIQUES
# ==========================================
col1, col2, col3, col4 = st.columns(4)

total_absorptions_buy = df['absorption_buy'].sum()
total_absorptions_sell = df['absorption_sell'].sum()
avg_rvol_buy = df['rvol_buy'].tail(20).mean()
avg_rvol_sell = df['rvol_sell'].tail(20).mean()

with col1:
    st.metric("Absorptions Buy", total_absorptions_buy, help="Limite orders acheteurs absorbant les vendeurs")

with col2:
    st.metric("Absorptions Sell", total_absorptions_sell, help="Limite orders vendeurs absorbant les acheteurs")

with col3:
    st.metric("RVOL Buy Moyen (20)", f"{avg_rvol_buy:.2f}x")

with col4:
    st.metric("RVOL Sell Moyen (20)", f"{avg_rvol_sell:.2f}x")

# ==========================================
# 5. AFFICHAGE PLOTLY (Double Subplot)
# ==========================================

# Créer 2 subplots: Price + RVOL
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=[0.6, 0.4],
    subplot_titles=("Prix BTCUSDT", "Directional RVOL (Buy vs Sell)")
)

# 1. Candlestick (Subplot 1)
fig.add_trace(go.Candlestick(
    x=df.index,
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    name="BTCUSDT",
    increasing_line_color='#26a69a',
    decreasing_line_color='#ef5350',
    showlegend=False
), row=1, col=1)

# Marqueurs d'absorption sur le prix
# Absorption Buy (diamant jaune en bas)
absorption_buy_df = df[df['absorption_buy']]
if not absorption_buy_df.empty:
    fig.add_trace(go.Scatter(
        x=absorption_buy_df.index,
        y=absorption_buy_df['low'] * 0.999,  # Juste en dessous du low
        mode='markers',
        marker=dict(
            size=10,
            color='yellow',
            symbol='diamond',
            line=dict(width=1, color='black')
        ),
        name='Absorption Buy',
        hovertemplate='<b>🔶 ABSORPTION BUY</b><br>Limite Orders Acheteurs<br>Prix: $%{y:,.2f}<extra></extra>',
        showlegend=True
    ), row=1, col=1)

# Absorption Sell (diamant fuchsia en haut)
absorption_sell_df = df[df['absorption_sell']]
if not absorption_sell_df.empty:
    fig.add_trace(go.Scatter(
        x=absorption_sell_df.index,
        y=absorption_sell_df['high'] * 1.001,  # Juste au-dessus du high
        mode='markers',
        marker=dict(
            size=10,
            color='fuchsia',
            symbol='diamond',
            line=dict(width=1, color='black')
        ),
        name='Absorption Sell',
        hovertemplate='<b>🔷 ABSORPTION SELL</b><br>Limite Orders Vendeurs<br>Prix: $%{y:,.2f}<extra></extra>',
        showlegend=True
    ), row=1, col=1)

# 2. Volume Directionnel (Subplot 2) - Format Miroir
# Buy Volume (barres vertes vers le haut)
fig.add_trace(go.Bar(
    x=df.index,
    y=df['curr_buy_vol'],
    name='Buy Volume',
    marker=dict(
        color=df['buy_color'],
        line=dict(width=0)
    ),
    hovertemplate='<b>Buy Volume</b><br>Volume: %{y:,.0f}<br>RVOL: ' + df['rvol_buy'].round(2).astype(str) + 'x<extra></extra>',
    showlegend=True
), row=2, col=1)

# Sell Volume (barres rouges vers le bas - valeurs négatives)
fig.add_trace(go.Bar(
    x=df.index,
    y=-df['curr_sell_vol'],  # Négatif pour effet miroir
    name='Sell Volume',
    marker=dict(
        color=df['sell_color'],
        line=dict(width=0)
    ),
    hovertemplate='<b>Sell Volume</b><br>Volume: %{y:,.0f}<br>RVOL: ' + df['rvol_sell'].round(2).astype(str) + 'x<extra></extra>',
    showlegend=True
), row=2, col=1)

# Ligne zéro
fig.add_hline(y=0, line_width=1, line_color='gray', line_dash='dash', row=2, col=1)

# Configuration du layout
fig.update_layout(
    height=900,
    paper_bgcolor='#0e1117',
    plot_bgcolor='#1e222d',
    xaxis_rangeslider_visible=False,
    font=dict(color='white'),
    hovermode='x unified',
    hoverlabel=dict(
        bgcolor='rgba(0,0,0,0.8)',
        font_size=12,
        font_family="monospace"
    ),
    margin=dict(l=20, r=100, t=60, b=40),
    legend=dict(
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=0.01,
        bgcolor='rgba(0,0,0,0.5)'
    ),
    barmode='relative'  # Important pour le mode miroir
)

# Update axes
fig.update_xaxes(
    showgrid=True,
    gridcolor='rgba(128,128,128,0.1)',
    color='white',
    row=2, col=1
)

fig.update_yaxes(
    showgrid=True,
    gridcolor='rgba(128,128,128,0.1)',
    color='white',
    side='right',
    tickformat=',.2f',
    tickprefix='$',
    row=1, col=1
)

fig.update_yaxes(
    showgrid=True,
    gridcolor='rgba(128,128,128,0.1)',
    color='white',
    side='right',
    title='Volume',
    row=2, col=1
)

st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 6. SIGNAUX ET INTERPRÉTATION
# ==========================================
st.subheader("🎯 Signaux de Trading")

# Dernière absorption
last_rows = df.tail(5)
recent_absorption_buy = last_rows['absorption_buy'].any()
recent_absorption_sell = last_rows['absorption_sell'].any()

col1, col2 = st.columns(2)

with col1:
    if recent_absorption_buy:
        st.success("🟢 **SIGNAL LONG** - Absorption Buy récente détectée")
        st.write("**Interprétation:** Les vendeurs sont absorbés par des limit orders acheteurs massifs. Les institutions accumulent. Potentiel retournement haussier.")
    else:
        st.info("Pas d'absorption buy récente (5 dernières bougies)")

with col2:
    if recent_absorption_sell:
        st.error("🔴 **SIGNAL SHORT** - Absorption Sell récente détectée")
        st.write("**Interprétation:** Les acheteurs sont absorbés par des limit orders vendeurs massifs. Les institutions distribuent. Potentiel retournement baissier.")
    else:
        st.info("Pas d'absorption sell récente (5 dernières bougies)")

# Tableau des absorptions récentes
st.markdown("---")
st.subheader("📋 Historique des Absorptions")

absorptions = df[df['absorption_buy'] | df['absorption_sell']].tail(10)
if not absorptions.empty:
    display_df = pd.DataFrame({
        'Type': absorptions.apply(lambda x: '🟢 BUY' if x['absorption_buy'] else '🔴 SELL', axis=1),
        'Prix': absorptions['close'].apply(lambda x: f"${x:,.2f}"),
        'RVOL Buy': absorptions['rvol_buy'].apply(lambda x: f"{x:.2f}x"),
        'RVOL Sell': absorptions['rvol_sell'].apply(lambda x: f"{x:.2f}x"),
        'Delta': absorptions['net_delta'].apply(lambda x: f"{x:,.0f}")
    })
    st.dataframe(display_df, use_container_width=True)
else:
    st.info("Aucune absorption détectée dans l'historique récent")

# Explication
st.markdown("---")
st.subheader("💡 Comprendre le RVOL Directionnel")

st.markdown(f"""
**RVOL (Relative Volume)** = Volume actuel / Volume moyen historique

**RVOL Buy** : Mesure si les **acheteurs** sont plus agressifs que d'habitude.
- RVOL Buy > {rvol_threshold}x = Volume d'achat anormalement élevé

**RVOL Sell** : Mesure si les **vendeurs** sont plus agressifs que d'habitude.
- RVOL Sell > {rvol_threshold}x = Volume de vente anormalement élevé

**Absorptions** :
- 🔶 **Absorption Buy** : RVOL Buy élevé MAIS prix baisse → Limit orders acheteurs absorbent les vendeurs
- 🔷 **Absorption Sell** : RVOL Sell élevé MAIS prix monte → Limit orders vendeurs absorbent les acheteurs

Ces absorptions indiquent souvent des **zones de retournement** où les institutions défendent un niveau.
""")

# Footer
st.markdown("---")
st.caption(f"🔄 Timeframe: {st.session_state.current_timeframe} | 📊 Bougies: {len(df)} | 🔴 Données temps réel via Bitget WebSocket")
st.caption(f"⚙️ Paramètres: Seuil RVOL={rvol_threshold}x, Moyenne={lookback_avg} périodes")

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
from components.timeframe_selector import timeframe_selector

st.set_page_config(layout="wide", page_title="KDJ Indicator")

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
st.title("📈 KDJ Indicator [Modern Aesthetics]")
st.caption("Oscillateur stochastique modifié avec nuage K/D et ligne J dynamique")

# ==========================================
# 1. PARAMÈTRES (SIDEBAR)
# ==========================================
with st.sidebar:
    # Sélecteur de timeframe
    current_tf = timeframe_selector("kdj_indicator")
    
    st.markdown("---")
    st.header("⚙️ Configuration KDJ")
    
    period = st.number_input(
        "Période (Lookback)", 
        value=9, 
        min_value=3, 
        max_value=50,
        help="Période pour calculer le RSV"
    )
    
    st.markdown("---")
    st.header("🎨 Couleurs Nuage K/D")
    col1, col2 = st.columns(2)
    with col1:
        color_kd_bull = st.color_picker("Bullish Cloud", "#3fbeb4")
    with col2:
        color_kd_bear = st.color_picker("Bearish Cloud", "#9144df")
    
    st.markdown("---")
    st.header("🎨 Couleurs Ligne J")
    color_j_neutral = st.color_picker("J Neutral", "#808080")
    color_j_ob = st.color_picker("J Overbought", "#6d03b9")
    color_j_os = st.color_picker("J Oversold", "#48d5d2")

# ==========================================
# 2. RÉCUPÉRATION DES DONNÉES
# ==========================================
df = st.session_state.data_manager.get_dataframe(st.session_state.current_timeframe)

if df.empty or len(df) < period + 10:
    st.warning("⏳ Pas assez de données disponibles. Attendez que plus de bougies arrivent...")
    st.info(f"📊 Données actuelles: {len(df)} bougies | Minimum requis: ~{period + 10}")
    st.stop()

# ==========================================
# 3. CALCULS KDJ
# ==========================================

def calculate_kdj(df, period):
    """
    Calcule les valeurs KDJ (Stochastic modifié)
    K = (2*K[1] + RSV) / 3
    D = (2*D[1] + K) / 3
    J = 3*K - 2*D
    """
    # RSV (Raw Stochastic Value)
    df['highest_high'] = df['high'].rolling(period).max()
    df['lowest_low'] = df['low'].rolling(period).min()
    
    # Calcul RSV avec gestion division par zéro
    df['rsv'] = np.where(
        df['highest_high'] != df['lowest_low'],
        100 * (df['close'] - df['lowest_low']) / (df['highest_high'] - df['lowest_low']),
        50
    )
    df['rsv'] = df['rsv'].fillna(50)
    
    # Initialisation K et D
    k_values = [50.0]
    d_values = [50.0]
    
    for i in range(1, len(df)):
        # K = (2 * K[prev] + RSV) / 3
        k = (2 * k_values[-1] + df['rsv'].iloc[i]) / 3
        k_values.append(k)
        
        # D = (2 * D[prev] + K) / 3
        d = (2 * d_values[-1] + k) / 3
        d_values.append(d)
    
    df['k'] = k_values
    df['d'] = d_values
    
    # J = 3*K - 2*D
    df['j'] = 3 * df['k'] - 2 * df['d']
    
    return df

# Exécuter le calcul
with st.spinner("🔄 Calcul du KDJ..."):
    df = calculate_kdj(df, period)

# ==========================================
# 4. MÉTRIQUES
# ==========================================
col1, col2, col3, col4 = st.columns(4)

last_k = df['k'].iloc[-1]
last_d = df['d'].iloc[-1]
last_j = df['j'].iloc[-1]

with col1:
    st.metric("K (Fast)", f"{last_k:.2f}")

with col2:
    st.metric("D (Slow)", f"{last_d:.2f}")

with col3:
    st.metric("J (Divergence)", f"{last_j:.2f}")

with col4:
    if last_j > 80:
        st.metric("Signal", "🔴 OVERBOUGHT", delta="Surachat")
    elif last_j < 20:
        st.metric("Signal", "🟢 OVERSOLD", delta="Survente")
    else:
        st.metric("Signal", "⚪ NEUTRAL", delta="Neutre")

# ==========================================
# 5. AFFICHAGE PLOTLY
# ==========================================

# Créer la figure avec prix + KDJ
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=[0.5, 0.5],
    subplot_titles=("Prix BTCUSDT", "KDJ Oscillator")
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

# 2. KDJ Oscillator (Subplot 2)

# K/D Cloud - Créer des zones séparées pour bull et bear
# Identifier les zones où K > D (bull) et K < D (bear)
df_display = df.copy()
df_display['k_above_d'] = df_display['k'] > df_display['d']

# Créer des segments pour les fills
# Pour chaque changement de direction, on crée un nouveau segment
segments = []
current_segment = {'bull': df_display['k_above_d'].iloc[0], 'start': 0}

for i in range(1, len(df_display)):
    if df_display['k_above_d'].iloc[i] != current_segment['bull']:
        # Fin du segment précédent
        segments.append({
            'bull': current_segment['bull'],
            'start': current_segment['start'],
            'end': i
        })
        current_segment = {'bull': df_display['k_above_d'].iloc[i], 'start': i}

# Ajouter le dernier segment
segments.append({
    'bull': current_segment['bull'],
    'start': current_segment['start'],
    'end': len(df_display)
})

# Tracer les fills pour chaque segment
for seg in segments:
    start_idx = seg['start']
    end_idx = seg['end']
    segment_df = df_display.iloc[start_idx:end_idx]
    
    if len(segment_df) > 0:
        fill_color = color_kd_bull if seg['bull'] else color_kd_bear
        # Convertir hex en rgba avec opacité
        if fill_color.startswith('#'):
            r = int(fill_color[1:3], 16)
            g = int(fill_color[3:5], 16)
            b = int(fill_color[5:7], 16)
            fill_color_rgba = f'rgba({r},{g},{b},0.4)'
        else:
            fill_color_rgba = fill_color
        
        # Trace pour K
        fig.add_trace(go.Scatter(
            x=segment_df.index,
            y=segment_df['k'],
            showlegend=False,
            line=dict(width=0),
            hoverinfo='skip',
            mode='lines'
        ), row=2, col=1)
        
        # Trace pour D avec fill
        fig.add_trace(go.Scatter(
            x=segment_df.index,
            y=segment_df['d'],
            fill='tonexty',
            fillcolor=fill_color_rgba,
            showlegend=False,
            line=dict(width=0),
            hoverinfo='skip',
            mode='lines'
        ), row=2, col=1)

# Maintenant tracer K et D visibles par-dessus
fig.add_trace(go.Scatter(
    x=df.index,
    y=df['k'],
    name='K Line',
    line=dict(color=color_kd_bull, width=1.5),
    showlegend=True
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=df.index,
    y=df['d'],
    name='D Line',
    line=dict(color=color_kd_bear, width=1.5),
    showlegend=True
), row=2, col=1)

# J Line avec gradient de couleur
# Créer une couleur dynamique pour chaque point
j_colors = []
for j_val in df['j']:
    if j_val > 80:
        # Gradient vers overbought
        intensity = min((j_val - 80) / 33, 1.0)  # Normaliser entre 80 et 113
        # Interpolation simple entre neutral et ob
        j_colors.append(color_j_ob)
    elif j_val < 20:
        # Gradient vers oversold
        intensity = min((20 - j_val) / 33, 1.0)  # Normaliser entre -13 et 20
        j_colors.append(color_j_os)
    else:
        j_colors.append(color_j_neutral)

fig.add_trace(go.Scatter(
    x=df.index,
    y=df['j'],
    name='J Line',
    line=dict(color=color_j_neutral, width=2),
    marker=dict(
        size=0,
        color=j_colors,
        colorscale=[[0, color_j_os], [0.5, color_j_neutral], [1, color_j_ob]]
    ),
    showlegend=True
), row=2, col=1)

# Niveaux horizontaux sur KDJ
fig.add_hline(y=100, line_width=1, line_color='rgba(128,128,128,0.2)', line_dash='dot', row=2, col=1)
fig.add_hline(y=0, line_width=1, line_color='rgba(128,128,128,0.2)', line_dash='dot', row=2, col=1)
fig.add_hline(y=80, line_width=1, line_color='rgba(128,128,128,0.3)', line_dash='dash', row=2, col=1, annotation_text="Overbought", annotation_position="right")
fig.add_hline(y=20, line_width=1, line_color='rgba(128,128,128,0.3)', line_dash='dash', row=2, col=1, annotation_text="Oversold", annotation_position="right")

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
    )
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
    title='KDJ',
    range=[-20, 120],  # Plage pour voir les extrêmes de J
    row=2, col=1
)

st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 6. INTERPRÉTATION
# ==========================================
st.subheader("💡 Interprétation KDJ")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**📊 Signaux de Trading**")
    
    # Crossover K/D
    if len(df) > 1:
        k_cross_d_up = df['k'].iloc[-2] < df['d'].iloc[-2] and df['k'].iloc[-1] > df['d'].iloc[-1]
        k_cross_d_down = df['k'].iloc[-2] > df['d'].iloc[-2] and df['k'].iloc[-1] < df['d'].iloc[-1]
        
        if k_cross_d_up and last_j < 20:
            st.success("🟢 **SIGNAL ACHAT** - K croise D à la hausse en zone de survente")
        elif k_cross_d_down and last_j > 80:
            st.error("🔴 **SIGNAL VENTE** - K croise D à la baisse en zone de surachat")
        elif k_cross_d_up:
            st.info("🔵 Signal haussier - K croise D à la hausse")
        elif k_cross_d_down:
            st.warning("🟠 Signal baissier - K croise D à la baisse")
        else:
            st.info("⚪ Pas de signal de croisement récent")

with col2:
    st.markdown("**📈 État du Marché**")
    
    # Divergence J
    j_extreme = abs(last_j - 50)
    
    if last_j > 100:
        st.error("⚠️ **Surachat Extrême** - J > 100, attention au retournement")
    elif last_j < 0:
        st.success("⚠️ **Survente Extrême** - J < 0, opportunité d'achat potentielle")
    elif last_j > 80:
        st.warning("📈 Zone de surachat - Prudence pour les achats")
    elif last_j < 20:
        st.success("📉 Zone de survente - Opportunité d'accumulation")
    else:
        st.info("⚖️ Zone neutre - Marché équilibré")

# Explication
st.markdown("---")
st.subheader("📚 Comprendre le KDJ")

st.markdown(f"""
**KDJ** est une version modifiée du Stochastic qui mesure le momentum du prix :

**K (Fast)** : Ligne rapide = {last_k:.1f}  
**D (Slow)** : Ligne lente (moyenne de K) = {last_d:.1f}  
**J (Divergence)** : J = 3K - 2D = {last_j:.1f}

**Zones clés:**
- **J > 80** : Surachat - Les acheteurs sont surpuissants
- **J < 20** : Survente - Les vendeurs sont surpuissants  
- **0 < J < 100** : Zone normale
- **J > 100 ou J < 0** : Extrême, retournement probable

**Signaux:**
- ✅ **Achat** : K croise D à la hausse + J < 20
- ❌ **Vente** : K croise D à la baisse + J > 80
- 🔄 **Divergence** : Si J s'éloigne fortement de K/D, le momentum change
""")

# Footer
st.markdown("---")
st.caption(f"🔄 Timeframe: {st.session_state.current_timeframe} | 📊 Bougies: {len(df)} | 🔴 Données temps réel via Bitget WebSocket")
st.caption(f"⚙️ Paramètres: Période={period}")

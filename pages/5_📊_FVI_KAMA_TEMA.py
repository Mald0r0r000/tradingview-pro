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

st.set_page_config(layout="wide", page_title="FVI KAMA + TEMA")

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
st.title("📊 FVI KAMA + TEMA avec Bandes Dynamiques")
st.caption("Oscillateur de volume avec moyennes mobiles adaptatives et bandes de volatilité")

# ==========================================
# 1. PARAMÈTRES (SIDEBAR)
# ==========================================
with st.sidebar:
    # Sélecteur de timeframe
    current_tf = timeframe_selector("fvi_kama_tema")
    
    st.markdown("---")
    st.header("📊 Paramètres FVI")
    
    period_kama = st.number_input("Période FVI KAMA", value=1, min_value=1, max_value=50)
    period_tema = st.number_input("Période FVI TEMA", value=3, min_value=1, max_value=50)
    volume_scale = st.number_input("Facteur Volume", value=9.0, min_value=0.1, max_value=50.0, step=0.1)
    
    st.markdown("---")
    st.header("⚙️ KAMA")
    fast_kama = st.number_input("Fast KAMA", value=2, min_value=1, max_value=20)
    slow_kama = st.number_input("Slow KAMA", value=6, min_value=1, max_value=50)
    long_mult_kama = st.number_input("Multiplicateur MA Longue KAMA", value=9, min_value=1, max_value=20)
    
    st.markdown("---")
    st.header("⚙️ TEMA")
    fast_tema = st.number_input("Fast TEMA", value=9, min_value=1, max_value=50)
    slow_tema = st.number_input("Slow TEMA", value=60, min_value=1, max_value=200)
    long_mult_tema = st.number_input("Multiplicateur MA Longue TEMA", value=12, min_value=1, max_value=50)
    
    st.markdown("---")
    st.header("📏 Bandes")
    atr_len = st.number_input("ATR Longueur", value=90, min_value=10, max_value=200)
    atr_mult_ext = st.number_input("Multiplicateur ATR EXT", value=4.4, min_value=1.0, max_value=10.0, step=0.1)
    atr_mult_int = st.number_input("Multiplicateur ATR INT", value=2.7, min_value=1.0, max_value=10.0, step=0.1)
    
    st.markdown("---")
    st.header("🎨 Couleurs")
    col1, col2 = st.columns(2)
    with col1:
        color_fvi = st.color_picker("FVI", "#FA9D1B")
        color_kama_fast = st.color_picker("KAMA Fast", "#7EE9C0")
        color_kama_long = st.color_picker("KAMA Long", "#9D5EC8")
    with col2:
        color_tema_fast = st.color_picker("TEMA Fast", "#4CAF50")
        color_tema_long = st.color_picker("TEMA Long", "#FF9800")
        color_band = st.color_picker("Bandes", "#888888")

# ==========================================
# 2. RÉCUPÉRATION DES DONNÉES
# ==========================================
df = st.session_state.data_manager.get_dataframe(st.session_state.current_timeframe)

min_required = max(period_kama * long_mult_kama, slow_tema * long_mult_tema, atr_len) + 50

if df.empty or len(df) < min_required:
    st.warning("⏳ Pas assez de données disponibles. Attendez que plus de bougies arrivent...")
    st.info(f"📊 Données actuelles: {len(df)} bougies | Minimum requis: ~{min_required}")
    st.stop()

# ==========================================
# 3. CALCULS FVI KAMA + TEMA
# ==========================================

def calculate_kama(src, length, fast_period, slow_period):
    """Kaufman Adaptive Moving Average"""
    change = np.abs(src - src.shift(length))
    volatility = src.diff().abs().rolling(length).sum()
    
    er = np.where(volatility != 0, change / volatility, 0.0)
    
    fast_sc = 2.0 / (fast_period + 1)
    slow_sc = 2.0 / (slow_period + 1)
    sc = np.power(er * (fast_sc - slow_sc) + slow_sc, 2)
    
    kama = pd.Series(index=src.index, dtype=float)
    kama.iloc[0] = src.iloc[0]
    
    for i in range(1, len(src)):
        if pd.isna(kama.iloc[i-1]):
            kama.iloc[i] = src.iloc[i]
        else:
            kama.iloc[i] = kama.iloc[i-1] + sc.iloc[i] * (src.iloc[i] - kama.iloc[i-1])
    
    return kama

def calculate_tema(src, length):
    """Triple Exponential Moving Average"""
    ema1 = src.ewm(span=length, adjust=False).mean()
    ema2 = ema1.ewm(span=length, adjust=False).mean()
    ema3 = ema2.ewm(span=length, adjust=False).mean()
    return 3 * ema1 - 3 * ema2 + ema3

# Calcul du FVI (custom OBV)
df['normalized_vol'] = df['volume'] / df['volume'].shift(1).fillna(df['volume'])
df['price_change'] = df['close'] - df['close'].shift(1)
df['direction'] = np.where(df['price_change'] > 0, 1.0, 
                           np.where(df['price_change'] < 0, -1.0, 0.0))

custom_obv = [0.0]
for i in range(1, len(df)):
    obv_val = custom_obv[-1] + volume_scale * df['normalized_vol'].iloc[i] * df['direction'].iloc[i]
    custom_obv.append(obv_val)

df['custom_obv'] = custom_obv

# KAMA Fast & Long
with st.spinner("🔄 Calcul KAMA..."):
    df['kama_fast'] = calculate_kama(df['custom_obv'], period_kama, fast_kama, slow_kama)
    df['kama_long'] = calculate_kama(df['custom_obv'], period_kama * long_mult_kama, fast_kama, slow_kama)

# TEMA Fast & Long
with st.spinner("🔄 Calcul TEMA..."):
    df['tema_fast'] = calculate_tema(df['custom_obv'], fast_tema)
    df['tema_long'] = calculate_tema(df['custom_obv'], slow_tema * long_mult_tema)

# Bandes dynamiques (ATR-like)
df['diff_kama'] = np.abs(df['kama_fast'] - df['kama_long'])
df['atr_like'] = df['diff_kama'].ewm(span=atr_len, adjust=False).mean()

df['upper_band_ext'] = df['kama_long'] + atr_mult_ext * df['atr_like']
df['lower_band_ext'] = df['kama_long'] - atr_mult_ext * df['atr_like']
df['upper_band_int'] = df['kama_long'] + atr_mult_int * df['atr_like']
df['lower_band_int'] = df['kama_long'] - atr_mult_int * df['atr_like']

# Signaux
df['long_signal_kama'] = False
df['short_signal_kama'] = False
df['long_signal_tema'] = False
df['short_signal_tema'] = False

# KAMA Crossovers avec filtre bandes
kama_cross_up = (df['kama_fast'].shift(1) < df['kama_long'].shift(1)) & (df['kama_fast'] > df['kama_long'])
kama_cross_down = (df['kama_fast'].shift(1) > df['kama_long'].shift(1)) & (df['kama_fast'] < df['kama_long'])

df.loc[kama_cross_up & (df['kama_fast'] > df['upper_band_ext']), 'long_signal_kama'] = True
df.loc[kama_cross_down & (df['kama_fast'] < df['lower_band_ext']), 'short_signal_kama'] = True

# TEMA Crossovers
tema_cross_up = (df['tema_fast'].shift(1) < df['tema_long'].shift(1)) & (df['tema_fast'] > df['tema_long'])
tema_cross_down = (df['tema_fast'].shift(1) > df['tema_long'].shift(1)) & (df['tema_fast'] < df['tema_long'])

df.loc[tema_cross_up, 'long_signal_tema'] = True
df.loc[tema_cross_down, 'short_signal_tema'] = True

# ==========================================
# 4. MÉTRIQUES
# ==========================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("FVI OBV", f"{df['custom_obv'].iloc[-1]:,.0f}")

with col2:
    st.metric("KAMA Fast", f"{df['kama_fast'].iloc[-1]:,.2f}")

with col3:
    st.metric("TEMA Fast", f"{df['tema_fast'].iloc[-1]:,.2f}")

with col4:
    total_signals_kama = df['long_signal_kama'].sum() + df['short_signal_kama'].sum()
    st.metric("Signaux KAMA", total_signals_kama)

# ==========================================
# 5. AFFICHAGE PLOTLY
# ==========================================

fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=[0.5, 0.5],
    subplot_titles=("Prix BTCUSDT", "FVI KAMA + TEMA Oscillator")
)

# 1. Candlestick
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

# 2. FVI Oscillator
fig.add_trace(go.Scatter(
    x=df.index,
    y=df['custom_obv'],
    name='FVI',
    line=dict(color=color_fvi, width=2)
), row=2, col=1)

# KAMA
fig.add_trace(go.Scatter(
    x=df.index,
    y=df['kama_fast'],
    name='KAMA Fast',
    line=dict(color=color_kama_fast, width=2)
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=df.index,
    y=df['kama_long'],
    name='KAMA Long',
    line=dict(color=color_kama_long, width=2)
), row=2, col=1)

# TEMA
fig.add_trace(go.Scatter(
    x=df.index,
    y=df['tema_fast'],
    name='TEMA Fast',
    line=dict(color=color_tema_fast, width=2)
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=df.index,
    y=df['tema_long'],
    name='TEMA Long',
    line=dict(color=color_tema_long, width=2)
), row=2, col=1)

# Bandes
fig.add_trace(go.Scatter(
    x=df.index,
    y=df['upper_band_ext'],
    name='Upper Band EXT',
    line=dict(color=color_band, width=1, dash='solid'),
    opacity=0.3
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=df.index,
    y=df['lower_band_ext'],
    name='Lower Band EXT',
    line=dict(color=color_band, width=1, dash='solid'),
    opacity=0.3
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=df.index,
    y=df['upper_band_int'],
    name='Upper Band INT',
    line=dict(color=color_band, width=1, dash='dash'),
    opacity=0.5
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=df.index,
    y=df['lower_band_int'],
    name='Lower Band INT',
    line=dict(color=color_band, width=1, dash='dash'),
    opacity=0.5
), row=2, col=1)

# Signaux KAMA
long_kama_df = df[df['long_signal_kama']]
short_kama_df = df[df['short_signal_kama']]

if not long_kama_df.empty:
    fig.add_trace(go.Scatter(
        x=long_kama_df.index,
        y=long_kama_df['kama_fast'],
        mode='markers+text',
        marker=dict(size=12, color='#57BAA7', symbol='triangle-up'),
        text='LONG',
        textposition='bottom center',
        name='Long KAMA',
        showlegend=True
    ), row=2, col=1)

if not short_kama_df.empty:
    fig.add_trace(go.Scatter(
        x=short_kama_df.index,
        y=short_kama_df['kama_fast'],
        mode='markers+text',
        marker=dict(size=12, color='#8F58C9', symbol='triangle-down'),
        text='SHORT',
        textposition='top center',
        name='Short KAMA',
        showlegend=True
    ), row=2, col=1)

# Configuration
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

fig.update_xaxes(showgrid=True, gridcolor='rgba(128,128,128,0.1)', color='white')
fig.update_yaxes(showgrid=True, gridcolor='rgba(128,128,128,0.1)', color='white', side='right', tickformat=',.2f', tickprefix='$', row=1, col=1)
fig.update_yaxes(showgrid=True, gridcolor='rgba(128,128,128,0.1)', color='white', side='right', title='FVI', row=2, col=1)

st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 6. TABLE D'INFORMATIONS
# ==========================================
st.subheader("📋 Valeurs des Bandes")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Bandes Internes (INT)**")
    st.write(f"Upper: {df['upper_band_int'].iloc[-1]:,.2f}")
    st.write(f"Lower: {df['lower_band_int'].iloc[-1]:,.2f}")

with col2:
    st.markdown("**Bandes Externes (EXT)**")
    st.write(f"Upper: {df['upper_band_ext'].iloc[-1]:,.2f}")
    st.write(f"Lower: {df['lower_band_ext'].iloc[-1]:,.2f}")

# Signaux récents
st.markdown("---")
st.subheader("🎯 Signaux Récents")

recent_signals = df[df['long_signal_kama'] | df['short_signal_kama'] | df['long_signal_tema'] | df['short_signal_tema']].tail(5)

if not recent_signals.empty:
    signals_display = pd.DataFrame({
        'Type': recent_signals.apply(lambda x: '🟢 LONG KAMA' if x['long_signal_kama'] else 
                                               '🔴 SHORT KAMA' if x['short_signal_kama'] else
                                               '🔺 LONG TEMA' if x['long_signal_tema'] else '🔻 SHORT TEMA', axis=1),
        'FVI': recent_signals['custom_obv'].apply(lambda x: f"{x:,.0f}"),
        'KAMA Fast': recent_signals['kama_fast'].apply(lambda x: f"{x:,.2f}"),
        'Prix': recent_signals['close'].apply(lambda x: f"${x:,.2f}")
    })
    st.dataframe(signals_display, use_container_width=True)
else:
    st.info("Aucun signal récent")

# Explication
st.markdown("---")
st.subheader("💡 Comprendre FVI KAMA + TEMA")

st.markdown("""
**FVI (Force Volume Index)** : OBV personnalisé qui pondère le volume par sa magnitude.

**KAMA (Kaufman Adaptive MA)** : Moyenne mobile qui s'adapte à la volatilité.
- Fast KAMA = Réactif aux changements
- Long KAMA = Tendance générale

**TEMA (Triple EMA)** : Moyenne ultra-réactive, moins de lag que EMA simple.

**Bandes Dynamiques** : Mesure de la volatilité basée sur l'écart KAMA fast/long.
- **INT (Internal)** : Zone normale
- **EXT (External)** : Zone extrême

**Signaux:**
- ✅ **LONG KAMA** : Fast croise Long UP + au-dessus de bande EXT = Force acheteuse
- ❌ **SHORT KAMA** : Fast croise Long DOWN + en-dessous de bande EXT = Force vendeuse
- 🔺 **TEMA** : Confirmation secondaire des croisements
""")

# Footer
st.markdown("---")
st.caption(f"🔄 Timeframe: {st.session_state.current_timeframe} | 📊 Bougies: {len(df)} | 🔴 Données temps réel via Bitget WebSocket")

import streamlit as st
import pandas as pd
import numpy as np
import asyncio
import threading
import queue
import time
from streamlit_lightweight_charts import renderLightweightCharts

from bitget_ws_client import BitgetWebSocketClient
from data_manager import DataManager
from pine_converter import PineScriptConverter
from indicator_executor import IndicatorExecutor

st.set_page_config(layout="wide", page_title="TradingView Pro")

# --- Configuration ---
SYMBOL = "BTCUSDT"
AVAILABLE_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1H", "4H", "1D", "1W", "1M"]

# --- Session State Initialization ---
if "data_manager" not in st.session_state:
    st.session_state.data_manager = DataManager(max_candles=500)

if "ws_client" not in st.session_state:
    st.session_state.ws_client = None

if "ws_thread" not in st.session_state:
    st.session_state.ws_thread = None

if "message_queue" not in st.session_state:
    st.session_state.message_queue = queue.Queue()

if "current_timeframe" not in st.session_state:
    st.session_state.current_timeframe = "1m"

if "indicators" not in st.session_state:
    # Format: {name: {'pine_code': str, 'python_code': str, 'enabled': bool}}
    st.session_state.indicators = {}

if "show_indicator_editor" not in st.session_state:
    st.session_state.show_indicator_editor = False

if "temp_pine_code" not in st.session_state:
    st.session_state.temp_pine_code = ""

if "temp_python_code" not in st.session_state:
    st.session_state.temp_python_code = ""

if "temp_indicator_name" not in st.session_state:
    st.session_state.temp_indicator_name = ""

if "ws_running" not in st.session_state:
    st.session_state.ws_running = False


# --- WebSocket Background Thread ---
def websocket_thread(timeframe: str, message_queue: queue.Queue):
    """Thread pour exécuter le WebSocket en arrière-plan"""
    def on_candle(candle):
        # Envoyer la bougie à la queue
        message_queue.put({"type": "candle", "data": candle, "timeframe": timeframe})
    
    # Créer le client
    client = BitgetWebSocketClient(
        symbol=SYMBOL,
        timeframe=timeframe,
        on_message=on_candle
    )
    
    # Exécuter la boucle asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(client.run())
    except Exception as e:
        st.error(f"WebSocket error: {e}")
    finally:
        loop.close()


def start_websocket(timeframe: str):
    """Démarre le WebSocket dans un thread séparé"""
    if st.session_state.ws_thread and st.session_state.ws_thread.is_alive():
        # Arrêter l'ancien thread (simplification, en production utiliser un système plus propre)
        st.session_state.ws_running = False
        time.sleep(1)
    
    st.session_state.ws_running = True
    st.session_state.ws_thread = threading.Thread(
        target=websocket_thread,
        args=(timeframe, st.session_state.message_queue),
        daemon=True
    )
    st.session_state.ws_thread.start()


# --- UI ---
st.title("🕯️ TradingView Pro - Bitget Live")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Sélection du timeframe
    selected_timeframe = st.selectbox(
        "Timeframe",
        AVAILABLE_TIMEFRAMES,
        index=AVAILABLE_TIMEFRAMES.index(st.session_state.current_timeframe)
    )
    
    # Si le timeframe a changé
    if selected_timeframe != st.session_state.current_timeframe:
        st.session_state.current_timeframe = selected_timeframe
        # Redémarrer le WebSocket
        start_websocket(selected_timeframe)
        st.rerun()
    
    st.markdown("---")
    
    # Indicateurs personnalisés
    st.header("📊 Indicateurs")
    
    # Liste des indicateurs
    if st.session_state.indicators:
        for ind_name, ind_data in st.session_state.indicators.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                enabled = st.checkbox(
                    ind_name,
                    value=ind_data.get('enabled', True),
                    key=f"ind_{ind_name}"
                )
                st.session_state.indicators[ind_name]['enabled'] = enabled
            with col2:
                if st.button("🗑️", key=f"del_{ind_name}"):
                    del st.session_state.indicators[ind_name]
                    st.rerun()
    else:
        st.info("Aucun indicateur ajouté")
    
    # Bouton pour ajouter un indicateur
    if st.button("➕ Nouvel Indicateur"):
        st.session_state.show_indicator_editor = True
        st.session_state.temp_pine_code = ""
        st.session_state.temp_python_code = ""
        st.session_state.temp_indicator_name = ""
        st.rerun()


# --- Main Area ---
# Démarrer le WebSocket si pas déjà démarré
if not st.session_state.ws_running:
    start_websocket(st.session_state.current_timeframe)

# --- Éditeur d'Indicateur (Modal) ---
if st.session_state.show_indicator_editor:
    st.markdown("---")
    st.subheader("✏️ Éditeur PineScript")
    
    # Nom de l'indicateur en haut
    indicator_name = st.text_input(
        "📝 Nom de l'indicateur *",
        value=st.session_state.temp_indicator_name,
        placeholder="Ex: Mon Indicateur Custom",
        help="Donnez un nom unique à votre indicateur"
    )
    st.session_state.temp_indicator_name = indicator_name
    
    col_edit1, col_edit2 = st.columns(2)
    
    with col_edit1:
        st.markdown("**📋 Code PineScript**")
        st.caption("Collez votre code PineScript ci-dessous")
        pine_code = st.text_area(
            "Code PineScript",
            value=st.session_state.temp_pine_code,
            height=350,
            key="pine_editor",
            label_visibility="collapsed"
        )
        st.session_state.temp_pine_code = pine_code
    
    with col_edit2:
        st.markdown("**🐍 Code Python Généré** (éditable)")
        st.caption("Modifiable pour ajustements manuels")
        if st.session_state.temp_python_code:
            python_code_edited = st.text_area(
                "Code Python",
                value=st.session_state.temp_python_code,
                height=350,
                key="python_editor",
                label_visibility="collapsed"
            )
            # Mettre à jour si modifié
            st.session_state.temp_python_code = python_code_edited
        else:
            st.info("👈 Collez votre code PineScript et cliquez sur 'Convertir'")
    
    # Boutons d'action
    st.markdown("")
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns([2, 2, 2, 1])
    
    with col_btn1:
        convert_disabled = not pine_code
        if st.button("🔄 Convertir", use_container_width=True, disabled=convert_disabled, type="primary"):
            converter = PineScriptConverter()
            python_code = converter.convert(pine_code)
            st.session_state.temp_python_code = python_code
            
            warnings = converter.get_warnings()
            errors = converter.get_errors()
            
            if errors:
                st.error("❌ Erreurs de conversion")
                for err in errors[:3]:  # Limiter à 3 erreurs
                    st.write(f"- {err}")
            
            if warnings:
                st.warning("⚠️ Conversion partielle")
                for warn in warnings[:3]:  # Limiter à 3 warnings
                    st.write(f"- {warn}")
                st.info("💡 Vérifiez les commentaires TODO dans le code généré")
            
            if not errors:
                st.success("✅ Conversion terminée!")
            
            st.rerun()
    
    with col_btn2:
        save_disabled = not st.session_state.temp_python_code or not indicator_name
        if st.button("💾 Sauvegarder", use_container_width=True, disabled=save_disabled, type="secondary"):
            st.session_state.indicators[indicator_name] = {
                'pine_code': st.session_state.temp_pine_code,
                'python_code': st.session_state.temp_python_code,
                'enabled': True
            }
            st.session_state.show_indicator_editor = False
            st.success(f"✅ '{indicator_name}' sauvegardé!")
            time.sleep(0.5)
            st.rerun()
    
    with col_btn3:
        if st.button("🧪 Tester", use_container_width=True, disabled=save_disabled):
            # Tester l'indicateur sans sauvegarder
            try:
                df = st.session_state.data_manager.get_dataframe(st.session_state.current_timeframe)
                if len(df) > 0:
                    executor = IndicatorExecutor()
                    results = executor.execute(st.session_state.temp_python_code, df)
                    st.success(f"✅ Test réussi! {len(results)} série(s) détectée(s)")
                else:
                    st.warning("⚠️ Pas assez de données pour tester")
            except Exception as e:
                st.error(f"❌ Erreur: {str(e)[:100]}")
    
    with col_btn4:
        if st.button("❌", use_container_width=True, help="Fermer l'éditeur"):
            st.session_state.show_indicator_editor = False
            st.rerun()

    st.markdown("---")


# --- Graphique Principal ---
@st.fragment(run_every=1)
def render_chart():
    """Rendu du graphique avec mise à jour temps réel"""
    
    # Lire les messages de la queue
    try:
        while not st.session_state.message_queue.empty():
            msg = st.session_state.message_queue.get_nowait()
            if msg["type"] == "candle":
                st.session_state.data_manager.add_candle(
                    msg["timeframe"],
                    msg["data"]
                )
    except queue.Empty:
        pass
    
    # Récupérer les données du timeframe actuel
    candles = st.session_state.data_manager.get_candles(st.session_state.current_timeframe)
    
    if not candles:
        st.info("📡 Connexion au WebSocket... En attente de données...")
        return
    
    # Afficher les métriques
    last_candle = candles[-1]
    col_m1, col_m2, col_m3 = st.columns(3)
    
    with col_m1:
        st.metric(
            "Prix Live",
            f"${last_candle['close']:.2f}",
            f"{last_candle['close'] - last_candle['open']:.2f}"
        )
    
    with col_m2:
        # Calculer variation 24h (approximation)
        if len(candles) > 1:
            first_close = candles[0]['close']
            variation = ((last_candle['close'] - first_close) / first_close) * 100
            st.metric("Variation", f"{variation:.2f}%")
    
    with col_m3:
        st.metric("Bougies", len(candles))
    
    # Préparer les séries pour le graphique
    series = [
        {
            "type": 'Candlestick',
            "data": candles,
            "options": {
                "upColor": '#26a69a',
                "downColor": '#ef5350',
                "borderVisible": False,
                "wickUpColor": '#26a69a',
                "wickDownColor": '#ef5350'
            }
        }
    ]
    
    # Ajouter les indicateurs activés
    if st.session_state.indicators:
        df = st.session_state.data_manager.get_dataframe(st.session_state.current_timeframe)
        executor = IndicatorExecutor()
        
        for ind_name, ind_data in st.session_state.indicators.items():
            if not ind_data.get('enabled', False):
                continue
            
            try:
                # Exécuter l'indicateur
                results = executor.execute(ind_data['python_code'], df)
                
                # Ajouter chaque série au graphique
                for series_name, series_data in results.items():
                    series.append(series_data)
            
            except Exception as e:
                st.error(f"Erreur dans l'indicateur '{ind_name}': {e}")
    
    # Configuration du graphique
    chart_options = {
        "layout": {
            "textColor": 'white',
            "background": {
                "type": 'solid',
                "color": '#1e222d'
            }
        },
        "grid": {
            "vertLines": {"color": "rgba(42, 46, 57, 0.6)"},
            "horzLines": {"color": "rgba(42, 46, 57, 0.6)"}
        },
        "timeScale": {
            "timeVisible": True,
            "secondsVisible": False
        },
        "crosshair": {
            "mode": 0
        }
    }
    
    charts = [
        {
            "chart": chart_options,
            "series": series
        }
    ]
    
    # Rendu
    renderLightweightCharts(
        charts=charts,
        key="live_chart"
    )


# Afficher le graphique
render_chart()

# Footer
st.markdown("---")
st.caption(f"🔌 Connecté à Bitget WebSocket | Symbol: {SYMBOL} | Timeframe: {st.session_state.current_timeframe}")

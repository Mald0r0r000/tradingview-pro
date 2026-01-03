"""
Composant réutilisable pour le sélecteur de timeframe
À importer dans toutes les pages
"""
import streamlit as st
import time
import threading
import asyncio
import queue

AVAILABLE_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1H", "4H", "1D", "1W", "1M"]

def websocket_thread(timeframe: str, message_queue: queue.Queue):
    """Thread pour exécuter le WebSocket en arrière-plan"""
    from bitget_ws_client import BitgetWebSocketClient
    
    def on_candle(candle):
        message_queue.put({"type": "candle", "data": candle, "timeframe": timeframe})
    
    client = BitgetWebSocketClient(
        symbol="BTCUSDT",
        timeframe=timeframe,
        on_message=on_candle
    )
    
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
    if "ws_thread" not in st.session_state:
        st.session_state.ws_thread = None
    
    if "message_queue" not in st.session_state:
        st.session_state.message_queue = queue.Queue()
    
    if "ws_running" not in st.session_state:
        st.session_state.ws_running = False
    
    if st.session_state.ws_thread and st.session_state.ws_thread.is_alive():
        st.session_state.ws_running = False
        time.sleep(1)
    
    st.session_state.ws_running = True
    st.session_state.ws_thread = threading.Thread(
        target=websocket_thread,
        args=(timeframe, st.session_state.message_queue),
        daemon=True
    )
    st.session_state.ws_thread.start()


def timeframe_selector(key_suffix=""):
    """
    Affiche un sélecteur de timeframe et gère le changement automatique
    
    Args:
        key_suffix: Suffixe pour rendre la clé unique entre les pages
    
    Returns:
        Le timeframe sélectionné
    """
    if "current_timeframe" not in st.session_state:
        st.session_state.current_timeframe = "1m"
    
    selected_tf = st.selectbox(
        "📊 Timeframe",
        AVAILABLE_TIMEFRAMES,
        index=AVAILABLE_TIMEFRAMES.index(st.session_state.current_timeframe),
        key=f"tf_selector_{key_suffix}",
        help="Changer le timeframe recharge l'historique et redémarre le WebSocket"
    )
    
    # Si le timeframe a changé, recharger l'historique et redémarrer le WebSocket
    if selected_tf != st.session_state.current_timeframe:
        st.session_state.current_timeframe = selected_tf
        
        # 1. Clear les anciennes données de ce timeframe
        if "data_manager" in st.session_state:
            st.session_state.data_manager.clear(selected_tf)
        
        # 2. Redémarrer le WebSocket (qui va charger l'historique via REST)
        start_websocket(selected_tf)
        
        st.success(f"✅ Changement vers {selected_tf} - Chargement de l'historique...")
        time.sleep(0.5)  # Petit délai pour laisser le temps au WebSocket de se connecter
        st.rerun()
    
    return selected_tf

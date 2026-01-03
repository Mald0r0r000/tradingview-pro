import asyncio
import json
import logging
import time
from typing import Callable, Optional, Dict, List
import websockets
import aiohttp
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BitgetWebSocketClient:
    """
    Client WebSocket pour Bitget API v2 - Futures USDT
    Support multi-timeframe avec reconnexion automatique
    Charge l'historique via REST API puis écoute les updates temps réel
    """
    
    # Mapping des timeframes vers les channels Bitget
    TIMEFRAME_MAPPING = {
        "1m": "candle1m",
        "3m": "candle3m",
        "5m": "candle5m",
        "15m": "candle15m",
        "30m": "candle30m",
        "1H": "candle1H",
        "4H": "candle4H",
        "6H": "candle6H",
        "12H": "candle12H",
        "1D": "candle1Dutc",
        "1W": "candle1Wutc",
        "1M": "candle1Mutc",
    }
    
    WS_URL = "wss://ws.bitget.com/v2/ws/public"
    REST_URL = "https://api.bitget.com"
    
    def __init__(self, symbol: str = "BTCUSDT", timeframe: str = "1m", 
                 on_message: Optional[Callable] = None):
        """
        Args:
            symbol: Trading pair (default: BTCUSDT)
            timeframe: Timeframe (1m, 3m, 5m, etc.)
            on_message: Callback function when new candle data arrives
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.on_message = on_message
        self.ws = None
        self.running = False
        self.reconnect_delay = 5
        self.last_ping = time.time()
        self.ping_interval = 30  # Ping every 30 seconds
        
        # Buffer pour stocker les bougies
        self.candles_buffer = deque(maxlen=500)
        
    async def fetch_historical_candles(self):
        """Récupère l'historique des bougies via REST API - Fait 2 appels pour 1000 bougies"""
        try:
            url = f"{self.REST_URL}/api/v2/mix/market/candles"
            all_candles = []
            
            # Bitget limite à 500 max par appel, on fait 2 appels
            # 1er appel: 500 bougies les plus récentes
            params = {
                "symbol": f"{self.symbol}USDT_UMCBL",
                "productType": "USDT-FUTURES", 
                "granularity": self.timeframe,
                "limit": "500"
            }
            
            logger.info(f"Fetching {self.timeframe} historical data (call 1/2)...")
            
            async with aiohttp.ClientSession() as session:
                # Premier appel - 500 bougies récentes
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("code") == "00000" and data.get("data"):
                            candles_batch1 = data["data"]
                            all_candles.extend(candles_batch1)
                            logger.info(f"✅ Batch 1: {len(candles_batch1)} candles")
                            
                            # Deuxième appel - 500 bougies avant
                            if len(candles_batch1) > 0:
                                # Prendre le timestamp de la bougie la plus ancienne du 1er batch
                                oldest_time = int(candles_batch1[-1][0])  # Timestamp en ms
                                
                                params["endTime"] = str(oldest_time - 1)  # Avant le 1er batch
                                
                                logger.info(f"Fetching older data (call 2/2)...")
                                async with session.get(url, params=params) as response2:
                                    if response2.status == 200:
                                        data2 = await response2.json()
                                        if data2.get("code") == "00000" and data2.get("data"):
                                            candles_batch2 = data2["data"]
                                            all_candles.extend(candles_batch2)
                                            logger.info(f"✅ Batch 2: {len(candles_batch2)} candles")
                        
                        # Traiter toutes les bougies (du plus ancien au plus récent)
                        logger.info(f"✅ Total loaded: {len(all_candles)} candles")
                        
                        # Les données sont du plus récent au plus ancien, on reverse
                        for candle_data in reversed(all_candles):
                            try:
                                candle = {
                                    "time": int(candle_data[0]) // 1000,  # ms → secondes
                                    "open": float(candle_data[1]),
                                    "high": float(candle_data[2]),
                                    "low": float(candle_data[3]),
                                    "close": float(candle_data[4]),
                                    "volume": float(candle_data[5]) if len(candle_data) > 5 else 0
                                }
                                self.candles_buffer.append(candle) # Add to buffer
                                if self.on_message:
                                    self.on_message(candle)
                            except (IndexError, ValueError) as e:
                                logger.warning(f"Error parsing candle: {e}")
                                continue
                    else:
                        logger.error(f"HTTP {response.status} - Using limit=500 instead")
                        
        except Exception as e:
            logger.error(f"Error fetching historical candles: {e}")
    
    async def connect(self):
        """Établit la connexion WebSocket et subscribe au channel"""
        try:
            logger.info(f"Connecting to {self.WS_URL}...")
            self.ws = await websockets.connect(self.WS_URL)
            logger.info("WebSocket connected!")
            
            # Subscribe to candle channel
            await self.subscribe()
            
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    async def subscribe(self):
        """Subscribe au channel candlestick"""
        channel = self.TIMEFRAME_MAPPING.get(self.timeframe)
        if not channel:
            raise ValueError(f"Unsupported timeframe: {self.timeframe}")
        
        subscribe_msg = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "USDT-FUTURES",
                    "channel": channel,
                    "instId": self.symbol
                }
            ]
        }
        
        logger.info(f"Subscribing to {channel} for {self.symbol}")
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def handle_message(self, message: str):
        """Parse et traite les messages reçus"""
        try:
            data = json.loads(message)
            
            # Gestion des messages de type "pong"
            if data.get("event") == "pong":
                logger.debug("Received pong")
                return
            
            # Gestion de la confirmation de subscription
            if data.get("event") == "subscribe":
                logger.info(f"Successfully subscribed: {data}")
                return
            
            # Gestion des données de bougies
            if data.get("action") in ["snapshot", "update"]:
                arg = data.get("arg", {})
                candles_data = data.get("data", [])
                
                if not candles_data:
                    return
                
                # Bitget renvoie les données sous forme: [timestamp, open, high, low, close, volume, ...]
                for candle_raw in candles_data:
                    candle = self.parse_candle(candle_raw)
                    if candle:
                        # Ajouter au buffer
                        self.candles_buffer.append(candle)
                        
                        # Callback si défini
                        if self.on_message:
                            self.on_message(candle)
                        
                        logger.debug(f"New candle: {candle}")
        
        except json.JSONDecodeError:
            logger.error(f"Failed to parse message: {message}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def parse_candle(self, raw_data: List) -> Optional[Dict]:
        """
        Convertit les données brutes Bitget en format lightweight-charts
        Format Bitget: [timestamp, open, high, low, close, volume, ...]
        Format output: {time: int, open: float, high: float, low: float, close: float}
        """
        try:
            if len(raw_data) < 6:
                return None
            
            timestamp = int(raw_data[0]) // 1000  # Convertir ms en secondes
            
            candle = {
                "time": timestamp,
                "open": float(raw_data[1]),
                "high": float(raw_data[2]),
                "low": float(raw_data[3]),
                "close": float(raw_data[4]),
                "volume": float(raw_data[5])
            }
            
            return candle
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to parse candle data: {e}")
            return None
    
    async def send_ping(self):
        """Envoie un ping pour maintenir la connexion"""
        try:
            ping_msg = {"op": "ping"}
            await self.ws.send(json.dumps(ping_msg))
            self.last_ping = time.time()
            logger.debug("Sent ping")
        except Exception as e:
            logger.error(f"Failed to send ping: {e}")
    
    async def run(self):
        """Boucle principale du WebSocket avec reconnexion automatique"""
        self.running = True
        
        # ÉTAPE 1: Charger l'historique via REST API
        logger.info("🔄 Loading historical data...")
        await self.fetch_historical_candles()
        logger.info("✅ Historical data loaded, starting real-time updates...")
        
        # ÉTAPE 2: WebSocket pour les updates temps réel
        while self.running:
            try:
                # Connexion
                connected = await self.connect()
                if not connected:
                    logger.warning(f"Reconnecting in {self.reconnect_delay}s...")
                    await asyncio.sleep(self.reconnect_delay)
                    continue
                
                # Boucle de réception
                while self.running:
                    try:
                        # Vérifier si on doit envoyer un ping
                        if time.time() - self.last_ping > self.ping_interval:
                            await self.send_ping()
                        
                        # Recevoir des messages avec timeout
                        message = await asyncio.wait_for(
                            self.ws.recv(), 
                            timeout=self.ping_interval + 10
                        )
                        await self.handle_message(message)
                    
                    except asyncio.TimeoutError:
                        logger.warning("No message received, sending ping...")
                        await self.send_ping()
                    
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("Connection closed, reconnecting...")
                        break
            
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
            
            # Attendre avant de reconnecter
            if self.running:
                logger.info(f"Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
    
    def stop(self):
        """Arrête le client WebSocket"""
        logger.info("Stopping WebSocket client...")
        self.running = False
    
    def get_candles(self) -> List[Dict]:
        """Retourne toutes les bougies du buffer"""
        return list(self.candles_buffer)


# Fonction de test
async def test_connection():
    """Test de connexion basique"""
    def on_candle(candle):
        print(f"📊 New candle received: {candle}")
    
    client = BitgetWebSocketClient(
        symbol="BTCUSDT",
        timeframe="1m",
        on_message=on_candle
    )
    
    try:
        await client.run()
    except KeyboardInterrupt:
        client.stop()
        print("Test stopped by user")


if __name__ == "__main__":
    # Test du client
    asyncio.run(test_connection())

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)


class DataManager:
    """
    Gestionnaire de données pour multiples timeframes
    Stocke les bougies et fournit des DataFrames pour les calculs d'indicateurs
    """
    
    def __init__(self, max_candles: int = 1000):
        """
        Args:
            max_candles: Nombre maximum de bougies à conserver par timeframe
        """
        self.max_candles = max_candles
        # Structure: {timeframe: deque([candles])}
        self.data: Dict[str, deque] = {}
        
    def add_candle(self, timeframe: str, candle: Dict):
        """
        Ajoute une bougie pour un timeframe donné
        
        Args:
            timeframe: Le timeframe (ex: "1m", "5m", "1H")
            candle: Dict avec {time, open, high, low, close, volume}
        """
        if timeframe not in self.data:
            self.data[timeframe] = deque(maxlen=self.max_candles)
        
        # Vérifier si la bougie existe déjà (même timestamp)
        existing = self.data[timeframe]
        if existing and existing[-1]["time"] == candle["time"]:
            # Mettre à jour la dernière bougie (update en temps réel)
            existing[-1] = candle
        else:
            # Nouvelle bougie
            self.data[timeframe].append(candle)
        
        logger.debug(f"Added candle for {timeframe}: {candle}")
    
    def add_candles(self, timeframe: str, candles: List[Dict]):
        """Ajoute plusieurs bougies d'un coup"""
        if timeframe not in self.data:
            self.data[timeframe] = deque(maxlen=self.max_candles)
        
        for candle in candles:
            self.data[timeframe].append(candle)
        
        logger.info(f"Added {len(candles)} candles for {timeframe}")
    
    def get_candles(self, timeframe: str) -> List[Dict]:
        """Retourne toutes les bougies pour un timeframe"""
        if timeframe not in self.data:
            return []
        return list(self.data[timeframe])
    
    def get_dataframe(self, timeframe: str) -> pd.DataFrame:
        """
        Retourne les données sous forme de DataFrame pandas
        Utile pour les calculs d'indicateurs
        
        Returns:
            DataFrame avec colonnes: time, open, high, low, close, volume
        """
        candles = self.get_candles(timeframe)
        if not candles:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
        
        df = pd.DataFrame(candles)
        df = df.sort_values("time")
        df = df.reset_index(drop=True)
        
        return df
    
    def get_latest_candle(self, timeframe: str) -> Optional[Dict]:
        """Retourne la dernière bougie pour un timeframe"""
        if timeframe not in self.data or not self.data[timeframe]:
            return None
        return self.data[timeframe][-1]
    
    def clear(self, timeframe: Optional[str] = None):
        """
        Efface les données
        
        Args:
            timeframe: Si spécifié, efface uniquement ce timeframe, sinon tout
        """
        if timeframe:
            if timeframe in self.data:
                self.data[timeframe].clear()
                logger.info(f"Cleared data for {timeframe}")
        else:
            self.data.clear()
            logger.info("Cleared all data")
    
    def aggregate_timeframe(self, source_tf: str, target_tf: str, 
                           target_minutes: int) -> List[Dict]:
        """
        Agrège un timeframe source vers un timeframe cible
        Utile pour créer des timeframes personnalisés (ex: 12m, 24m)
        
        Args:
            source_tf: Timeframe source (ex: "1m")
            target_tf: Timeframe cible (ex: "12m")
            target_minutes: Durée en minutes du timeframe cible
        
        Returns:
            Liste de bougies agrégées
        """
        source_candles = self.get_candles(source_tf)
        if not source_candles:
            return []
        
        aggregated = []
        current_group = []
        group_start_time = None
        
        for candle in source_candles:
            candle_time = candle["time"]
            
            # Déterminer le début du groupe pour cette bougie
            group_time = (candle_time // (target_minutes * 60)) * (target_minutes * 60)
            
            if group_start_time is None:
                group_start_time = group_time
            
            if group_time == group_start_time:
                current_group.append(candle)
            else:
                # Créer la bougie agrégée du groupe précédent
                if current_group:
                    agg_candle = self._aggregate_candles(current_group, group_start_time)
                    aggregated.append(agg_candle)
                
                # Nouveau groupe
                current_group = [candle]
                group_start_time = group_time
        
        # Dernière bougie agrégée
        if current_group:
            agg_candle = self._aggregate_candles(current_group, group_start_time)
            aggregated.append(agg_candle)
        
        return aggregated
    
    def _aggregate_candles(self, candles: List[Dict], timestamp: int) -> Dict:
        """
        Agrège plusieurs bougies en une seule
        
        Args:
            candles: Liste de bougies à agréger
            timestamp: Timestamp de la bougie agrégée
        
        Returns:
            Bougie agrégée
        """
        if not candles:
            return {}
        
        return {
            "time": timestamp,
            "open": candles[0]["open"],
            "high": max(c["high"] for c in candles),
            "low": min(c["low"] for c in candles),
            "close": candles[-1]["close"],
            "volume": sum(c.get("volume", 0) for c in candles)
        }
    
    def count_candles(self, timeframe: str) -> int:
        """Retourne le nombre de bougies pour un timeframe"""
        if timeframe not in self.data:
            return 0
        return len(self.data[timeframe])


# Test basique
if __name__ == "__main__":
    dm = DataManager()
    
    # Simuler des données
    for i in range(100):
        candle = {
            "time": 1700000000 + i * 60,
            "open": 100 + i,
            "high": 101 + i,
            "low": 99 + i,
            "close": 100.5 + i,
            "volume": 1000
        }
        dm.add_candle("1m", candle)
    
    # Tester le DataFrame
    df = dm.get_dataframe("1m")
    print(f"DataFrame shape: {df.shape}")
    print(df.head())
    
    # Tester l'agrégation
    agg_5m = dm.aggregate_timeframe("1m", "5m", 5)
    print(f"\nAggregated 5m candles: {len(agg_5m)}")
    print(f"First 5m candle: {agg_5m[0]}")

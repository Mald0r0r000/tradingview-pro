import pandas as pd
import numpy as np
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class IndicatorExecutor:
    """
    Exécute le code Python généré depuis PineScript de manière sécurisée
    et retourne les résultats au format compatible avec lightweight-charts
    """
    
    def __init__(self):
        self.last_results = {}
        self.last_error = None
    
    def execute(self, python_code: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Exécute le code Python avec le DataFrame fourni
        
        Args:
            python_code: Code Python à exécuter (doit contenir une fonction calculate(df))
            df: DataFrame avec les données OHLCV
        
        Returns:
            Dict avec les séries calculées, format: {
                'series_name': {
                    'data': [...],
                    'color': 'blue',
                    'type': 'Line'
                }
            }
        """
        self.last_error = None
        
        try:
            # Préparer le contexte d'exécution
            context = self._prepare_context()
            
            # Exécuter le code dans un environnement contrôlé
            exec(python_code, context)
            
            # Vérifier que la fonction calculate existe
            if 'calculate' not in context:
                raise ValueError("Le code doit définir une fonction calculate(df)")
            
            # Appeler la fonction calculate
            calculate_func = context['calculate']
            results = calculate_func(df)
            
            # Convertir les résultats au format lightweight-charts
            formatted_results = self._format_results(results, df)
            
            self.last_results = formatted_results
            return formatted_results
        
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Execution error: {e}")
            raise
    
    def _prepare_context(self) -> Dict[str, Any]:
        """Prépare le contexte d'exécution avec les imports et fonctions utilitaires"""
        from pine_converter import calculate_rsi, calculate_macd, crossover, crossunder
        
        context = {
            'pd': pd,
            'np': np,
            'numpy': np,
            'pandas': pd,
            # Fonctions utilitaires
            'calculate_rsi': calculate_rsi,
            'calculate_macd': calculate_macd,
            'crossover': crossover,
            'crossunder': crossunder,
            # Éviter l'accès à des fonctions dangereuses
            '__builtins__': {
                'range': range,
                'len': len,
                'max': max,
                'min': min,
                'sum': sum,
                'abs': abs,
                'round': round,
                'float': float,
                'int': int,
                'str': str,
                'print': print,
            }
        }
        
        return context
    
    def _format_results(self, results: Dict, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Formate les résultats pour lightweight-charts
        
        Args:
            results: Résultats bruts de calculate()
            df: DataFrame original avec timestamps
        
        Returns:
            Résultats formatés pour le graphique
        """
        formatted = {}
        
        for name, value in results.items():
            try:
                # Si c'est déjà au bon format
                if isinstance(value, dict) and 'data' in value:
                    formatted[name] = self._format_series(value['data'], df, 
                                                          value.get('color', 'blue'),
                                                          value.get('type', 'Line'))
                # Si c'est une Series pandas
                elif isinstance(value, pd.Series):
                    formatted[name] = self._format_series(value, df, 'blue', 'Line')
                # Si c'est une liste
                elif isinstance(value, list):
                    formatted[name] = self._format_series(value, df, 'blue', 'Line')
                else:
                    logger.warning(f"Unknown result type for {name}: {type(value)}")
            
            except Exception as e:
                logger.error(f"Error formatting result {name}: {e}")
        
        return formatted
    
    def _format_series(self, data: Any, df: pd.DataFrame, color: str, 
                      series_type: str) -> Dict[str, Any]:
        """
        Convertit une série de données au format lightweight-charts
        
        Args:
            data: Données (Series, list, etc.)
            df: DataFrame avec les timestamps
            color: Couleur de la série
            series_type: Type de série (Line, Histogram, etc.)
        
        Returns:
            Dict formaté pour lightweight-charts
        """
        # Convertir en liste si nécessaire
        if isinstance(data, pd.Series):
            values = data.tolist()
        elif isinstance(data, list):
            values = data
        else:
            values = list(data)
        
        # Créer les points avec timestamps
        # Format: [{time: timestamp, value: y}]
        points = []
        timestamps = df['time'].tolist() if 'time' in df.columns else range(len(values))
        
        for i, (timestamp, value) in enumerate(zip(timestamps, values)):
            # Ignorer les NaN
            if pd.isna(value):
                continue
            
            points.append({
                'time': int(timestamp),
                'value': float(value)
            })
        
        return {
            'type': series_type,
            'data': points,
            'options': {
                'color': self._convert_color(color),
                'lineWidth': 2
            }
        }
    
    def _convert_color(self, color: str) -> str:
        """Convertit les noms de couleur PineScript en codes couleur"""
        color_map = {
            'blue': '#2962FF',
            'red': '#FF0000',
            'green': '#00FF00',
            'yellow': '#FFFF00',
            'orange': '#FF6D00',
            'purple': '#9C27B0',
            'gray': '#787B86',
            'white': '#FFFFFF',
            'black': '#000000',
        }
        
        return color_map.get(color.lower(), color)
    
    def get_last_error(self) -> str:
        """Retourne la dernière erreur"""
        return self.last_error


# Test
if __name__ == "__main__":
    # Créer des données de test
    test_df = pd.DataFrame({
        'time': range(1700000000, 1700000000 + 100),
        'open': np.random.randn(100).cumsum() + 100,
        'high': np.random.randn(100).cumsum() + 102,
        'low': np.random.randn(100).cumsum() + 98,
        'close': np.random.randn(100).cumsum() + 100,
        'volume': np.random.randint(1000, 10000, 100)
    })
    
    # Code Python test (exemple généré par le converter)
    test_code = """
# Auto-generated from PineScript
import pandas as pd
import numpy as np

def calculate(df):
    results = {}
    
    sma20 = df['close'].rolling(20).mean()
    sma50 = df['close'].rolling(50).mean()
    
    results['SMA 20'] = {'data': sma20, 'color': 'blue', 'type': 'Line'}
    results['SMA 50'] = {'data': sma50, 'color': 'red', 'type': 'Line'}
    
    return results
"""
    
    executor = IndicatorExecutor()
    
    try:
        results = executor.execute(test_code, test_df)
        print("Execution successful!")
        print(f"Number of series: {len(results)}")
        for name, series in results.items():
            print(f"  - {name}: {len(series['data'])} points")
    except Exception as e:
        print(f"Execution failed: {e}")

import re
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PineScriptConverter:
    """
    Convertisseur PineScript vers Python
    Gère les cas basiques et les fonctions ta.* courantes
    """
    
    def __init__(self):
        self.converted_code = ""
        self.errors = []
    
    def convert(self, pine_code: str) -> str:
        """
        Convertit du code PineScript en Python
        
        Args:
            pine_code: Code PineScript source
        
        Returns:
            Code Python converti
        """
        self.errors = []
        lines = pine_code.strip().split('\n')
        converted_lines = []
        
        # En-tête Python
        converted_lines.append("# Auto-generated from PineScript")
        converted_lines.append("import pandas as pd")
        converted_lines.append("import numpy as np")
        converted_lines.append("")
        
        # Variable pour stocker les outputs à afficher
        converted_lines.append("# Cette fonction sera appelée avec le DataFrame")
        converted_lines.append("def calculate(df):")
        converted_lines.append("    results = {}")
        converted_lines.append("")
        
        for line in lines:
            stripped = line.strip()
            
            # Ignorer les commentaires et lignes vides
            if not stripped or stripped.startswith('//'):
                continue
            
            # Ignorer les directives //@version
            if stripped.startswith('//@'):
                continue
            
            # Convertir la ligne
            try:
                converted = self._convert_line(stripped)
                if converted:
                    # Indenter pour la fonction
                    converted_lines.append(f"    {converted}")
            except Exception as e:
                self.errors.append(f"Error converting '{stripped}': {e}")
                logger.error(f"Conversion error: {e}")
        
        # Retourner les résultats
        converted_lines.append("")
        converted_lines.append("    return results")
        
        self.converted_code = '\n'.join(converted_lines)
        return self.converted_code
    
    def _convert_line(self, line: str) -> Optional[str]:
        """Convertit une ligne individuelle"""
        
        # Déclaration d'indicateur (ex: indicator("My Indicator"))
        if line.startswith('indicator(') or line.startswith('strategy('):
            # Ignorer, juste un commentaire en Python
            return f"# {line}"
        
        # plot() - affichage d'une série
        if 'plot(' in line:
            return self._convert_plot(line)
        
        # Déclaration de variable avec assignation
        if '=' in line and not line.startswith('if') and not line.startswith('for'):
            return self._convert_assignment(line)
        
        # Fonctions ta.*
        if 'ta.' in line:
            return self._convert_ta_function(line)
        
        # Par défaut, retourner tel quel avec commentaire
        return f"# TODO: Manual conversion needed - {line}"
    
    def _convert_assignment(self, line: str) -> str:
        """Convertit les assignations de variables"""
        
        # Enlever les types (var, float, int, bool, etc.)
        line = re.sub(r'\b(var\s+)?(float|int|bool|string|color)\s+', '', line)
        
        # Convertir les références de séries: close[1] -> df['close'].shift(1)
        line = self._convert_series_references(line)
        
        # Convertir les fonctions ta.*
        line = self._convert_ta_inline(line)
        
        # Convertir les opérateurs logiques
        line = line.replace(' and ', ' & ')
        line = line.replace(' or ', ' | ')
        line = line.replace(' not ', ' ~ ')
        
        return line
    
    def _convert_series_references(self, line: str) -> str:
        """Convertit les références de séries: close[1] -> df['close'].shift(1)"""
        
        # Pattern pour détecter les séries OHLCV
        series_names = ['open', 'high', 'low', 'close', 'volume', 'hl2', 'hlc3', 'ohlc4']
        
        for series in series_names:
            # Référence avec offset: close[1]
            pattern = rf'\b{series}\[(\d+)\]'
            replacement = rf"df['{series}'].shift(\1)"
            line = re.sub(pattern, replacement, line)
            
            # Référence simple: close
            pattern = rf'\b{series}\b(?!\[)'
            replacement = rf"df['{series}']"
            line = re.sub(pattern, replacement, line)
        
        # Séries calculées spéciales
        line = line.replace("df['hl2']", "(df['high'] + df['low']) / 2")
        line = line.replace("df['hlc3']", "(df['high'] + df['low'] + df['close']) / 3")
        line = line.replace("df['ohlc4']", "(df['open'] + df['high'] + df['low'] + df['close']) / 4")
        
        return line
    
    def _convert_ta_inline(self, line: str) -> str:
        """Convertit les fonctions ta.* inline"""
        
        # ta.sma(source, length)
        pattern = r'ta\.sma\(([^,]+),\s*(\d+)\)'
        replacement = r'\1.rolling(\2).mean()'
        line = re.sub(pattern, replacement, line)
        
        # ta.ema(source, length)
        pattern = r'ta\.ema\(([^,]+),\s*(\d+)\)'
        replacement = r'\1.ewm(span=\2, adjust=False).mean()'
        line = re.sub(pattern, replacement, line)
        
        # ta.rsi(source, length)
        pattern = r'ta\.rsi\(([^,]+),\s*(\d+)\)'
        replacement = r'calculate_rsi(\1, \2)'
        line = re.sub(pattern, replacement, line)
        
        # ta.crossover(a, b)
        pattern = r'ta\.crossover\(([^,]+),\s*([^)]+)\)'
        replacement = r'crossover(\1, \2)'
        line = re.sub(pattern, replacement, line)
        
        # ta.crossunder(a, b)
        pattern = r'ta\.crossunder\(([^,]+),\s*([^)]+)\)'
        replacement = r'crossunder(\1, \2)'
        line = re.sub(pattern, replacement, line)
        
        return line
    
    def _convert_ta_function(self, line: str) -> str:
        """Convertit les lignes contenant des fonctions ta.*"""
        return self._convert_assignment(line)
    
    def _convert_plot(self, line: str) -> str:
        """
        Convertit les statements plot() 
        Ex: plot(sma, color=color.blue) -> results['sma'] = sma
        """
        # Extraire le nom de la variable à plotter
        match = re.search(r'plot\(([^,)]+)', line)
        if match:
            var_name = match.group(1).strip()
            # Extraire le titre si présent
            title_match = re.search(r'title\s*=\s*["\']([^"\']+)["\']', line)
            title = title_match.group(1) if title_match else var_name
            
            # Extraire la couleur si présente
            color_match = re.search(r'color\s*=\s*color\.(\w+)', line)
            color = color_match.group(1) if color_match else 'blue'
            
            return f"results['{title}'] = {{'data': {var_name}.tolist(), 'color': '{color}'}}"
        
        return f"# TODO: Convert plot - {line}"
    
    def get_errors(self) -> list:
        """Retourne la liste des erreurs de conversion"""
        return self.errors


# Fonctions utilitaires pour les calculs d'indicateurs
def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calcule le RSI (Relative Strength Index)"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calcule le MACD"""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def crossover(series1: pd.Series, series2: pd.Series) -> pd.Series:
    """Détecte un croisement haussier (series1 croise series2 vers le haut)"""
    return (series1 > series2) & (series1.shift(1) <= series2.shift(1))


def crossunder(series1: pd.Series, series2: pd.Series) -> pd.Series:
    """Détecte un croisement baissier (series1 croise series2 vers le bas)"""
    return (series1 < series2) & (series1.shift(1) >= series2.shift(1))


# Test
if __name__ == "__main__":
    converter = PineScriptConverter()
    
    # Exemple de script PineScript simple
    pine_code = """
    //@version=5
    indicator("SMA Cross", overlay=true)
    
    sma20 = ta.sma(close, 20)
    sma50 = ta.sma(close, 50)
    
    plot(sma20, color=color.blue, title="SMA 20")
    plot(sma50, color=color.red, title="SMA 50")
    """
    
    python_code = converter.convert(pine_code)
    print("Converted Python code:")
    print("=" * 50)
    print(python_code)
    print("=" * 50)
    
    if converter.get_errors():
        print("\nConversion errors:")
        for error in converter.get_errors():
            print(f"  - {error}")

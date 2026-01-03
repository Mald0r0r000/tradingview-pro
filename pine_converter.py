import re
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class PineScriptConverter:
    """
    Convertisseur PineScript vers Python (amélioré)
    Gère plus de cas: inputs, conditionals, opérateurs ternaires, etc.
    """
    
    def __init__(self):
        self.converted_code = ""
        self.errors = []
        self.warnings = []
        self.indent_level = 1  # Commence à 1 car on est dans def calculate()
    
    def convert(self, pine_code: str) -> str:
        """
        Convertit du code PineScript en Python
        
        Args:
            pine_code: Code PineScript source
        
        Returns:
            Code Python converti
        """
        self.errors = []
        self.warnings = []
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
        
        for i, line in enumerate(lines):
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
                    indent = "    " * (self.indent_level + 1)
                    converted_lines.append(f"{indent}{converted}")
            except Exception as e:
                self.errors.append(f"Line {i+1}: Error converting '{stripped}': {e}")
                logger.error(f"Conversion error on line {i+1}: {e}")
                converted_lines.append(f"    # ERROR: Could not convert: {stripped}")
        
        # Retourner les résultats
        converted_lines.append("")
        converted_lines.append("    return results")
        
        self.converted_code = '\n'.join(converted_lines)
        return self.converted_code
    
    def _convert_line(self, line: str) -> Optional[str]:
        """Convertit une ligne individuelle"""
        
        # Déclaration d'indicateur/strategy
        if line.startswith(('indicator(', 'strategy(')):
            return f"# {line}"
        
        # Déclaration de type personnalisé (type FVG, etc.) - ignorer
        if line.startswith('type '):
            self.warnings.append(f"Custom types not supported: {line}")
            return f"# UNSUPPORTED: {line}"
        
        # Inputs - convertir en constantes
        if 'input.' in line:
            return self._convert_input(line)
        
        # plot(), plotshape(), bgcolor() - convertir ou commenter
        if any(func in line for func in ['plot(', 'plotshape(', 'bgcolor(', 'alertcondition(']):
            return self._convert_plot_functions(line)
        
        # Conditions if
        if line.startswith('if '):
            return self._convert_if(line)
        
        # else
        if line == 'else' or line.startswith('else'):
            return line
        
        # Boucles for
        if line.startswith('for '):
            self.warnings.append("For loops require manual conversion")
            return f"# TODO: Manual for loop conversion - {line}"
        
        # Déclaration de variable avec assignation
        if '=' in line and not any(line.startswith(kw) for kw in ['if', 'for', 'while']):
            # Détecter opérateur d'assignation := (Pine v5)
            if ':=' in line:
                return self._convert_reassignment(line)
            else:
                return self._convert_assignment(line)
        
        # Fonctions ta.*
        if 'ta.' in line:
            return self._convert_ta_function(line)
        
        # Array/box/other Pine-specific - marquer comme TODO
        if any(keyword in line for keyword in ['array.', 'box.', 'line.', 'label.']):
            self.warnings.append(f"Advanced Pine feature not supported: {line}")
            return f"# UNSUPPORTED (requires manual conversion): {line}"
        
        # Par défaut, retourner tel quel avec commentaire
        return f"# TODO: Manual conversion - {line}"
    
    def _convert_input(self, line: str) -> str:
        """Convertit les input.* en constantes Python"""
        # input.int(10, "Title") -> 10
        # input.bool(true, "Title") -> True
        # input.float(1.5, "Title") -> 1.5
        
        # Extraire la valeur par défaut
        match = re.search(r'input\.\w+\(([^,)]+)', line)
        if match:
            default_value = match.group(1).strip()
            
            # Convertir true/false en True/False
            default_value = default_value.replace('true', 'True').replace('false', 'False')
            
            # Garder le nom de la variable
            var_match = re.match(r'(\w+)\s*=', line)
            if var_match:
                var_name = var_match.group(1)
                return f"{var_name} = {default_value}  # Input parameter"
        
        return f"# TODO: Convert input - {line}"
    
    def _convert_assignment(self, line: str) -> str:
        """Convertit les assignations de variables"""
        
        # Enlever les types (var, float, int, bool, etc.)
        line = re.sub(r'\b(var\s+)?(float|int|bool|string|color)\s+', '', line)
        
        # Convertir les opérateurs ternaires: condition ? value1 : value2
        line = self._convert_ternary(line)
        
        # Convertir les références de séries: close[1] -> df['close'].shift(1)
        line = self._convert_series_references(line)
        
        # Convertir les fonctions ta.*
        line = self._convert_ta_inline(line)
        
        # Convertir les opérateurs logiques
        line = line.replace(' and ', ' & ')
        line = line.replace(' or ', ' | ')
        line = line.replace(' not ', ' ~ ')
        
        return line
    
    def _convert_reassignment(self, line: str) -> str:
        """Convertit les réassignations := en ="""
        line = line.replace(':=', '=')
        return self._convert_assignment(line)
    
    def _convert_if(self, line: str) -> str:
        """Convertit les conditions if"""
        # if condition -> if condition:
        line = line.replace('if ', 'if ')
        
        # Convertir les opérateurs
        line = self._convert_ternary(line)
        line = self._convert_series_references(line)
        line = line.replace(' and ', ' & ')
        line = line.replace(' or ', ' | ')
        line = line.replace(' not ', ' ~ ')
        
        # Ajouter : à la fin si pas présent
        if not line.endswith(':'):
            line += ':'
        
        return line
    
    def _convert_ternary(self, line: str) -> str:
        """Convertit les opérateurs ternaires: a ? b : c -> b if a else c"""
        # Pattern simple pour opérateur ternaire
        pattern = r'(\w+|\([^)]+\))\s*\?\s*([^:]+)\s*:\s*(.+)'
        
        def ternary_replacement(match):
            condition = match.group(1).strip()
            if_true = match.group(2).strip()
            if_false = match.group(3).strip()
            return f"{if_true} if {condition} else {if_false}"
        
        # Appliquer la conversion
        line = re.sub(pattern, ternary_replacement, line)
        
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
            
            # Référence simple: close (mais pas dans df['close'])
            # Éviter de convertir si déjà dans df['...']
            pattern = rf"(?<!df\[')(?<!\['){series}(?!'\])(?!\[)"
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
        pattern = r'ta\.sma\(([^,]+),\s*(\w+)\)'
        replacement = r'\1.rolling(\2).mean()'
        line = re.sub(pattern, replacement, line)
        
        # ta.ema(source, length)
        pattern = r'ta\.ema\(([^,]+),\s*(\w+)\)'
        replacement = r'\1.ewm(span=\2, adjust=False).mean()'
        line = re.sub(pattern, replacement, line)
        
        # ta.rsi(source, length)
        pattern = r'ta\.rsi\(([^,]+),\s*(\w+)\)'
        replacement = r'calculate_rsi(\1, \2)'
        line = re.sub(pattern, replacement, line)
        
        # ta.stdev(source, length)
        pattern = r'ta\.stdev\(([^,]+),\s*(\w+)\)'
        replacement = r'\1.rolling(\2).std()'
        line = re.sub(pattern, replacement, line)
        
        # ta.pivothigh(source, leftbars, rightbars) - complexe, noter
        if 'ta.pivothigh' in line or 'ta.pivotlow' in line:
            self.warnings.append("Pivot functions require custom implementation")
            return f"# NOTE: Pivots need manual implementation - {line}"
        
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
    
    def _convert_plot_functions(self, line: str) -> str:
        """Convertit plot(), plotshape(), bgcolor(), etc."""
        
        # plot(series, ...)
        if line.startswith('plot('):
            match = re.search(r'plot\(([^,)]+)', line)
            if match:
                var_name = match.group(1).strip()
                
                # Convertir les références
                var_name = self._convert_series_references(var_name)
                
                # Extraire le titre
                title_match = re.search(r'title\s*=\s*["\']([^"\']+)["\']', line)
                title = title_match.group(1) if title_match else var_name.replace("df['", "").replace("']", "")
                
                # Extraire la couleur
                color_match = re.search(r'color\s*=\s*color\.(\w+)', line)
                color = color_match.group(1) if color_match else 'blue'
                
                return f"results['{title}'] = {{'data': {var_name}, 'color': '{color}', 'type': 'Line'}}"
        
        # plotshape - ignore, pas supporté dans lightweight-charts
        if 'plotshape(' in line:
            self.warnings.append("plotshape not supported in lightweight-charts")
            return f"# UNSUPPORTED: {line}"
        
        # bgcolor - ignore
        if 'bgcolor(' in line:
            return f"# UNSUPPORTED (bgcolor): {line}"
        
        # alertcondition - ignore
        if 'alertcondition(' in line:
            return f"# INFO: Alert condition - {line}"
        
        return f"# TODO: Convert plot function - {line}"
    
    def get_errors(self) -> List[str]:
        """Retourne la liste des erreurs de conversion"""
        return self.errors
    
    def get_warnings(self) -> List[str]:
        """Retourne la liste des avertissements"""
        return self.warnings


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
    indicator("Test Indicator", overlay=true)
    
    // Inputs
    len = input.int(20, "Length")
    showMA = input.bool(true, "Show MA")
    
    // Calculs
    ma = ta.sma(close, len)
    upper = ma + ta.stdev(close, len) * 2
    
    // Conditions
    bullish = close > ma
    signal = bullish ? 1 : 0
    
    // Plots
    plot(ma, color=color.blue, title="MA")
    plot(upper, color=color.red, title="Upper")
    """
    
    python_code = converter.convert(pine_code)
    print("Converted Python code:")
    print("=" * 50)
    print(python_code)
    print("=" * 50)
    
    if converter.get_warnings():
        print("\nWarnings:")
        for warning in converter.get_warnings():
            print(f"  ⚠️  {warning}")
    
    if converter.get_errors():
        print("\nErrors:")
        for error in converter.get_errors():
            print(f"  ❌ {error}")

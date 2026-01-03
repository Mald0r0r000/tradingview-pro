# Limitations du Convertisseur PineScript

Le convertisseur PineScript-to-Python est conçu pour gérer les cas **simples et courants**. Les indicateurs complexes nécessitent souvent une adaptation manuelle.

## ✅ Ce qui est Supporté

### Inputs
```pinescript
len = input.int(20, "Length")
mult = input.float(1.5, "Multiplier")
show = input.bool(true, "Show")
```
→ Converti en constantes Python

### Fonctions ta.* Basiques
- `ta.sma()` → `.rolling().mean()`
- `ta.ema()` → `.ewm().mean()`
- `ta.rsi()` → `calculate_rsi()`
- `ta.stdev()` → `.rolling().std()`
- `ta.crossover()` / `ta.crossunder()`

### Références de Séries
```pinescript
close        → df['close']
close[1]     → df['close'].shift(1)
high[2]      → df['high'].shift(2)
```

### Opérateurs Ternaires
```pinescript
signal = condition ? 1 : 0
```
→ Converti en `signal = 1 if condition else 0`

### Conditions Simples
```pinescript
if close > ma
    value = 1
```
→ Converti en Python avec indentation

### Plot Basique
```pinescript
plot(ma, color=color.blue, title="MA")
```
→ Ajouté aux résultats pour affichage

## ❌ Ce qui N'est PAS Supporté

### 1. Boxes, Lines, Labels
```pinescript
box.new(...)
line.new(...)
label.new(...)
```
**Raison**: Ces fonctionnalités sont spécifiques à TradingView et n'existent pas dans lightweight-charts.

**Solution**: Simplifiez l'indicateur pour utiliser uniquement des lignes/histogrammes.

### 2. Types Personnalisés
```pinescript
type FVG
    box id
    floatlimitLevel
    bool isBull
```
**Raison**: Conversion complexe nécessitant restructuration.

**Solution**: Utilisez des dictionnaires Python ou simplifiez la logique.

### 3. Arrays Dynamiques
```pinescript
var FVG[] fvg_list = array.new<FVG>()
array.push(fvg_list, item)
```
**Raison**: Les arrays Pine avec états persistants nécessitent une logique différente en pandas.

**Solution**: Utilisez des listes Python ou des DataFrames avec colonnes supplémentaires.

### 4. Fonctions Pivot
```pinescript
ta.pivothigh(high, 10, 3)
ta.pivotlow(low, 10, 3)
```
**Raison**: Calcul complexe nécessitant implémentation personnalisée.

**Solution**: Implémentez manuellement ou utilisez une bibliothèque comme `pandas_ta`.

### 5. plotshape, bgcolor, alertcondition
```pinescript
plotshape(condition, title="Signal", ...)
bgcolor(condition ? color.red : na)
alertcondition(signal, ...)
```
**Raison**: Fonctionnalités UI/decoration non supportées dans notre système.

**Solution**: Concentrez-vous sur les calculs, pas la décoration.

### 6. Boucles for Complexes
```pinescript
for i = 0 to 100
    // logique complexe
```
**Raison**: Les boucles nécessitent adaptation selon le contexte.

**Solution**: Utilisez les opérations vectorisées pandas quand possible.

### 7. Variables var (état persistant)
```pinescript
var float last_value = na
```
**Raison**: Les variables persistantes entre bougies nécessitent une gestion d'état.

**Solution**: Utilisez des techniques pandas (shift, cumsum, etc.) ou stockez dans le DataFrame.

## 💡 Conseils pour Adapter Vos Indicateurs

### 1. Simplifiez d'Abord
- Supprimez les boxes/labels
- Gardez uniquement les calculs mathématiques
- Utilisez plot() pour les lignes principales

### 2. Exemple: Indicateur Complexe → Simple

**Avant (Complexe)**:
```pinescript
type Signal
    box display
    float price
    
var Signal[] signals = array.new<Signal>()

if condition
    newBox = box.new(...)
    array.push(signals, Signal.new(newBox, close))
    
plot(close, color=color.new(color.blue, 50))
```

**Après (Simplifié)**:
```pinescript
// Calculer juste le signal
signal_value = condition ? close : na

// Afficher
plot(signal_value, color=color.blue, title="Signal")
```

### 3. Utilisez des Indicateurs Simples comme Base

Commencez avec des exemples qui fonctionnent:
- SMA/EMA crosses
- RSI simple
- Bollinger Bands

Puis ajoutez progressivement votre logique.

### 4. Testez Progressivement

1. Convertir
2. Corriger les erreurs évidentes
3. Tester sur le graphique
4. Itérer

## 📝 Exemple de Conversion Manuelle

### Indicateur Original (avec boxes)
Votre indicateur FVI Sniper utilise:
- Types personnalisés (FVG)
- Boxes pour visualisation
- Arrays dynamiques
- Variables persistantes

### Approche Simplifiée

Pour l'adapter, il faudrait:

1. **Garder** les calculs de base:
   - Z-Score
   - Liquidity levels (pivots)
   - Conditions de sweep

2. **Supprimer** les boxes et les visualiser comme lignes:
   ```python
   # Au lieu de boxes FVG
   fvg_bull_level = df['high'].shift(2).where(fvg_bull_cond)
   results['FVG Bull'] = {'data': fvg_bull_level, 'color': 'green', 'type': 'Line'}
   ```

3. **Simplifier** la logique de mitigation:
   - Au lieu de tracker chaque box, marquez simplement les niveaux

## 🔗 Ressources

- **Pandas Documentation**: https://pandas.pydata.org/docs/
- **Pandas TA**: https://github.com/twopirllc/pandas-ta (bibliothèque avec indicateurs prêts)
- **Exemples**: Voir `examples/pine_indicators.md` dans le projet

## ✉️ Besoin d'Aide?

Si votre indicateur est trop complexe:
1. Partagez le code PineScript
2. Expliquez l'objectif principal
3. Je peux vous aider à créer une version simplifiée compatible

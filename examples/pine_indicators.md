# Exemples d'Indicateurs PineScript

Collection d'exemples d'indicateurs PineScript que vous pouvez tester dans l'éditeur.

## 1. SMA Simple (Simple Moving Average)

```pinescript
//@version=5
indicator("SMA 20", overlay=true)

sma20 = ta.sma(close, 20)

plot(sma20, color=color.blue, title="SMA 20")
```

## 2. Croisement de Moyennes Mobiles

```pinescript
//@version=5
indicator("SMA Cross", overlay=true)

sma20 = ta.sma(close, 20)
sma50 = ta.sma(close, 50)

plot(sma20, color=color.blue, title="SMA 20")
plot(sma50, color=color.red, title="SMA 50")
```

## 3. EMA (Exponential Moving Average)

```pinescript
//@version=5
indicator("EMA", overlay=true)

ema12 = ta.ema(close, 12)
ema26 = ta.ema(close, 26)

plot(ema12, color=color.green, title="EMA 12")
plot(ema26, color=color.orange, title="EMA 26")
```

## 4. RSI (Relative Strength Index)

```pinescript
//@version=5
indicator("RSI", overlay=false)

rsi = ta.rsi(close, 14)

plot(rsi, color=color.purple, title="RSI 14")
```

## 5. Bollinger Bands

```pinescript
//@version=5
indicator("Bollinger Bands", overlay=true)

length = 20
mult = 2.0

basis = ta.sma(close, length)
dev = mult * ta.stdev(close, length)

upper = basis + dev
lower = basis - dev

plot(basis, color=color.blue, title="Basis")
plot(upper, color=color.red, title="Upper")
plot(lower, color=color.green, title="Lower")
```

## Notes d'utilisation

- Copiez l'un de ces exemples dans l'éditeur PineScript de l'application
- Cliquez sur "Convertir" pour générer le code Python
- Vérifiez le code généré et cliquez sur "Sauvegarder"
- L'indicateur apparaîtra dans la sidebar et sera appliqué au graphique

## Limitations actuelles

Le convertisseur gère les cas basiques. Pour des scripts plus complexes:
- Les boucles `for` peuvent nécessiter un ajustement manuel
- Les conditions `if/else` complexes peuvent nécessiter une révision
- Certaines fonctions `ta.*` avancées peuvent ne pas être supportées

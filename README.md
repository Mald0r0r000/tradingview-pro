# 🕯️ TradingView Pro - Application de Charting avec Bitget

Application Streamlit de charting en temps réel utilisant l'API WebSocket de Bitget avec support multi-timeframe, convertisseur PineScript intégré, et pages spécialisées pour analyses avancées.

## 🚀 Fonctionnalités

### Page Principale (Home)
- ✅ **Connexion WebSocket Bitget** - Données en temps réel pour BTCUSDT.P
- ✅ **Multi-Timeframe** - Support de 1m à 1M (1m, 3m, 5m, 15m, 30m, 1H, 4H, 1D, 1W, 1M)
- ✅ **Convertisseur PineScript** - Convertit vos indicateurs PineScript en Python
- ✅ **Éditeur Intégré** - Créez et testez vos indicateurs directement dans l'UI
- ✅ **Graphique Professionnel** - Powered by TradingView Lightweight Charts
- ✅ **Reconnexion Automatique** - Gestion intelligente des déconnexions

### Page Bitget Sniper 🎯
- ✅ **Liquidation Levels** - Calcul automatique des niveaux de liquidation (125x, 100x, 50x, 25x)
- ✅ **Logique Pac-Man** - Lignes qui disparaissent quand touchées par le prix
- ✅ **GEX Integration** - Call Wall, Put Wall, Zero Gamma
- ✅ **Multi-Tier Analysis** - 3 niveaux d'analyse (Scalping, Intraday, Swing)
- ✅ **Visualisation Plotly** - Graphiques interactifs avancés
- ✅ **Données Temps Réel** - Utilise le même WebSocket que la page principale

## 📦 Installation

1. **Cloner/Naviguer vers le projet**
   ```bash
   cd /Users/antoinebedos/.gemini/antigravity/scratch/trading-chart-app
   ```

2. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration (optionnel)**
   
   Pour les canaux publics (klines), aucune configuration n'est nécessaire. Si vous souhaitez utiliser des canaux privés dans le futur:
   
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # Éditez .streamlit/secrets.toml avec vos clés API Bitget
   ```

## 🎯 Utilisation

### Lancer l'application

```bash
streamlit run Home.py
```

L'application s'ouvrira dans votre navigateur à `http://localhost:8501`

**Navigation**: Utilisez la sidebar pour basculer entre les pages :
- 🏠 **Home** : Graphique principal avec indicateurs personnalisés
- 🎯 **Bitget Sniper** : Analyse des liquidations et GEX

### Utiliser le Convertisseur PineScript

1. Cliquez sur "➕ Nouvel Indicateur" dans la sidebar
2. Collez votre code PineScript dans l'éditeur gauche
3. Cliquez sur "🔄 Convertir" pour générer le Python
4. Vérifiez le code généré à droite
5. Cliquez sur "💾 Sauvegarder" et donnez un nom à votre indicateur
6. Activez/désactivez l'indicateur dans la sidebar

### Exemples d'Indicateurs

Voir le fichier [`examples/pine_indicators.md`](examples/pine_indicators.md) pour des exemples d'indicateurs prêts à l'emploi.

## 🏗️ Architecture

```
trading-chart-app/
├── app.py                    # Application Streamlit principale
├── bitget_ws_client.py       # Client WebSocket Bitget
├── data_manager.py           # Gestionnaire de données multi-timeframe
├── pine_converter.py         # Convertisseur PineScript → Python
├── indicator_executor.py     # Exécuteur sécurisé d'indicateurs
├── requirements.txt          # Dépendances Python
├── .streamlit/
│   └── secrets.toml.example  # Template de configuration
└── examples/
    └── pine_indicators.md    # Exemples d'indicateurs
```

## 🔧 Composants Principaux

### WebSocket Client (`bitget_ws_client.py`)
- Connexion au WebSocket Bitget v2
- Support multi-timeframe
- Reconnexion automatique
- Gestion du ping/pong

### Data Manager (`data_manager.py`)
- Stockage des bougies par timeframe
- Conversion en DataFrame pandas
- Agrégation de timeframes personnalisés

### PineScript Converter (`pine_converter.py`)
- Conversion des variables et opérateurs
- Mapping des fonctions `ta.*` (sma, ema, rsi, etc.)
- Gestion des références de séries (`close[1]` → `df['close'].shift(1)`)

### Indicator Executor (`indicator_executor.py`)
- Exécution sécurisée du code Python généré
- Formatage des résultats pour lightweight-charts
- Gestion des erreurs

## 📊 Timeframes Supportés

| Timeframe | Status | Notes |
|-----------|--------|-------|
| 1m, 3m, 5m, 15m, 30m | ✅ Natif | API Bitget |
| 1H, 4H | ✅ Natif | API Bitget |
| 1D, 1W, 1M | ✅ Natif | API Bitget (UTC) |
| 12m, 24m | ⚠️ Agrégation | Calculé depuis 1m |

## 🐛 Troubleshooting

### WebSocket ne se connecte pas
- Vérifiez votre connexion Internet
- Vérifiez que le port 443 n'est pas bloqué
- Consultez les logs dans la console

### Indicateur ne s'affiche pas
- Vérifiez qu'il y a suffisamment de données (certains indicateurs nécessitent un historique)
- Vérifiez le code Python généré pour des erreurs
- Activez l'indicateur dans la sidebar

### Conversion PineScript échoue
- Le convertisseur gère les cas basiques
- Les scripts complexes peuvent nécessiter des ajustements manuels
- Consultez la section "Code Python Généré" pour voir les TODO

## 🚧 Limitations Connues

- Le convertisseur PineScript est basique et ne supporte pas toutes les fonctionnalités
- Les boucles `for` et conditions `if/else` complexes nécessitent un ajustement manuel
- Timeframes 12m et 24m sont agrégés côté client (non optimaux pour grandes quantités de données)

## 📝 TODO / Améliorations Futures

- [ ] Support de multiples symboles
- [ ] Sauvegarde persistante des indicateurs (fichiers/DB)
- [ ] Export des données en CSV
- [ ] Alertes basées sur les indicateurs
- [ ] Mode dark/light personnalisable
- [ ] Support REST API pour données historiques

## 🤝 Contribution

Pour ajouter des fonctionnalités ou corriger des bugs, modifiez les fichiers correspondants et testez localement avant de déployer.

## 📄 License

Ce projet est créé pour un usage personnel/éducatif.

## 🔗 Ressources

- [Documentation Bitget WebSocket](https://www.bitget.com/api-doc/contract/websocket/public/Candlesticks-Channel)
- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [PineScript Documentation](https://www.tradingview.com/pine-script-docs/)

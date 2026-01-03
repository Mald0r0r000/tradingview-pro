# 🚀 Guide de Déploiement - GitHub & Streamlit Cloud

## Étape 1: Créer le Repository GitHub

1. **Aller sur GitHub** : [https://github.com/new](https://github.com/new)

2. **Créer le repository** :
   - **Repository name** : `tradingview-pro` (ou autre nom)
   - **Description** : `Real-time trading chart with Bitget WebSocket and PineScript converter`
   - **Visibility** : Public ou Private (selon votre préférence)
   - ⚠️ **NE PAS** cocher "Initialize with README" (on a déjà les fichiers)

3. **Cliquer sur "Create repository"**

## Étape 2: Pusher le Code

Une fois le repository créé, GitHub affiche les commandes. Utilisez celles-ci dans le terminal :

```bash
cd /Users/antoinebedos/.gemini/antigravity/scratch/trading-chart-app

# Configurer la remote (remplacez YOUR_USERNAME et YOUR_REPO)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# Renommer la branche en main (optionnel mais recommandé)
git branch -M main

# Push
git push -u origin main
```

**Exemple concret** :
```bash
# Si votre username est "antoinebedos" et le repo "tradingview-pro"
git remote add origin https://github.com/antoinebedos/tradingview-pro.git
git branch -M main
git push -u origin main
```

## Étape 3: Déployer sur Streamlit Cloud

### 3.1 Aller sur Streamlit Cloud

1. Aller sur : [https://share.streamlit.io/](https://share.streamlit.io/)
2. Se connecter avec votre compte GitHub

### 3.2 Créer un New App

1. Cliquer sur **"New app"**
2. Remplir les informations :
   - **Repository** : Sélectionner votre repo (ex: `antoinebedos/tradingview-pro`)
   - **Branch** : `main`
   - **Main file path** : `app.py`
   - **App URL** : Choisir un nom unique (ex: `tradingview-pro`)

### 3.3 Configuration (Optionnel)

Si vous avez besoin de secrets (API keys Bitget pour canaux privés) :

1. Cliquer sur **"Advanced settings"**
2. Dans la section **"Secrets"**, coller le contenu de `.streamlit/secrets.toml.example`
3. Modifier avec vos vraies clés API si nécessaire

**Note** : Pour les canaux publics (klines), les secrets ne sont PAS nécessaires.

### 3.4 Déployer

1. Cliquer sur **"Deploy!"**
2. Attendre quelques minutes pendant que Streamlit Cloud :
   - Clone le repo
   - Installe les dépendances depuis `requirements.txt`
   - Lance l'application

### 3.5 Vérification

Une fois déployé, vous verrez :
- ✅ URL de l'application (ex: `https://tradingview-pro.streamlit.app`)
- ✅ Logs de déploiement
- ✅ Status "Running"

## 🔍 Vérifications Post-Déploiement

### Test 1: WebSocket Connection
- [ ] L'application se charge
- [ ] Le WebSocket se connecte (voir logs en bas)
- [ ] Les premières bougies apparaissent (10-30 secondes)

### Test 2: Timeframe Switching
- [ ] Changer de timeframe dans la sidebar
- [ ] Les nouvelles données se chargent

### Test 3: PineScript Converter
- [ ] Cliquer sur "➕ Nouvel Indicateur"
- [ ] Coller un exemple de PineScript
- [ ] Convertir et sauvegarder
- [ ] L'indicateur s'affiche sur le graphique

## ⚠️ Troubleshooting

### Erreur: "ModuleNotFoundError"
**Cause** : Dépendance manquante dans `requirements.txt`
**Solution** : 
1. Vérifier `requirements.txt`
2. Ajouter la dépendance manquante
3. Commit et push
4. Streamlit redéploie automatiquement

### Erreur: "WebSocket connection failed"
**Cause** : Firewall ou timeout
**Solution** : 
- Vérifier les logs Streamlit Cloud
- Attendre quelques secondes (le WebSocket peut prendre du temps)
- Vérifier que l'URL Bitget est accessible

### L'application est lente
**Cause** : Ressources limitées sur Streamlit Cloud
**Solution** :
- Réduire le nombre de bougies stockées (modifier `max_candles` dans `DataManager`)
- Utiliser un plan payant Streamlit Cloud pour plus de ressources

### Les indicateurs ne s'affichent pas
**Cause** : Pas assez de données ou erreur dans le code
**Solution** :
- Attendre que plus de bougies arrivent
- Vérifier les logs pour voir les erreurs Python
- Tester localement d'abord

## 🔄 Mises à Jour Futures

Pour mettre à jour l'application après modifications :

```bash
# Faire vos modifications
git add .
git commit -m "Description de vos changements"
git push

# Streamlit Cloud redéploie automatiquement !
```

## 📱 Partager l'Application

Une fois déployée, vous pouvez partager l'URL avec qui vous voulez :
- **URL publique** : `https://your-app-name.streamlit.app`
- Fonctionne sur mobile, tablette, desktop
- Pas besoin d'installation pour les utilisateurs

## 🎉 C'est Tout !

Votre application de trading est maintenant en ligne et accessible 24/7 ! 🚀

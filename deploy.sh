#!/bin/bash

# Script d'aide pour le déploiement GitHub

echo "🚀 Setup GitHub Repository"
echo ""
echo "Ce script va vous guider pour pusher sur GitHub"
echo ""

# Demander les infos
read -p "Entrez votre username GitHub: " username
read -p "Entrez le nom du repository (ex: tradingview-pro): " repo

# Construire l'URL
repo_url="https://github.com/$username/$repo.git"

echo ""
echo "📋 URL du repository: $repo_url"
echo ""
echo "✅ Étapes à suivre:"
echo ""
echo "1. Créez d'abord le repository sur GitHub:"
echo "   👉 https://github.com/new"
echo "   - Repository name: $repo"
echo "   - NE PAS cocher 'Initialize with README'"
echo ""
read -p "Appuyez sur ENTER quand le repository est créé..."

echo ""
echo "2. Configuration de la remote Git..."
git remote remove origin 2>/dev/null  # Supprimer si existe déjà
git remote add origin "$repo_url"
git branch -M main

echo ""
echo "3. Push vers GitHub..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SUCCESS! Code pushé sur GitHub"
    echo ""
    echo "📱 Prochaines étapes:"
    echo "1. Aller sur: https://share.streamlit.io/"
    echo "2. Se connecter avec GitHub"
    echo "3. Cliquer 'New app'"
    echo "4. Sélectionner: $username/$repo"
    echo "5. Branch: main"
    echo "6. Main file: app.py"
    echo "7. Cliquer 'Deploy!'"
    echo ""
    echo "🎉 Votre app sera live dans quelques minutes!"
else
    echo ""
    echo "❌ Erreur lors du push"
    echo "Vérifiez:"
    echo "- Que le repository existe sur GitHub"
    echo "- Vos credentials GitHub"
    echo "- Votre connexion internet"
fi

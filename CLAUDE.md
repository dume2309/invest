# Portfolio Tracker — Brief Claude Code

## Objectif
Web app de suivi de portefeuille personnel : ETF, actions (RKLB, SpaceX post-IPO), or physique.
Interface dark mode, données temps réel via yfinance, alertes prix, graphiques.

## Stack technique
- **Backend** : Python 3 + Flask + yfinance
- **Frontend** : HTML/CSS/JS vanilla — fichier unique `index.html`
- **Stockage** : `portfolio.json` (local, gitignored)
- **Graphiques** : Chart.js (CDN)

## Architecture fichiers
```
portfolio-tracker/
├── CLAUDE.md           ← ce fichier
├── app.py              ← serveur Flask + routes API
├── index.html          ← frontend complet (CSS + JS inline)
├── portfolio.json      ← données persistées (créé auto au 1er lancement)
├── requirements.txt    ← dépendances Python
└── .gitignore
```

## Routes API Flask (app.py)

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/portfolio` | Retourne toutes les positions |
| POST | `/api/portfolio` | Ajoute une position |
| DELETE | `/api/portfolio/<id>` | Supprime une position |
| GET | `/api/quote/<ticker>` | Cours actuel via yfinance |
| GET | `/api/history/<ticker>?period=1mo` | Historique cours (1mo/3mo/1y) |
| GET | `/api/refresh` | Rafraîchit tous les cours du portefeuille |
| GET | `/api/alerts` | Retourne les alertes déclenchées |
| POST | `/api/alerts` | Ajoute une alerte prix |
| DELETE | `/api/alerts/<id>` | Supprime une alerte |

## Structure portfolio.json
```json
{
  "positions": [
    {
      "id": "uuid",
      "ticker": "CW8.PA",
      "nom": "Amundi MSCI World",
      "type": "ETF",
      "quantite": 10,
      "prix_achat": 420.50,
      "date_achat": "2025-01-15",
      "devise": "EUR"
    }
  ],
  "alertes": [
    {
      "id": "uuid",
      "ticker": "RKLB",
      "seuil_haut": 110.0,
      "seuil_bas": 70.0,
      "actif": true
    }
  ]
}
```

## Portefeuille cible de l'utilisateur

### Stratégie globale
- Investisseur débutant, approche long terme (DCA mensuel)
- Enveloppe fiscale : **PEA** (à ne pas clôturer avant 5 ans)
- Objectif : croissance (ETF) + protection (or physique)

### Allocation cible
| Actif | Ticker | Type | % cible | Rôle |
|-------|--------|------|---------|------|
| Amundi MSCI World | `CW8.PA` | ETF | 50 % | Socle mondial (1 600 entreprises) |
| Amundi S&P 500 | `500.PA` | ETF | 30 % | Renforcement US |
| Amundi MSCI Emerging Asia | `AASI.PA` | ETF | 20 % | Croissance Asie (Inde, Chine, Corée...) |
| Or physique Godot & Fils | `GC=F` | Or | hors PEA | Couverture inflation / crise |
| Rocket Lab | `RKLB` | Action | satellite | Pari spatial long terme |
| SpaceX (post-IPO juin 2026) | TBD | Action | satellite | À ajouter dès cotation |

### Paramètres or physique
- Dépositaire : **Godot & Fils**
- Supports : lingotins + Napoléons 20F
- Saisie dans l'appli : en **grammes**
- Fiscalité : régime PV réelle (36,2 %) si factures conservées, forfait 11,5 % sinon
- Abattement : 5 %/an à partir de la 3e année, exonération totale à 22 ans

### Notes fiscales PEA
- Plafond versements : 150 000 €
- Après 5 ans : exonération IR sur PV (prélèvements sociaux 17,2 % restants)
- Retrait avant 5 ans = clôture PEA + flat tax 30 %

## Tickers Yahoo Finance — référence complète
| Actif | Ticker Yahoo | Devise |
|-------|-------------|--------|
| Or spot | `GC=F` | USD/once |
| EUR/USD | `EURUSD=X` | — |
| Amundi MSCI World | `CW8.PA` | EUR |
| Amundi S&P 500 | `500.PA` | EUR |
| Amundi MSCI Emerging Asia | `AASI.PA` | EUR |
| Amundi Emerging Markets | `AEEM.PA` | EUR |
| Rocket Lab | `RKLB` | USD |
| SpaceX (post-IPO) | TBD | USD |
| Nvidia | `NVDA` | USD |
| Palantir | `PLTR` | USD |
| Super Micro Computer | `SMCI` | USD |
| Arista Networks | `ANET` | USD |

## Fonctionnalités à implémenter (dans l'ordre)

### 1. Backend Flask (app.py)
- Chargement/sauvegarde portfolio.json
- Route `/api/quote/<ticker>` : prix actuel, variation jour %, devise
- Route `/api/history/<ticker>` : OHLCV sur période
- Route `/api/refresh` : mise à jour de toutes les positions en batch
- Gestion alertes : vérification seuils à chaque refresh
- Conversion devise auto si nécessaire (GC=F en USD → EUR)

### 2. Frontend (index.html)
**Design** : dark mode, palette charbon/or/vert-rouge, typographie financière nette.

**Sections UI :**
1. **Header** — valeur totale portefeuille, PV/MV globale, heure dernière MAJ
2. **Tableau positions** — colonnes : Ticker | Nom | Type | Qté | Prix achat | Cours actuel | Valeur | PV/MV€ | PV/MV% | Alerte
3. **Donut chart** — répartition par type (ETF / Actions / Or) et par ligne
4. **Line chart** — historique valeur portefeuille (1M / 3M / 1A)
5. **Panel alertes** — liste alertes actives, badge rouge/vert si seuil atteint
6. **Modal ajout position** — formulaire : ticker, nom, type, qté, prix achat, date

**Comportement :**
- Rafraîchissement auto toutes les 60 secondes
- Indicateur visuel de chargement pendant le fetch
- PV positif = vert, négatif = rouge
- Responsive (mobile-friendly)

### 3. Or physique — cas particulier
L'or peut être saisi en grammes ou en onces.
- 1 once troy = 31,1035 grammes
- Ticker : `GC=F` (prix en USD/once) → convertir en EUR/gramme pour affichage
- Exemple : 50g d'or → quantité = 50, unité = "grammes"

## Commandes utiles

```bash
# Installation
pip install flask yfinance flask-cors

# Lancement
python app.py
# → http://localhost:5000

# Test API
curl http://localhost:5000/api/quote/GC=F
curl http://localhost:5000/api/quote/CW8.PA
```

## Contraintes
- Code commenté en français
- Pas de clé API requise (yfinance est gratuit)
- portfolio.json dans .gitignore (données perso)
- Gestion des erreurs yfinance (ticker invalide, timeout réseau)
- Rate limiting yfinance : ne pas appeler plus de 1 req/seconde en batch

## Watchlist — actions à surveiller (pas encore achetées)
| Société | Ticker | Secteur | Statut |
|---------|--------|---------|--------|
| Rocket Lab | `RKLB` | Spatial | Priorité — surveiller point entrée |
| SpaceX | TBD | Spatial | IPO ciblée juin 2026 — attendre S-1 |
| Nvidia | `NVDA` | Infrastructure IA | Incontournable — surveiller |
| Palantir | `PLTR` | IA appliquée défense | Fort potentiel |
| Super Micro Computer | `SMCI` | Serveurs IA | Très volatil — prudence |
| Arista Networks | `ANET` | Réseau data centers IA | Solide, moins risqué |

L'appli doit afficher une section **Watchlist** séparée du portefeuille réel :
- Cours temps réel + variation jour %
- Pas de PV/MV (non acheté)
- Alertes prix configurables identiques au portefeuille
- Bouton "Ajouter au portefeuille" pour convertir quand on achète

"""
Portfolio Tracker — Backend Flask
Suivi ETF, actions, or physique via yfinance
"""
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import yfinance as yf
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# --- Config ---
BASE_DIR = Path(__file__).parent
PORTFOLIO_FILE = BASE_DIR / "portfolio.json"
ONCE_TROY_GRAMMES = 31.1035  # 1 once = 31,1035 g

app = Flask(__name__, static_folder=None)
CORS(app)

# Cache simple en mémoire pour limiter les appels yfinance (TTL 30s)
_quote_cache = {}
_CACHE_TTL = 30


# ---------------------------------------------------------------------------
# Persistance portfolio.json
# ---------------------------------------------------------------------------
def load_portfolio():
    """Charge le portfolio depuis le JSON, structure vide par défaut."""
    if not PORTFOLIO_FILE.exists():
        return {"positions": [], "alertes": [], "watchlist": []}
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Compat : ajoute clés manquantes
    data.setdefault("positions", [])
    data.setdefault("alertes", [])
    data.setdefault("watchlist", [])
    return data


def save_portfolio(data):
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# yfinance helpers
# ---------------------------------------------------------------------------
def fetch_quote(ticker):
    """
    Récupère cours actuel + variation jour pour un ticker.
    Retourne dict { ticker, price, previous_close, change, change_pct, currency, name }.
    Lève une exception si ticker invalide.
    """
    now = time.time()
    cached = _quote_cache.get(ticker)
    if cached and now - cached["_ts"] < _CACHE_TTL:
        return cached["data"]

    t = yf.Ticker(ticker)
    info = t.fast_info  # plus rapide que .info
    price = info.get("last_price")
    prev = info.get("previous_close")
    currency = info.get("currency") or "USD"

    if price is None or prev is None:
        # Fallback sur historique si fast_info incomplet
        hist = t.history(period="2d")
        if hist.empty:
            raise ValueError(f"Ticker introuvable: {ticker}")
        price = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price

    change = price - prev
    change_pct = (change / prev * 100) if prev else 0

    # Nom long si dispo
    name = ticker
    try:
        long_name = t.info.get("longName") or t.info.get("shortName")
        if long_name:
            name = long_name
    except Exception:
        pass

    data = {
        "ticker": ticker,
        "price": round(float(price), 4),
        "previous_close": round(float(prev), 4),
        "change": round(float(change), 4),
        "change_pct": round(float(change_pct), 2),
        "currency": currency,
        "name": name,
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    _quote_cache[ticker] = {"_ts": now, "data": data}
    return data


def fetch_history(ticker, period="1mo"):
    """Historique OHLCV — period: 1mo, 3mo, 6mo, 1y, 5y."""
    t = yf.Ticker(ticker)
    hist = t.history(period=period)
    if hist.empty:
        return []
    return [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "close": round(float(row["Close"]), 4),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
        }
        for idx, row in hist.iterrows()
    ]


def get_eur_usd_rate():
    """Taux EUR/USD courant (1 EUR = ? USD)."""
    try:
        q = fetch_quote("EURUSD=X")
        return q["price"]
    except Exception:
        return 1.08  # fallback raisonnable


# ---------------------------------------------------------------------------
# Calcul valorisation d'une position
# ---------------------------------------------------------------------------
def valorise_position(pos):
    """
    Ajoute à la position : cours actuel, valeur, PV/MV en €.
    Pour l'or : pos["quantite"] est en grammes, on convertit GC=F (USD/once) → EUR/g.
    """
    ticker = pos["ticker"]
    try:
        q = fetch_quote(ticker)
    except Exception as e:
        return {**pos, "error": str(e)}

    prix_actuel = q["price"]
    devise = q["currency"]

    # Cas spécial OR (GC=F = USD/once → conversion en EUR/g)
    if pos.get("type") == "Or" and ticker == "GC=F":
        eur_usd = get_eur_usd_rate()
        prix_eur_par_gramme = (prix_actuel / ONCE_TROY_GRAMMES) / eur_usd
        valeur_eur = prix_eur_par_gramme * pos["quantite"]
        cout_total = pos["prix_achat"] * pos["quantite"]  # prix_achat saisi en €/g
        pv_eur = valeur_eur - cout_total
        pv_pct = (pv_eur / cout_total * 100) if cout_total else 0
        return {
            **pos,
            "prix_actuel": round(prix_eur_par_gramme, 4),
            "valeur_eur": round(valeur_eur, 2),
            "pv_eur": round(pv_eur, 2),
            "pv_pct": round(pv_pct, 2),
            "change_pct_jour": q["change_pct"],
            "devise_cotation": "EUR/g",
            "name": q["name"],
        }

    # Cas standard (ETF, actions)
    valeur_devise = prix_actuel * pos["quantite"]
    cout_devise = pos["prix_achat"] * pos["quantite"]

    # Conversion en EUR
    if devise == "EUR":
        valeur_eur = valeur_devise
        cout_eur = cout_devise
    elif devise == "USD":
        eur_usd = get_eur_usd_rate()
        valeur_eur = valeur_devise / eur_usd
        cout_eur = cout_devise / eur_usd
    else:
        valeur_eur = valeur_devise
        cout_eur = cout_devise

    pv_eur = valeur_eur - cout_eur
    pv_pct = (pv_eur / cout_eur * 100) if cout_eur else 0

    return {
        **pos,
        "prix_actuel": round(prix_actuel, 4),
        "valeur_eur": round(valeur_eur, 2),
        "pv_eur": round(pv_eur, 2),
        "pv_pct": round(pv_pct, 2),
        "change_pct_jour": q["change_pct"],
        "devise_cotation": devise,
        "name": q["name"],
    }


def check_alertes(data):
    """Marque chaque alerte comme déclenchée si seuil franchi (au prix actuel)."""
    for a in data.get("alertes", []):
        if not a.get("actif", True):
            a["declenchee"] = False
            continue
        try:
            q = fetch_quote(a["ticker"])
            prix = q["price"]
            haut = a.get("seuil_haut")
            bas = a.get("seuil_bas")
            decl = False
            if haut is not None and prix >= haut:
                decl = True
            if bas is not None and prix <= bas:
                decl = True
            a["declenchee"] = decl
            a["prix_actuel"] = prix
        except Exception:
            a["declenchee"] = False


# ---------------------------------------------------------------------------
# Routes : frontend
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


# ---------------------------------------------------------------------------
# Routes : portfolio
# ---------------------------------------------------------------------------
@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    data = load_portfolio()
    positions_valo = [valorise_position(p) for p in data["positions"]]

    valeur_totale = sum(p.get("valeur_eur", 0) for p in positions_valo if "error" not in p)
    cout_total = sum(
        p["prix_achat"] * p["quantite"]
        if p.get("type") != "Or" and p.get("devise", "EUR") == "EUR"
        else (p.get("valeur_eur", 0) - p.get("pv_eur", 0))
        for p in positions_valo
        if "error" not in p
    )
    pv_total = valeur_totale - cout_total
    pv_pct = (pv_total / cout_total * 100) if cout_total else 0

    check_alertes(data)
    save_portfolio(data)  # persiste l'état des alertes

    return jsonify({
        "positions": positions_valo,
        "alertes": data["alertes"],
        "watchlist": data["watchlist"],
        "totaux": {
            "valeur_eur": round(valeur_totale, 2),
            "cout_eur": round(cout_total, 2),
            "pv_eur": round(pv_total, 2),
            "pv_pct": round(pv_pct, 2),
        },
        "ts": datetime.utcnow().isoformat() + "Z",
    })


@app.route("/api/portfolio", methods=["POST"])
def add_position():
    payload = request.get_json(force=True)
    required = ["ticker", "type", "quantite", "prix_achat"]
    if not all(k in payload for k in required):
        return jsonify({"error": "Champs requis: " + ", ".join(required)}), 400

    data = load_portfolio()
    pos = {
        "id": str(uuid.uuid4()),
        "ticker": payload["ticker"].upper().strip(),
        "nom": payload.get("nom", ""),
        "type": payload["type"],
        "quantite": float(payload["quantite"]),
        "prix_achat": float(payload["prix_achat"]),
        "date_achat": payload.get("date_achat", datetime.utcnow().strftime("%Y-%m-%d")),
        "devise": payload.get("devise", "EUR"),
    }
    data["positions"].append(pos)
    save_portfolio(data)
    return jsonify(pos), 201


@app.route("/api/portfolio/<pos_id>", methods=["DELETE"])
def delete_position(pos_id):
    data = load_portfolio()
    before = len(data["positions"])
    data["positions"] = [p for p in data["positions"] if p["id"] != pos_id]
    if len(data["positions"]) == before:
        return jsonify({"error": "Position introuvable"}), 404
    save_portfolio(data)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Routes : quotes
# ---------------------------------------------------------------------------
@app.route("/api/quote/<path:ticker>", methods=["GET"])
def quote(ticker):
    try:
        return jsonify(fetch_quote(ticker))
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/history/<path:ticker>", methods=["GET"])
def history(ticker):
    period = request.args.get("period", "1mo")
    try:
        return jsonify({"ticker": ticker, "period": period, "data": fetch_history(ticker, period)})
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/refresh", methods=["GET"])
def refresh():
    """Vide le cache et recharge tout."""
    _quote_cache.clear()
    return get_portfolio()


# ---------------------------------------------------------------------------
# Routes : alertes
# ---------------------------------------------------------------------------
@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    data = load_portfolio()
    check_alertes(data)
    save_portfolio(data)
    return jsonify(data["alertes"])


@app.route("/api/alerts", methods=["POST"])
def add_alert():
    payload = request.get_json(force=True)
    if "ticker" not in payload:
        return jsonify({"error": "ticker requis"}), 400
    data = load_portfolio()
    alerte = {
        "id": str(uuid.uuid4()),
        "ticker": payload["ticker"].upper().strip(),
        "seuil_haut": float(payload["seuil_haut"]) if payload.get("seuil_haut") not in (None, "") else None,
        "seuil_bas": float(payload["seuil_bas"]) if payload.get("seuil_bas") not in (None, "") else None,
        "actif": payload.get("actif", True),
        "declenchee": False,
    }
    data["alertes"].append(alerte)
    save_portfolio(data)
    return jsonify(alerte), 201


@app.route("/api/alerts/<alert_id>", methods=["DELETE"])
def delete_alert(alert_id):
    data = load_portfolio()
    before = len(data["alertes"])
    data["alertes"] = [a for a in data["alertes"] if a["id"] != alert_id]
    if len(data["alertes"]) == before:
        return jsonify({"error": "Alerte introuvable"}), 404
    save_portfolio(data)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Routes : watchlist
# ---------------------------------------------------------------------------
@app.route("/api/watchlist", methods=["GET"])
def get_watchlist():
    data = load_portfolio()
    enriched = []
    for w in data["watchlist"]:
        try:
            q = fetch_quote(w["ticker"])
            enriched.append({**w, **q})
        except Exception as e:
            enriched.append({**w, "error": str(e)})
    return jsonify(enriched)


@app.route("/api/watchlist", methods=["POST"])
def add_watchlist():
    payload = request.get_json(force=True)
    if "ticker" not in payload:
        return jsonify({"error": "ticker requis"}), 400
    data = load_portfolio()
    item = {
        "id": str(uuid.uuid4()),
        "ticker": payload["ticker"].upper().strip(),
        "nom": payload.get("nom", ""),
        "secteur": payload.get("secteur", ""),
        "note": payload.get("note", ""),
    }
    data["watchlist"].append(item)
    save_portfolio(data)
    return jsonify(item), 201


@app.route("/api/watchlist/<item_id>", methods=["DELETE"])
def delete_watchlist(item_id):
    data = load_portfolio()
    before = len(data["watchlist"])
    data["watchlist"] = [w for w in data["watchlist"] if w["id"] != item_id]
    if len(data["watchlist"]) == before:
        return jsonify({"error": "Item introuvable"}), 404
    save_portfolio(data)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Bootstrap : remplit watchlist par défaut au 1er lancement
# ---------------------------------------------------------------------------
def bootstrap_watchlist_default():
    data = load_portfolio()
    if data["watchlist"]:
        return
    defaults = [
        {"ticker": "RKLB", "nom": "Rocket Lab", "secteur": "Spatial", "note": "Priorité — surveiller point entrée"},
        {"ticker": "NVDA", "nom": "Nvidia", "secteur": "Infrastructure IA", "note": "Incontournable"},
        {"ticker": "PLTR", "nom": "Palantir", "secteur": "IA défense", "note": "Fort potentiel"},
        {"ticker": "SMCI", "nom": "Super Micro Computer", "secteur": "Serveurs IA", "note": "Très volatil"},
        {"ticker": "ANET", "nom": "Arista Networks", "secteur": "Réseau IA", "note": "Solide"},
    ]
    for d in defaults:
        d["id"] = str(uuid.uuid4())
        data["watchlist"].append(d)
    save_portfolio(data)


if __name__ == "__main__":
    if not PORTFOLIO_FILE.exists():
        save_portfolio({"positions": [], "alertes": [], "watchlist": []})
    bootstrap_watchlist_default()
    print("Portfolio Tracker -> http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)

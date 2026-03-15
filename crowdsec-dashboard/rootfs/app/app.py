#!/usr/bin/env python3
"""CrowdSec Dashboard - Flask Backend Proxy"""

import os
import json
import time
import logging
import requests
from flask import Flask, jsonify, request, Response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Read config from HA options file or environment
def load_config():
    options_file = "/data/options.json"
    if os.path.exists(options_file):
        with open(options_file) as f:
            opts = json.load(f)
            logger.info(f"Loaded config from {options_file}")
            return opts
    # Fallback to environment variables
    return {
        "crowdsec_url":      os.environ.get("CROWDSEC_URL",      "http://424ccef4-crowdsec:8080"),
        "machine_id":        os.environ.get("MACHINE_ID",        "crowdsec-dashboard"),
        "machine_password":  os.environ.get("MACHINE_PASSWORD",  "dashboard123"),
        "bouncer_api_key":   os.environ.get("BOUNCER_API_KEY",   "kbf9zXlr+TmLjIx5hDippRfw5NdvziY1tyjlsej5u5g"),
    }

config = load_config()
CROWDSEC_URL     = config.get("crowdsec_url",     "http://424ccef4-crowdsec:8080")
MACHINE_ID       = config.get("machine_id",       "crowdsec-dashboard")
MACHINE_PASSWORD = config.get("machine_password", "dashboard123")
BOUNCER_API_KEY  = config.get("bouncer_api_key",  "kbf9zXlr+TmLjIx5hDippRfw5NdvziY1tyjlsej5u5g")

logger.info(f"CrowdSec LAPI: {CROWDSEC_URL}")
logger.info(f"Bouncer Key: {'set' if BOUNCER_API_KEY else 'NOT SET!'}")

app = Flask(__name__)

# HA Ingress middleware
class ReverseProxied:
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_INGRESS_PATH', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ.get('PATH_INFO', '')
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]
        return self.app(environ, start_response)

app.wsgi_app = ReverseProxied(app.wsgi_app)

# JWT Token cache
_token = None
_token_expiry = 0

def get_jwt_token():
    global _token, _token_expiry
    now = time.time()
    if _token and now < _token_expiry - 60:
        return _token
    logger.info("Fetching new JWT token...")
    resp = requests.post(
        f"{CROWDSEC_URL}/v1/watchers/login",
        json={"machine_id": MACHINE_ID, "password": MACHINE_PASSWORD},
        timeout=10
    )
    resp.raise_for_status()
    _token = resp.json().get("token")
    _token_expiry = now + (23 * 3600)
    logger.info("JWT token obtained")
    return _token

def bouncer_headers():
    return {"X-Api-Key": BOUNCER_API_KEY, "Accept": "application/json"}

def jwt_headers():
    return {"Authorization": f"Bearer {get_jwt_token()}", "Accept": "application/json"}

# ─── ROUTES ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    ingress_path = request.headers.get('X-Ingress-Path', '')
    with open('/app/index.html', 'r') as f:
        content = f.read()
    content = content.replace('__INGRESS_PATH__', ingress_path)
    return Response(content, mimetype='text/html')

@app.route("/api/health")
def health():
    try:
        get_jwt_token()
        return jsonify({"status": "ok", "crowdsec_url": CROWDSEC_URL})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 503

@app.route("/api/decisions")
def decisions():
    try:
        params = {k: request.args[k] for k in ("ip","range","scenario") if k in request.args}
        resp = requests.get(f"{CROWDSEC_URL}/v1/decisions", headers=bouncer_headers(), params=params or None, timeout=15)
        if resp.status_code == 404:
            return jsonify([])
        resp.raise_for_status()
        return jsonify(resp.json() or [])
    except Exception as e:
        logger.error(f"Error fetching decisions: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts")
def alerts():
    try:
        params = {"limit": request.args.get("limit", "100")}
        params.update({k: request.args[k] for k in ("ip","scenario") if k in request.args})
        resp = requests.get(f"{CROWDSEC_URL}/v1/alerts", headers=jwt_headers(), params=params, timeout=15)
        if resp.status_code == 404:
            return jsonify([])
        resp.raise_for_status()
        return jsonify(resp.json() or [])
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/decisions/<int:decision_id>", methods=["DELETE"])
def delete_decision(decision_id):
    try:
        resp = requests.delete(f"{CROWDSEC_URL}/v1/decisions/{decision_id}", headers=jwt_headers(), timeout=15)
        resp.raise_for_status()
        return jsonify({"success": True, "id": decision_id})
    except Exception as e:
        logger.error(f"Error deleting decision {decision_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/decisions/all", methods=["DELETE"])
def delete_all():
    try:
        resp = requests.delete(f"{CROWDSEC_URL}/v1/decisions", headers=jwt_headers(), timeout=15)
        resp.raise_for_status()
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error deleting all: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/metrics")
def metrics():
    try:
        d = requests.get(f"{CROWDSEC_URL}/v1/decisions", headers=bouncer_headers(), timeout=15)
        decisions_data = d.json() if d.status_code == 200 else []
        a = requests.get(f"{CROWDSEC_URL}/v1/alerts", headers=jwt_headers(), params={"limit":"500"}, timeout=15)
        alerts_data = a.json() if a.status_code == 200 else []

        by_type, by_origin, by_scenario = {}, {}, {}
        for dec in (decisions_data or []):
            by_type[dec.get("type","ban")] = by_type.get(dec.get("type","ban"), 0) + 1
            origin = dec.get("origin","unknown")
            if origin == "crowdsec": origin = "CAPI 🌐"
            elif origin == "cscli": origin = "Manual"
            by_origin[origin] = by_origin.get(origin, 0) + 1
            s = dec.get("scenario","unknown")
            by_scenario[s] = by_scenario.get(s, 0) + 1

        return jsonify({
            "total_decisions": len(decisions_data or []),
            "total_alerts": len(alerts_data or []),
            "by_type": by_type,
            "by_origin": by_origin,
            "by_scenario": dict(sorted(by_scenario.items(), key=lambda x: x[1], reverse=True)[:10]),
        })
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    logger.info("Starting CrowdSec Dashboard on port 8099")
    app.run(host="0.0.0.0", port=8099, debug=False)

#!/usr/bin/env python3
"""CrowdSec Dashboard - Flask Backend Proxy"""

import os
import json
import time
import logging
import requests
from flask import Flask, jsonify, request, send_file, Response

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# HA Ingress: forward the ingress path so Flask routes correctly
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

# Config from environment
CROWDSEC_URL     = os.environ.get("CROWDSEC_URL",       "http://424ccef4-crowdsec:8080")
MACHINE_ID       = os.environ.get("MACHINE_ID",         "crowdsec-dashboard")
MACHINE_PASSWORD = os.environ.get("MACHINE_PASSWORD",   "dashboard123")
BOUNCER_API_KEY  = os.environ.get("BOUNCER_API_KEY",    "")

# JWT Token cache (for delete operations)
_token = None
_token_expiry = 0

def get_jwt_token():
    """Get a valid JWT token for write operations (delete)."""
    global _token, _token_expiry
    now = time.time()
    if _token and now < _token_expiry - 60:
        return _token
    logger.info("Fetching new JWT token from CrowdSec LAPI...")
    resp = requests.post(
        f"{CROWDSEC_URL}/v1/watchers/login",
        json={"machine_id": MACHINE_ID, "password": MACHINE_PASSWORD},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    _token = data.get("token")
    _token_expiry = now + (23 * 3600)
    logger.info("JWT token obtained successfully")
    return _token

def bouncer_headers():
    """Headers for read operations using Bouncer API key."""
    return {"X-Api-Key": BOUNCER_API_KEY, "Accept": "application/json"}

def jwt_headers():
    """Headers for write operations using JWT token."""
    token = get_jwt_token()
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

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
        # Test bouncer key
        r = requests.get(f"{CROWDSEC_URL}/v1/decisions", headers=bouncer_headers(), timeout=5)
        bouncer_ok = r.status_code in (200, 404)
        # Test JWT
        get_jwt_token()
        return jsonify({"status": "ok", "bouncer": bouncer_ok, "jwt": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 503

@app.route("/api/decisions")
def decisions():
    try:
        params = {}
        for key in ("ip", "range", "scenario"):
            if request.args.get(key):
                params[key] = request.args.get(key)
        resp = requests.get(
            f"{CROWDSEC_URL}/v1/decisions",
            headers=bouncer_headers(),
            params=params or None,
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        return jsonify(data if data else [])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return jsonify([])
        logger.error(f"HTTP error fetching decisions: {e}")
        return jsonify({"error": str(e)}), e.response.status_code
    except Exception as e:
        logger.error(f"Error fetching decisions: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts")
def alerts():
    try:
        params = {"limit": request.args.get("limit", "100")}
        for key in ("ip", "scenario"):
            if request.args.get(key):
                params[key] = request.args.get(key)
        resp = requests.get(
            f"{CROWDSEC_URL}/v1/alerts",
            headers=jwt_headers(),
            params=params,
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
        return jsonify(data if data else [])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return jsonify([])
        logger.error(f"HTTP error fetching alerts: {e}")
        return jsonify({"error": str(e)}), e.response.status_code
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/decisions/<int:decision_id>", methods=["DELETE"])
def delete_decision(decision_id):
    try:
        resp = requests.delete(
            f"{CROWDSEC_URL}/v1/decisions/{decision_id}",
            headers=jwt_headers(),
            timeout=15
        )
        resp.raise_for_status()
        logger.info(f"Deleted decision {decision_id}")
        return jsonify({"success": True, "id": decision_id})
    except Exception as e:
        logger.error(f"Error deleting decision {decision_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/decisions/all", methods=["DELETE"])
def delete_all_decisions():
    try:
        resp = requests.delete(
            f"{CROWDSEC_URL}/v1/decisions",
            headers=jwt_headers(),
            timeout=15
        )
        resp.raise_for_status()
        logger.info("Deleted all decisions")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error deleting all decisions: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/metrics")
def metrics():
    try:
        decisions_resp = requests.get(
            f"{CROWDSEC_URL}/v1/decisions",
            headers=bouncer_headers(),
            timeout=15
        )
        decisions_data = decisions_resp.json() if decisions_resp.status_code == 200 else []

        alerts_resp = requests.get(
            f"{CROWDSEC_URL}/v1/alerts",
            headers=jwt_headers(),
            params={"limit": "500"},
            timeout=15
        )
        alerts_data = alerts_resp.json() if alerts_resp.status_code == 200 else []

        by_type, by_origin, by_scenario = {}, {}, {}
        for d in (decisions_data or []):
            dtype = d.get("type", "ban")
            by_type[dtype] = by_type.get(dtype, 0) + 1
            origin = d.get("origin", "unknown")
            if origin == "crowdsec": origin = "CAPI 🌐"
            elif origin == "cscli": origin = "Manual"
            by_origin[origin] = by_origin.get(origin, 0) + 1
            scenario = d.get("scenario", "unknown")
            by_scenario[scenario] = by_scenario.get(scenario, 0) + 1

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
    logger.info(f"Starting CrowdSec Dashboard on port 8099")
    logger.info(f"CrowdSec LAPI: {CROWDSEC_URL}")
    logger.info(f"Machine ID: {MACHINE_ID}")
    logger.info(f"Bouncer Key: {'set' if BOUNCER_API_KEY else 'NOT SET!'}")
    app.run(host="0.0.0.0", port=8099, debug=False)

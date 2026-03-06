#!/usr/bin/env python3
"""CrowdSec Dashboard - Flask Backend Proxy"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_file, abort

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class ReverseProxied:
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        script_name = environ.get("HTTP_X_INGRESS_PATH", "")
        if script_name:
            environ["SCRIPT_NAME"] = script_name
            path_info = environ.get("PATH_INFO", "")
            if path_info.startswith(script_name):
                environ["PATH_INFO"] = path_info[len(script_name):]
        return self.app(environ, start_response)

app.wsgi_app = ReverseProxied(app.wsgi_app)

# Config from environment (set by HA addon options)
CROWDSEC_URL = os.environ.get("CROWDSEC_URL", "http://424ccef4-crowdsec:8080")
MACHINE_ID = os.environ.get("MACHINE_ID", "crowdsec-dashboard")
MACHINE_PASSWORD = os.environ.get("MACHINE_PASSWORD", "dashboard123")

# Token cache
_token = None
_token_expiry = 0

def get_token():
    """Get a valid JWT token, refreshing if needed."""
    global _token, _token_expiry
    now = time.time()
    
    if _token and now < _token_expiry - 60:
        return _token
    
    logger.info("Fetching new JWT token from CrowdSec LAPI...")
    try:
        resp = requests.post(
            f"{CROWDSEC_URL}/v1/watchers/login",
            json={"machine_id": MACHINE_ID, "password": MACHINE_PASSWORD},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        _token = data.get("token")
        # Tokens typically valid for 24h, refresh after 23h
        _token_expiry = now + (23 * 3600)
        logger.info("JWT token obtained successfully")
        return _token
    except Exception as e:
        logger.error(f"Failed to get JWT token: {e}")
        raise

def crowdsec_get(path, params=None):
    """Make authenticated GET request to CrowdSec LAPI."""
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(
        f"{CROWDSEC_URL}{path}",
        headers=headers,
        params=params,
        timeout=15
    )
    resp.raise_for_status()
    return resp.json()

def crowdsec_delete(path):
    """Make authenticated DELETE request to CrowdSec LAPI."""
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.delete(
        f"{CROWDSEC_URL}{path}",
        headers=headers,
        timeout=15
    )
    resp.raise_for_status()
    return resp.status_code

# ─── API Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_file("/app/index.html")

@app.route("/api/health")
def health():
    try:
        token = get_token()
        return jsonify({"status": "ok", "crowdsec_url": CROWDSEC_URL, "token": "valid"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 503

@app.route("/api/decisions")
def decisions():
    """Get all active decisions (bans)."""
    try:
        params = {}
        if request.args.get("ip"):
            params["ip"] = request.args.get("ip")
        if request.args.get("range"):
            params["range"] = request.args.get("range")
        if request.args.get("scenario"):
            params["scenario"] = request.args.get("scenario")
        
        data = crowdsec_get("/v1/decisions", params if params else None)
        if data is None:
            data = []
        return jsonify(data)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return jsonify([])
        logger.error(f"HTTP error fetching decisions: {e}")
        return jsonify({"error": str(e)}), e.response.status_code
    except Exception as e:
        logger.error(f"Error fetching decisions: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/decisions/stream")
def decisions_stream():
    """Get decisions stream (startup=true for all decisions)."""
    try:
        data = crowdsec_get("/v1/decisions/stream", {"startup": "true"})
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error fetching decisions stream: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts")
def alerts():
    """Get all alerts."""
    try:
        params = {}
        if request.args.get("ip"):
            params["ip"] = request.args.get("ip")
        if request.args.get("scenario"):
            params["scenario"] = request.args.get("scenario")
        if request.args.get("limit"):
            params["limit"] = request.args.get("limit", "100")
        
        data = crowdsec_get("/v1/alerts", params if params else {"limit": "100"})
        if data is None:
            data = []
        return jsonify(data)
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
    """Delete a specific decision by ID."""
    try:
        status = crowdsec_delete(f"/v1/decisions/{decision_id}")
        logger.info(f"Deleted decision {decision_id}, status: {status}")
        return jsonify({"success": True, "id": decision_id})
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error deleting decision {decision_id}: {e}")
        return jsonify({"error": str(e)}), e.response.status_code
    except Exception as e:
        logger.error(f"Error deleting decision {decision_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/decisions/all", methods=["DELETE"])
def delete_all_decisions():
    """Delete all active decisions."""
    try:
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.delete(
            f"{CROWDSEC_URL}/v1/decisions",
            headers=headers,
            timeout=15
        )
        resp.raise_for_status()
        logger.info("Deleted all decisions")
        return jsonify({"success": True, "message": "All decisions deleted"})
    except Exception as e:
        logger.error(f"Error deleting all decisions: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/metrics")
def metrics():
    """Aggregate stats for the dashboard."""
    try:
        decisions_data = crowdsec_get("/v1/decisions", None) or []
        alerts_data = crowdsec_get("/v1/alerts", {"limit": "500"}) or []
        
        # Aggregate by type
        by_type = {}
        by_country = {}
        by_scenario = {}
        
        for d in decisions_data:
            dtype = d.get("type", "ban")
            by_type[dtype] = by_type.get(dtype, 0) + 1
            
            country = d.get("origin", "unknown")
            if country == "crowdsec":
                country = "CAPI 🌐"
            elif country == "cscli":
                country = "Manual"
            by_country[country] = by_country.get(country, 0) + 1
            
            scenario = d.get("scenario", "unknown")
            by_scenario[scenario] = by_scenario.get(scenario, 0) + 1
        
        return jsonify({
            "total_decisions": len(decisions_data),
            "total_alerts": len(alerts_data),
            "by_type": by_type,
            "by_origin": by_country,
            "by_scenario": dict(sorted(by_scenario.items(), key=lambda x: x[1], reverse=True)[:10]),
        })
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    logger.info(f"Starting CrowdSec Dashboard on port 8099")
    logger.info(f"CrowdSec LAPI: {CROWDSEC_URL}")
    logger.info(f"Machine ID: {MACHINE_ID}")
    app.run(host="0.0.0.0", port=8099, debug=False)

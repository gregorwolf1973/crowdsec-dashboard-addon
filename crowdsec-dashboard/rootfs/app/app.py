#!/usr/bin/env python3
"""CrowdSec Dashboard - Flask Backend Proxy."""

import os
import json
import time
import logging
import requests
from flask import Flask, jsonify, request, Response

# ─── Config ──────────────────────────────────────────────────────────────────

def load_config():
    options_file = "/data/options.json"
    if os.path.exists(options_file):
        try:
            with open(options_file) as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Could not read {options_file}: {e}")
    return {
        "crowdsec_url":     os.environ.get("CROWDSEC_URL",     "http://424ccef4-crowdsec:8080"),
        "machine_id":       os.environ.get("MACHINE_ID",       "crowdsec-dashboard"),
        "machine_password": os.environ.get("MACHINE_PASSWORD", ""),
        "bouncer_api_key":  os.environ.get("BOUNCER_API_KEY",  ""),
        "log_level":        os.environ.get("LOG_LEVEL",        "info"),
    }

config = load_config()
CROWDSEC_URL     = config.get("crowdsec_url",     "http://424ccef4-crowdsec:8080").rstrip("/")
MACHINE_ID       = config.get("machine_id",       "crowdsec-dashboard")
MACHINE_PASSWORD = config.get("machine_password", "")
BOUNCER_API_KEY  = config.get("bouncer_api_key",  "")
LOG_LEVEL        = config.get("log_level",        "info").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

logger.info(f"CrowdSec LAPI: {CROWDSEC_URL}")
logger.info(f"Machine ID: {MACHINE_ID}")
logger.info(f"Machine password: {'set' if MACHINE_PASSWORD else 'NOT SET'}")
logger.info(f"Bouncer key: {'set' if BOUNCER_API_KEY else 'NOT SET'}")

app = Flask(__name__)

# ─── HA Ingress middleware ─────────────────────────────────────────────────────

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

# ─── Auth helpers ──────────────────────────────────────────────────────────────

_token = None
_token_expiry = 0

def get_jwt_token(force=False):
    global _token, _token_expiry
    now = time.time()
    if not force and _token and now < _token_expiry - 60:
        return _token
    logger.info("Fetching new JWT token...")
    resp = requests.post(
        f"{CROWDSEC_URL}/v1/watchers/login",
        json={"machine_id": MACHINE_ID, "password": MACHINE_PASSWORD},
        timeout=10,
    )
    resp.raise_for_status()
    _token = resp.json().get("token")
    _token_expiry = now + (23 * 3600)
    logger.info("JWT token obtained")
    return _token

def bouncer_headers():
    return {"X-Api-Key": BOUNCER_API_KEY, "Accept": "application/json"}

def jwt_headers(force=False):
    return {"Authorization": f"Bearer {get_jwt_token(force=force)}", "Accept": "application/json"}

def cs_jwt(method, path, **kwargs):
    """Call the LAPI with JWT auth. On 401, refresh the token once and retry.
    Raises requests.HTTPError on non-OK final responses."""
    kwargs.setdefault("timeout", 15)
    url = f"{CROWDSEC_URL}{path}"
    resp = requests.request(method, url, headers=jwt_headers(), **kwargs)
    if resp.status_code == 401:
        logger.warning(f"JWT 401 on {method} {path}, refreshing token and retrying...")
        resp = requests.request(method, url, headers=jwt_headers(force=True), **kwargs)
    return resp

def cs_bouncer(method, path, **kwargs):
    """Call the LAPI with bouncer-key auth."""
    kwargs.setdefault("timeout", 15)
    return requests.request(method, f"{CROWDSEC_URL}{path}", headers=bouncer_headers(), **kwargs)

def err(e, msg):
    logger.error(f"{msg}: {e}")
    return jsonify({"error": str(e)}), 500

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    ingress_path = request.headers.get("X-Ingress-Path", "")
    with open("/app/index.html") as f:
        content = f.read()
    return Response(content.replace("__INGRESS_PATH__", ingress_path), mimetype="text/html")

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
        params = {k: request.args[k] for k in ("ip", "range", "scenario") if k in request.args}
        resp = cs_bouncer("GET", "/v1/decisions", params=params or None)
        if resp.status_code == 404:
            return jsonify([])
        resp.raise_for_status()
        return jsonify(resp.json() or [])
    except Exception as e:
        return err(e, "Error fetching decisions")

@app.route("/api/alerts")
def alerts():
    try:
        params = {"limit": request.args.get("limit", "500")}
        params.update({k: request.args[k] for k in ("ip", "scenario") if k in request.args})
        resp = cs_jwt("GET", "/v1/alerts", params=params)
        if resp.status_code == 404:
            return jsonify([])
        resp.raise_for_status()
        return jsonify(resp.json() or [])
    except Exception as e:
        return err(e, "Error fetching alerts")

@app.route("/api/metrics")
def metrics():
    try:
        d = cs_bouncer("GET", "/v1/decisions")
        decisions_data = d.json() if d.status_code == 200 else []
        a = cs_jwt("GET", "/v1/alerts", params={"limit": "500"})
        alerts_data = a.json() if a.status_code == 200 else []

        by_type, by_origin, by_scenario = {}, {}, {}
        for dec in (decisions_data or []):
            t = dec.get("type", "ban")
            by_type[t] = by_type.get(t, 0) + 1
            o = dec.get("origin", "unknown")
            by_origin[o] = by_origin.get(o, 0) + 1
            s = dec.get("scenario", "unknown")
            by_scenario[s] = by_scenario.get(s, 0) + 1

        return jsonify({
            "total_decisions": len(decisions_data or []),
            "total_alerts": len(alerts_data or []),
            "by_type": by_type,
            "by_origin": by_origin,
            "by_scenario": dict(sorted(by_scenario.items(), key=lambda x: x[1], reverse=True)[:10]),
        })
    except Exception as e:
        return err(e, "Error fetching metrics")

# ─── Delete endpoints (GET variants because HA Ingress blocks DELETE/POST) ─────

@app.route("/api/decisions/<int:decision_id>/remove", methods=["GET"])
def remove_decision(decision_id):
    try:
        resp = cs_jwt("DELETE", f"/v1/decisions/{decision_id}")
        resp.raise_for_status()
        logger.info(f"Removed decision {decision_id}")
        return jsonify({"success": True, "id": decision_id})
    except Exception as e:
        return err(e, f"Error removing decision {decision_id}")

@app.route("/api/decisions/remove-all", methods=["GET"])
def remove_all_decisions():
    try:
        resp = cs_jwt("DELETE", "/v1/decisions")
        resp.raise_for_status()
        logger.info("Removed all decisions")
        return jsonify({"success": True})
    except Exception as e:
        return err(e, "Error removing all decisions")

@app.route("/api/decisions/local/remove-all", methods=["GET"])
def remove_local_decisions():
    """Delete only local decisions (origin crowdsec or cscli)."""
    try:
        resp = cs_bouncer("GET", "/v1/decisions")
        resp.raise_for_status()
        local = [d for d in (resp.json() or []) if d.get("origin") in ("crowdsec", "cscli")]
        deleted = 0
        for d in local:
            r = cs_jwt("DELETE", f"/v1/decisions/{d['id']}", timeout=10)
            if r.status_code in (200, 204):
                deleted += 1
            else:
                logger.warning(f"Could not delete decision {d['id']}: HTTP {r.status_code}")
        logger.info(f"Deleted {deleted} local decisions")
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        return err(e, "Error removing local decisions")

@app.route("/api/decisions/ip/<ip>/remove", methods=["GET"])
def remove_by_ip(ip):
    try:
        resp = cs_jwt("DELETE", "/v1/decisions", params={"ip": ip})
        resp.raise_for_status()
        logger.info(f"Deleted decisions for IP {ip}")
        return jsonify({"success": True, "ip": ip})
    except Exception as e:
        return err(e, f"Error removing IP {ip}")

if __name__ == "__main__":
    logger.info("Starting CrowdSec Dashboard on port 8099")
    app.run(host="0.0.0.0", port=8099, debug=False)

#!/usr/bin/with-contenv bashio

# API Key aus Add-on Konfiguration lesen
API_KEY=$(bashio::config 'crowdsec_api_key')
CROWDSEC_URL=$(bashio::config 'crowdsec_url')

# Config in JS-Datei schreiben damit Frontend sie laden kann
cat > /var/www/html/config.js << JSEOF
window.CROWDSEC_API = "/api";
window.CROWDSEC_KEY = "${API_KEY}";
JSEOF

bashio::log.info "CrowdSec Dashboard gestartet auf Port 8099"
nginx -g "daemon off;"

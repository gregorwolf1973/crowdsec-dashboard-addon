#!/usr/bin/with-contenv bashio

API_KEY=$(bashio::config 'crowdsec_api_key')
CROWDSEC_URL=$(bashio::config 'crowdsec_url')

sed -i "s|CROWDSEC_API_KEY_PLACEHOLDER|${API_KEY}|" /etc/nginx/nginx.conf
sed -i "s|CROWDSEC_URL_PLACEHOLDER|${CROWDSEC_URL}|" /etc/nginx/nginx.conf

bashio::log.info "CrowdSec Dashboard gestartet auf Port 8099"
nginx -g "daemon off;"

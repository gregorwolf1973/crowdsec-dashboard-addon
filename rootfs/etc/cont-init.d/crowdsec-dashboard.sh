#!/usr/bin/with-contenv bashio

bashio::log.info "=== CrowdSec Dashboard Startup ==="
bashio::log.info "Checking Python dependencies..."

if ! python3 -c "import flask, requests" 2>/dev/null; then
    bashio::log.warning "Installing missing Python packages..."
    pip3 install --no-cache-dir flask requests --quiet
fi

bashio::log.info "Dependencies OK"
bashio::log.info "Dashboard will be available via HA Ingress"

#!/bin/bash
# Aktuellen Stand des Add-ons nach GitHub pushen.
# Die Version wird aus config.yaml gelesen, gepusht wird nach main.
set -e

cd "$(dirname "$0")"

VERSION="$(sed -n 's/^version:[[:space:]]*"\{0,1\}\([^"]*\)"\{0,1\}[[:space:]]*$/\1/p' config.yaml)"
if [ -z "$VERSION" ]; then
  echo "Version konnte nicht aus config.yaml gelesen werden." >&2
  exit 1
fi

git add .
if git diff --cached --quiet; then
  echo "Keine Änderungen zum Committen."
else
  git commit -m "v${VERSION}"
fi
git push origin main

echo "Fertig. Danach in HA: ha supervisor reload && ha apps update 54b27e84_crowdsec_dashboard"

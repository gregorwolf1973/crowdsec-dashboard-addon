#!/bin/bash
# v1.4.0 nach GitHub pushen.
# Ausführen im lokalen Klon von crowdsec-dashboard-addon,
# nachdem die vier Dateien aus dem ZIP hineinkopiert wurden.
set -e
git add crowdsec-dashboard/
git commit -m "v1.4.0: haerten - Secrets raus, JWT-Retry ueberall, config:rw entfernt, parseDuration-Fix"
git push origin master
echo "Fertig. Danach in HA: ha supervisor reload && ha apps update 54b27e84_crowdsec_dashboard"

FROM python:3.11-alpine

# Install dependencies
RUN pip3 install --no-cache-dir flask requests

# Copy application files
COPY rootfs/app /app
COPY rootfs/etc /etc

# Make scripts executable
RUN chmod a+x /etc/services.d/crowdsec-dashboard/run \
    && chmod a+x /etc/services.d/crowdsec-dashboard/finish \
    && chmod a+x /etc/cont-init.d/crowdsec-dashboard.sh

WORKDIR /app
EXPOSE 8099

CMD ["python3", "/app/app.py"]

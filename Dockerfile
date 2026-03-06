ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python dependencies
RUN pip3 install --no-cache-dir flask requests

# Copy application files
COPY rootfs /

# Make scripts executable
RUN chmod a+x /etc/services.d/crowdsec-dashboard/run
RUN chmod a+x /etc/services.d/crowdsec-dashboard/finish
RUN chmod a+x /etc/cont-init.d/crowdsec-dashboard.sh

EXPOSE 8099

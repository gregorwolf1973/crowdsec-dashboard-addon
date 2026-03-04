ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache nginx

COPY src/frontend/ /var/www/html/
COPY nginx.conf /tmp/nginx-crowdsec.conf
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8099
CMD ["/run.sh"]

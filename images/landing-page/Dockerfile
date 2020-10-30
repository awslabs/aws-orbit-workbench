FROM nginx:1.19.2-alpine

COPY build /usr/share/nginx/html
COPY docker-entrypoint.sh /
RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]

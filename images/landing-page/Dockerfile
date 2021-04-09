FROM public.ecr.aws/v3o4w1g6/aws-orbit-workbench/nginx:1.19.4-alpine

COPY build /usr/share/nginx/html
COPY docker-entrypoint.sh /
RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]

FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
RUN apk add --no-cache gettext
EXPOSE 80
CMD ["/bin/sh", "-c", "envsubst '$BACKEND_URL' < /usr/share/nginx/html/index.html > /tmp/index.html && mv /tmp/index.html /usr/share/nginx/html/index.html && nginx -g 'daemon off;'"]

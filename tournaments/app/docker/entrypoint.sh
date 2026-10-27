#!/bin/sh
set -e

envsubst '${API_URL}' < /usr/share/nginx/html/env-config.js > /tmp/env-config.js
cp /tmp/env-config.js /usr/share/nginx/html/env-config.js

exec nginx -g 'daemon off;'

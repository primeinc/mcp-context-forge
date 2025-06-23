#!/bin/sh

# Replace environment variables in nginx config and HTML files
envsubst '${API_BASE_URL}' < /etc/nginx/conf.d/default.conf > /tmp/default.conf
mv /tmp/default.conf /etc/nginx/conf.d/default.conf

# Inject environment variables into JavaScript config
cat > /usr/share/nginx/html/config.js << EOF
window.APP_CONFIG = {
    AZURE_CLIENT_ID: '${AZURE_CLIENT_ID}',
    AZURE_TENANT_ID: '${AZURE_TENANT_ID}',
    AZURE_AUTHORITY_HOST: '${AZURE_AUTHORITY_HOST}',
    API_BASE_URL: '${API_BASE_URL}',
    WEB_REDIRECT_URI: '${WEB_REDIRECT_URI}'
};
EOF
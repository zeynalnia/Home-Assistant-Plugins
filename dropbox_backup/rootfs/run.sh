#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Dropbox HA Backup addon..."

# Auto-install companion integration into Home Assistant
INTEGRATION_SRC="/app/custom_components/dropbox_ha_backup"
INTEGRATION_DST="/config/custom_components/dropbox_ha_backup"

if [ -d "$INTEGRATION_SRC" ]; then
    mkdir -p /config/custom_components
    if [ -d "$INTEGRATION_DST" ]; then
        SRC_VERSION=$(jq -r '.version' "$INTEGRATION_SRC/manifest.json")
        DST_VERSION=$(jq -r '.version' "$INTEGRATION_DST/manifest.json" 2>/dev/null || echo "0")
        if [ "$SRC_VERSION" != "$DST_VERSION" ]; then
            bashio::log.info "Updating companion integration ($DST_VERSION -> $SRC_VERSION)..."
            rm -rf "$INTEGRATION_DST"
            cp -r "$INTEGRATION_SRC" "$INTEGRATION_DST"
            bashio::log.info "Companion integration updated. Restart HA Core to activate."
        else
            bashio::log.info "Companion integration is up to date ($SRC_VERSION)."
        fi
    else
        bashio::log.info "Installing companion integration..."
        cp -r "$INTEGRATION_SRC" "$INTEGRATION_DST"
        bashio::log.info "Companion integration installed. Restart HA Core to activate."
    fi
fi

# Start the Python web server in the background with unbuffered output
# (-u ensures logs appear immediately in the addon Log tab)
python3 -u /app/run.py 2>&1 &
PYTHON_PID=$!

# Wait briefly for the web server to start
sleep 2

# Read stdin in the foreground (receives hassio.app_stdin input)
bashio::log.info "Listening for stdin commands..."
while true; do
    read -r input || break
    bashio::log.debug "Raw stdin input: ${input}"
    input=$(echo "$input" | jq -r . 2>/dev/null || echo "$input")

    if [ "$input" = "trigger" ]; then
        bashio::log.info "Received stdin trigger command"
        curl -s -X POST http://127.0.0.1:8099/trigger \
            -H "Accept: application/json" || true
    else
        bashio::log.warning "Unknown stdin command: ${input}"
    fi
done

# If stdin closes, wait for Python to finish
wait $PYTHON_PID

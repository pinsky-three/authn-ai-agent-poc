#!/bin/sh
set -e

# Substitute environment variables in envoy config
envsubst < /etc/envoy/envoy.yaml.template > /etc/envoy/envoy.yaml

# Start Envoy
exec /usr/local/bin/envoy -c /etc/envoy/envoy.yaml

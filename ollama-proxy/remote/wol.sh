#!/bin/bash
# Persist WOL across reboots
# Deploy to: /etc/networkd-dispatcher/configuring.d/wol.sh
ethtool -s eno1 wol g

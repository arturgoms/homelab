#!/bin/bash

AVAILABLE=$(df / | awk 'NR==2 {print $4}')
if [ $AVAILABLE -lt 20480 ]; then
  echo "Warning: Root filesystem has less than 20G available space. Available: ${AVAILABLE}K" | message --content "Warning: Root filesystem has less than 20G available space. Available: ${AVAILABLE}K" --channel "telegram" --chat_id "$TELEGRAM_CHAT_ID"
fi
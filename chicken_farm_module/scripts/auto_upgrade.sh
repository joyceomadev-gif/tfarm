#!/bin/bash
# ==============================================================================
# Taghini Farm Management - Automated Migration & Upgrade Script
# ==============================================================================
set -e

DB_NAME="${1:-Taghini_live}"
CONF_FILE="/etc/odoo/odoo.conf"

echo "=================================================================="
echo " Starting Taghini Farm Management Auto-Upgrade"
echo " Database: $DB_NAME"
echo " Config  : $CONF_FILE"
echo "=================================================================="

# 1. Run Python Migration Pre-Flight Script
if [ -f "/mnt/odoo-source/chicken_farm_addons/chicken_farm_module/scripts/migrate_taghini_database.py" ]; then
    echo ">> Running pre-flight database migration and schema repair..."
    python3 /mnt/odoo-source/chicken_farm_addons/chicken_farm_module/scripts/migrate_taghini_database.py -d "$DB_NAME"
fi

# 2. Trigger Odoo Module Upgrade
echo ">> Running Odoo module upgrade (-u chicken_farm_module)..."
odoo -c "$CONF_FILE" -d "$DB_NAME" -u chicken_farm_module --stop-after-init

echo "=================================================================="
echo " Taghini Farm Management upgrade completed successfully!"
echo "=================================================================="

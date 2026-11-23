# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pre-migration script for chicken_farm_module v1.6.2:
    Validates schema integrity and ensures all required columns exist.
    """
    _logger.info("===========================================================")
    _logger.info("[chicken_farm_module] Starting Pre-Migration to v1.6.2...")
    _logger.info("[chicken_farm_module] Installed DB Version: %s", version)
    _logger.info("===========================================================")

    # Ensure all stored columns exist
    cr.execute("""
        ALTER TABLE taghini_daily_log 
            ADD COLUMN IF NOT EXISTS feed_product_id integer REFERENCES product_product(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS farm_id integer REFERENCES taghini_farm(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS warehouse_id integer REFERENCES stock_warehouse(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS name varchar,
            ADD COLUMN IF NOT EXISTS has_escalated_remarks boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS vet_notified boolean DEFAULT false;

        ALTER TABLE taghini_flock 
            ADD COLUMN IF NOT EXISTS warehouse_id integer REFERENCES stock_warehouse(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS pen_model_id integer REFERENCES taghini_pen(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS batch_id integer REFERENCES taghini_chicken_batch(id) ON DELETE SET NULL;
    """)

    _logger.info("[chicken_farm_module] Pre-Migration to v1.6.2 completed successfully.")

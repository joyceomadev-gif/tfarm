# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Post-migration script for chicken_farm_module v1.6.2:
    Final record verification, sequence integrity, and metric updates.
    """
    _logger.info("===========================================================")
    _logger.info("[chicken_farm_module] Starting Post-Migration to v1.6.2...")
    _logger.info("[chicken_farm_module] Installed DB Version: %s", version)
    _logger.info("===========================================================")

    # Ensure all daily logs have names assigned
    cr.execute("""
        UPDATE taghini_daily_log
        SET name = 'LOG/' || TO_CHAR(date, 'YYYY') || '/' || LPAD(id::text, 5, '0')
        WHERE name IS NULL OR name = 'New' OR name = '';
    """)

    # Refresh flock metrics (updating stored fields)
    cr.execute("""
        UPDATE taghini_flock f
        SET current_birds = f.initial_birds - COALESCE(sub.dead, 0) - COALESCE(sub.harvested, 0),
            total_feed_bags = COALESCE(sub.bags, 0),
            unrecorded_birds = 0
        FROM (
            SELECT flock_id,
                   SUM(COALESCE(mortality, 0)) AS dead,
                   SUM(COALESCE(harvested_qty, 0)) AS harvested,
                   SUM(COALESCE(feed_consumed_bags, 0)) AS bags
            FROM taghini_daily_log
            GROUP BY flock_id
        ) sub
        WHERE f.id = sub.flock_id;
    """)

    _logger.info("[chicken_farm_module] Post-Migration to v1.6.2 completed successfully.")

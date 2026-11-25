# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Post-migration script for chicken_farm_module v1.6.3:
    1. Backfill maturity_age_days = 42 on existing broiler standards.
    2. Backfill destination_location_id on existing bagging headers from lines or farm.
    3. Backfill storage_class = 'frozen' and is_within_spec on existing bagging QA rows.
    4. Backfill sequential harvest/production traceability fields on existing bagging records.
    """
    _logger.info("===========================================================")
    _logger.info("[chicken_farm_module] Starting Post-Migration to v1.6.3...")
    _logger.info("[chicken_farm_module] Installed DB Version: %s", version)
    _logger.info("===========================================================")

    # 1. Backfill maturity_age_days on existing broiler standards
    cr.execute("""
        UPDATE taghini_farm_standard
        SET maturity_age_days = 42
        WHERE standard_type = 'broiler'
          AND (maturity_age_days IS NULL OR maturity_age_days = 0);
    """)

    # 2. Backfill header destination_location_id from legacy bagging line column if present
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'taghini_abattoir_bagging_line'
          AND column_name = 'destination_location_id';
    """)
    if cr.fetchone():
        cr.execute("""
            UPDATE taghini_abattoir_bagging b
            SET destination_location_id = sub.loc_id
            FROM (
                SELECT DISTINCT ON (bagging_id) bagging_id, destination_location_id AS loc_id
                FROM taghini_abattoir_bagging_line
                WHERE destination_location_id IS NOT NULL
                ORDER BY bagging_id, id
            ) sub
            WHERE b.id = sub.bagging_id
              AND b.destination_location_id IS NULL;
        """)

    # Fallback: fill remaining bagging destination_location_id from farm freezer/storage
    cr.execute("""
        UPDATE taghini_abattoir_bagging b
        SET destination_location_id = COALESCE(f.freezer_location_id, f.storage_location_id)
        FROM taghini_farm f
        WHERE b.farm_id = f.id
          AND b.destination_location_id IS NULL
          AND COALESCE(f.freezer_location_id, f.storage_location_id) IS NOT NULL;
    """)

    # 3. Backfill storage_class and recompute is_within_spec on existing QA temperature rows
    cr.execute("""
        UPDATE taghini_abattoir_bagging_qa
        SET storage_class = 'frozen',
            is_within_spec = (temperature_celsius <= -18.0)
        WHERE storage_class IS NULL;
    """)

    # 4. Backfill sequential harvest & production traceability fields on existing bagging records
    cr.execute("""
        UPDATE taghini_abattoir_bagging b
        SET harvest_id = ab.harvest_id,
            production_output_weight_kg = ab.total_output_weight_kg,
            packaging_supervisor_id = ab.packaging_supervisor_id,
            qa_shopfloor_id = ab.qa_shopfloor_id,
            flock_id = h.flock_id,
            breeder_flock_id = h.breeder_flock_id,
            pen_id = h.pen_id,
            birds_received = h.birds_received,
            total_live_weight = h.total_live_weight
        FROM taghini_abattoir_batch ab
        LEFT JOIN taghini_harvest h ON h.id = ab.harvest_id
        WHERE b.batch_id = ab.id
          AND b.harvest_id IS NULL;
    """)

    _logger.info("[chicken_farm_module] Post-Migration to v1.6.3 completed successfully.")

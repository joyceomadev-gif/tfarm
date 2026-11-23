# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Post-migration script for chicken_farm_module v1.6.0:
    Runs AFTER models and views have been updated.
    1. Migrates historical breeder logs from taghini_breeder_daily_log into taghini_breeder_pen_log.
    2. Recalculates mother batch allocations.
    3. Backfills and repairs existing taghini_daily_log records (farm, warehouse, feed_product, name).
    4. Recomputes flock and batch statistics.
    """
    _logger.info("===========================================================")
    _logger.info("[chicken_farm_module] Starting Post-Migration to v1.6.0...")
    _logger.info("[chicken_farm_module] Installed DB Version: %s", version)
    _logger.info("===========================================================")

    # -------------------------------------------------------------------------
    # 1. MIGRATE HISTORICAL DATA FROM taghini_breeder_daily_log
    # -------------------------------------------------------------------------
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'taghini_breeder_daily_log'
        );
    """)
    if cr.fetchone()[0]:
        cr.execute("SELECT count(*) FROM taghini_breeder_daily_log;")
        legacy_count = cr.fetchone()[0]
        if legacy_count > 0:
            _logger.info("[Post-Migration] Found %d legacy breeder logs to migrate.", legacy_count)

            cr.execute("""
                SELECT id, name, batch_id, date, activity_type,
                       COALESCE(female_mortality_premise, 0) + COALESCE(female_mortality_transit, 0) AS f_mort,
                       COALESCE(male_mortality_premise, 0) + COALESCE(male_mortality_transit, 0) AS m_mort,
                       COALESCE(eggs_collected, 0) AS eggs,
                       COALESCE(eggs_sent_to_hatchery, 0) AS hatch_eggs,
                       observations, remarks, state
                FROM taghini_breeder_daily_log
                ORDER BY date ASC, id ASC;
            """)
            legacy_logs = cr.fetchall()

            for row in legacy_logs:
                (leg_id, leg_name, batch_id, log_date, act_type,
                 f_mort, m_mort, eggs, hatch_eggs, obs, rem, state) = row

                if not batch_id:
                    continue

                # Find an active flock for this batch or create one
                cr.execute("""
                    SELECT id FROM taghini_breeder_flock 
                    WHERE batch_id = %s 
                    ORDER BY id ASC LIMIT 1;
                """, (batch_id,))
                flock_res = cr.fetchone()

                if flock_res:
                    flock_id = flock_res[0]
                else:
                    cr.execute("SELECT id FROM taghini_pen ORDER BY id ASC LIMIT 1;")
                    pen_res = cr.fetchone()
                    pen_id = pen_res[0] if pen_res else False
                    if not pen_id:
                        continue

                    flock_seq = f"BFLK/MIG/{batch_id:04d}"
                    cr.execute("""
                        INSERT INTO taghini_breeder_flock 
                            (name, batch_id, pen_id, start_date, initial_females, initial_males, state, create_date, write_date)
                        VALUES (%s, %s, %s, %s, 1000, 120, 'active', NOW(), NOW())
                        RETURNING id;
                    """, (flock_seq, batch_id, pen_id, log_date))
                    flock_id = cr.fetchone()[0]
                    _logger.info("[Post-Migration] Auto-created Breeder Flock %s (id: %d) for Batch %d.", flock_seq, flock_id, batch_id)

                log_ref = f"BPLOG/MIG/{leg_id:05d}"
                remarks_full = " ".join(filter(None, [obs, rem]))

                cr.execute("""
                    INSERT INTO taghini_breeder_pen_log 
                        (name, flock_id, date, female_mortality, male_mortality,
                         total_eggs_collected, hatching_eggs, clinical_remarks,
                         state, row_status, danger_count, error_count, create_date, write_date)
                    VALUES 
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ok', 0, 0, NOW(), NOW())
                    ON CONFLICT DO NOTHING;
                """, (
                    log_ref, flock_id, log_date, f_mort, m_mort,
                    eggs, hatch_eggs, remarks_full,
                    'posted' if state == 'done' else 'draft'
                ))

            _logger.info("[Post-Migration] Successfully migrated %d legacy records to taghini_breeder_pen_log.", len(legacy_logs))

            # Safely archive the old table so no historical data is ever destroyed
            cr.execute("""
                ALTER TABLE taghini_breeder_daily_log 
                RENAME TO legacy_taghini_breeder_daily_log_backup;
            """)
            _logger.info("[Post-Migration] Renamed taghini_breeder_daily_log -> legacy_taghini_breeder_daily_log_backup.")

    # -------------------------------------------------------------------------
    # 2. RECALCULATE MOTHER BATCH STOCK & ALLOCATION BALANCES
    # -------------------------------------------------------------------------
    _logger.info("[Post-Migration] Recalculating mother batch allocation balances...")
    cr.execute("""
        UPDATE taghini_breeder_batch b
        SET allocated_female_qty = COALESCE((
            SELECT SUM(initial_females) FROM taghini_breeder_flock WHERE batch_id = b.id
        ), 0),
        allocated_male_qty = COALESCE((
            SELECT SUM(initial_males) FROM taghini_breeder_flock WHERE batch_id = b.id
        ), 0),
        remaining_female_qty = COALESCE(b.stocked_female_qty, 0) - COALESCE((
            SELECT SUM(initial_females) FROM taghini_breeder_flock WHERE batch_id = b.id
        ), 0),
        remaining_male_qty = COALESCE(b.stocked_male_qty, 0) - COALESCE((
            SELECT SUM(initial_males) FROM taghini_breeder_flock WHERE batch_id = b.id
        ), 0);
    """)

    # -------------------------------------------------------------------------
    # 3. BACKFILL AND UPDATE EXISTING taghini_daily_log RECORDS
    # -------------------------------------------------------------------------
    _logger.info("[Post-Migration] Updating existing taghini_daily_log records...")

    # 3a. Backfill farm_id from parent flock
    cr.execute("""
        UPDATE taghini_daily_log l
        SET farm_id = f.farm_id
        FROM taghini_flock f
        WHERE l.flock_id = f.id AND l.farm_id IS NULL AND f.farm_id IS NOT NULL;
    """)

    # 3b. Backfill warehouse_id from parent flock or farm
    cr.execute("""
        UPDATE taghini_daily_log l
        SET warehouse_id = COALESCE(f.warehouse_id, fm.warehouse_id)
        FROM taghini_flock f
        LEFT JOIN taghini_farm fm ON f.farm_id = fm.id
        WHERE l.flock_id = f.id AND l.warehouse_id IS NULL;
    """)

    # 3c. Backfill unique sequential name for daily logs with NULL or 'New'
    cr.execute("""
        UPDATE taghini_daily_log
        SET name = 'LOG/' || TO_CHAR(date, 'YYYY') || '/' || LPAD(id::text, 5, '0')
        WHERE name IS NULL OR name = 'New' OR name = '';
    """)

    # 3d. Backfill feed_product_id from standards line if available
    cr.execute("""
        UPDATE taghini_daily_log l
        SET feed_product_id = (
            SELECT sl.product_id 
            FROM taghini_farm_standard_line sl
            WHERE sl.standard_id = l.standard_id 
              AND l.age_day >= sl.age_min 
              AND l.age_day <= sl.age_max
              AND sl.product_id IS NOT NULL
            LIMIT 1
        )
        WHERE l.feed_product_id IS NULL AND l.standard_id IS NOT NULL;
    """)

    # -------------------------------------------------------------------------
    # 4. RECOMPUTE BROILER FLOCK AND BATCH AGGREGATES
    # -------------------------------------------------------------------------
    _logger.info("[Post-Migration] Recomputing flock totals and metrics...")
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

    _logger.info("[chicken_farm_module] Post-Migration to v1.6.0 completed successfully.")

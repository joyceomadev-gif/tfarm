#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Taghini Database Migration & Auto-Upgrade Utility
==================================================
Safely prepares, migrates, and upgrades any Taghini Odoo database (live, staging, or test)
to match the current module version (v1.6.2), resolving schema conflicts and updating records.

Key Operations:
  1. Fail-Safe Column Pre-Creation: Ensures feed_product_id, farm_id, warehouse_id exist before ORM queries.
  2. Resolves NULL foreign keys (taghini_pen.farm_id, standard_type, farm_type).
  3. JSONB-safe cleanup of obsolete views referencing deleted models.
  4. Migrates historical breeder logs to taghini_breeder_pen_log with archive preservation.
  5. Recalculates mother batch allocation balances and flock metrics.
  6. Backfills existing taghini_daily_log records (farm, warehouse, feed product, sequential names).
  7. Triggers Odoo module upgrade if requested (--upgrade).

Usage:
  # Inspect only (Dry Run):
  python3 scripts/migrate_taghini_database.py -d Taghini_live --dry-run

  # Apply migrations:
  python3 scripts/migrate_taghini_database.py -d Taghini_live

  # Apply migrations AND immediately run Odoo module upgrade:
  python3 scripts/migrate_taghini_database.py -d Taghini_live --upgrade
"""
import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_logger = logging.getLogger("taghini.migration")


def run_migration(dbname, dry_run=False, trigger_upgrade=False):
    print("=================================================================")
    print(f" Taghini Farm DB Migration & Repair Utility")
    print(f" Target Database : {dbname}")
    print(f" Execution Mode  : {'DRY RUN (No changes will be saved)' if dry_run else 'APPLY MIGRATIONS'}")
    print(f" Auto-Upgrade    : {'YES (Will upgrade chicken_farm_module)' if trigger_upgrade else 'NO'}")
    print("=================================================================")

    try:
        import odoo
        from odoo.modules.registry import Registry
    except ImportError:
        print("ERROR: Odoo library not found. Run this script inside the Odoo container or virtual environment.")
        sys.exit(1)

    try:
        reg = Registry(dbname)
    except Exception as e:
        print(f"ERROR: Could not open database registry '{dbname}': {e}")
        sys.exit(1)

    with reg.cursor() as cr:
        # -------------------------------------------------------------
        # STEP 0: Fail-Safe Column Pre-Creation
        # -------------------------------------------------------------
        print("\n[Step 0] Ensuring table schema columns exist...")
        if not dry_run:
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

                ALTER TABLE taghini_pen 
                    ADD COLUMN IF NOT EXISTS capacity integer DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS farm_id integer REFERENCES taghini_farm(id) ON DELETE SET NULL;
            """)
            print("  -> Schema columns verified/created.")
        else:
            print("  -> Would verify/add missing schema columns.")

        # -------------------------------------------------------------
        # STEP 1: Fix NULL farm_id on taghini_pen
        # -------------------------------------------------------------
        cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'taghini_pen');")
        if cr.fetchone()[0]:
            cr.execute("SELECT count(*) FROM taghini_pen WHERE farm_id IS NULL;")
            null_pens = cr.fetchone()[0]
            print(f"\n[Step 1] taghini_pen rows with NULL farm_id: {null_pens}")
            if null_pens > 0:
                if not dry_run:
                    cr.execute("SELECT id FROM taghini_farm ORDER BY id ASC LIMIT 1;")
                    f_row = cr.fetchone()
                    if f_row:
                        default_farm = f_row[0]
                    else:
                        cr.execute("SELECT id FROM res_company ORDER BY id ASC LIMIT 1;")
                        c_id = cr.fetchone()[0]
                        cr.execute("SELECT id FROM stock_warehouse WHERE company_id = %s ORDER BY id ASC LIMIT 1;", (c_id,))
                        wh_row = cr.fetchone()
                        if not wh_row:
                            cr.execute("SELECT id FROM stock_warehouse ORDER BY id ASC LIMIT 1;")
                            wh_row = cr.fetchone()
                        
                        if wh_row:
                            wh_id = wh_row[0]
                            cr.execute("""
                                INSERT INTO taghini_farm (name, code, company_id, warehouse_id, farm_type, create_date, write_date)
                                VALUES ('Main Farm Site', 'FRM/MAIN', %s, %s, 'mixed', NOW(), NOW())
                                RETURNING id;
                            """, (c_id, wh_id))
                            default_farm = cr.fetchone()[0]
                        else:
                            cr.execute("ALTER TABLE taghini_farm ALTER COLUMN warehouse_id DROP NOT NULL;")
                            cr.execute("""
                                INSERT INTO taghini_farm (name, code, company_id, farm_type, create_date, write_date)
                                VALUES ('Main Farm Site', 'FRM/MAIN', %s, 'mixed', NOW(), NOW())
                                RETURNING id;
                            """, (c_id,))
                            default_farm = cr.fetchone()[0]
                    cr.execute("UPDATE taghini_pen SET farm_id = %s WHERE farm_id IS NULL;", (default_farm,))
                    print(f"  -> FIXED: Assigned {null_pens} pens to default farm_id {default_farm}.")
                else:
                    print(f"  -> WOULD FIX: Would backfill {null_pens} pens to a default farm.")

        # -------------------------------------------------------------
        # STEP 2: Fix NULL standard_type on taghini_farm_standard
        # -------------------------------------------------------------
        cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'taghini_farm_standard' AND column_name = 'standard_type'
            );
        """)
        if cr.fetchone()[0]:
            cr.execute("SELECT count(*) FROM taghini_farm_standard WHERE standard_type IS NULL;")
            null_stds = cr.fetchone()[0]
            print(f"\n[Step 2] taghini_farm_standard rows with NULL standard_type: {null_stds}")
            if null_stds > 0:
                if not dry_run:
                    cr.execute("UPDATE taghini_farm_standard SET standard_type = 'broiler' WHERE standard_type IS NULL;")
                    print(f"  -> FIXED: Defaulted {null_stds} standards to 'broiler'.")
                else:
                    print(f"  -> WOULD FIX: Would default {null_stds} standards to 'broiler'.")

        # -------------------------------------------------------------
        # STEP 3: Fix NULL farm_type on taghini_farm
        # -------------------------------------------------------------
        cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'taghini_farm' AND column_name = 'farm_type'
            );
        """)
        if cr.fetchone()[0]:
            cr.execute("SELECT count(*) FROM taghini_farm WHERE farm_type IS NULL;")
            null_farms = cr.fetchone()[0]
            print(f"\n[Step 3] taghini_farm rows with NULL farm_type: {null_farms}")
            if null_farms > 0:
                if not dry_run:
                    cr.execute("UPDATE taghini_farm SET farm_type = 'broiler' WHERE farm_type IS NULL;")
                    print(f"  -> FIXED: Defaulted {null_farms} farms to 'broiler'.")
                else:
                    print(f"  -> WOULD FIX: Would default {null_farms} farms to 'broiler'.")

        # -------------------------------------------------------------
        # STEP 4: Clean up obsolete security rules & views (JSONB Safe)
        # -------------------------------------------------------------
        cr.execute("""
            SELECT count(*) FROM ir_rule 
            WHERE model_id IN (SELECT id FROM ir_model WHERE model = 'taghini.breeder.daily.log');
        """)
        stale_rules = cr.fetchone()[0]
        print(f"\n[Step 4] Stale security rules for deleted model: {stale_rules}")
        if stale_rules > 0:
            if not dry_run:
                cr.execute("DELETE FROM ir_rule WHERE model_id IN (SELECT id FROM ir_model WHERE model = 'taghini.breeder.daily.log');")
                cr.execute("DELETE FROM ir_model_access WHERE model_id IN (SELECT id FROM ir_model WHERE model = 'taghini.breeder.daily.log');")
                cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.model' AND name = 'model_taghini_breeder_daily_log';")
                print(f"  -> FIXED: Purged {stale_rules} obsolete security rules and model references.")
            else:
                print(f"  -> WOULD FIX: Would purge {stale_rules} obsolete security rules.")

        # Clean views safely with PostgreSQL jsonb cast
        if not dry_run:
            cr.execute("""
                DELETE FROM ir_ui_view 
                WHERE model = 'taghini.breeder.daily.log'
                   OR arch_db::text LIKE '%taghini.breeder.daily.log%';
            """)
            print("  -> Obsolete legacy views cleaned safely.")

        # -------------------------------------------------------------
        # STEP 5: Migrate data from taghini_breeder_daily_log
        # -------------------------------------------------------------
        cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'taghini_breeder_daily_log');")
        if cr.fetchone()[0]:
            cr.execute("SELECT count(*) FROM taghini_breeder_daily_log;")
            legacy_count = cr.fetchone()[0]
            print(f"\n[Step 5] Legacy taghini_breeder_daily_log records found: {legacy_count}")
            if legacy_count > 0:
                if not dry_run:
                    cr.execute("""
                        SELECT id, name, batch_id, date,
                               COALESCE(female_mortality_premise, 0) + COALESCE(female_mortality_transit, 0) AS f_mort,
                               COALESCE(male_mortality_premise, 0) + COALESCE(male_mortality_transit, 0) AS m_mort,
                               COALESCE(eggs_collected, 0) AS eggs,
                               COALESCE(eggs_sent_to_hatchery, 0) AS hatch_eggs,
                               observations, remarks, state
                        FROM taghini_breeder_daily_log
                        ORDER BY date ASC, id ASC;
                    """)
                    logs_to_migrate = cr.fetchall()
                    migrated = 0
                    for row in logs_to_migrate:
                        (leg_id, leg_name, b_id, l_date, f_m, m_m, eg, h_eg, obs, rem, st) = row
                        if not b_id:
                            continue

                        cr.execute("SELECT id FROM taghini_breeder_flock WHERE batch_id = %s LIMIT 1;", (b_id,))
                        f_res = cr.fetchone()
                        if f_res:
                            flk_id = f_res[0]
                        else:
                            cr.execute("SELECT id FROM taghini_pen ORDER BY id ASC LIMIT 1;")
                            p_row = cr.fetchone()
                            pen_id = p_row[0] if p_row else False
                            if not pen_id:
                                continue
                            flk_name = f"BFLK/MIG/{b_id:04d}"
                            cr.execute("""
                                INSERT INTO taghini_breeder_flock 
                                    (name, batch_id, pen_id, start_date, initial_females, initial_males, state, create_date, write_date)
                                VALUES (%s, %s, %s, %s, 1000, 120, 'active', NOW(), NOW())
                                RETURNING id;
                            """, (flk_name, b_id, pen_id, l_date))
                            flk_id = cr.fetchone()[0]

                        new_ref = f"BPLOG/MIG/{leg_id:05d}"
                        notes = " ".join(filter(None, [obs, rem]))
                        cr.execute("""
                            INSERT INTO taghini_breeder_pen_log 
                                (name, flock_id, date, female_mortality, male_mortality,
                                 total_eggs_collected, hatching_eggs, clinical_remarks,
                                 state, row_status, danger_count, error_count, create_date, write_date)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ok', 0, 0, NOW(), NOW())
                            ON CONFLICT DO NOTHING;
                        """, (new_ref, flk_id, l_date, f_m, m_m, eg, h_eg, notes, 'posted' if st == 'done' else 'draft'))
                        migrated += 1

                    cr.execute("ALTER TABLE taghini_breeder_daily_log RENAME TO legacy_taghini_breeder_daily_log_backup;")
                    print(f"  -> FIXED: Migrated {migrated} records to taghini_breeder_pen_log.")
                    print(f"  -> ARCHIVED: Renamed taghini_breeder_daily_log -> legacy_taghini_breeder_daily_log_backup.")
                else:
                    print(f"  -> WOULD FIX: Would migrate {legacy_count} records to taghini_breeder_pen_log.")
        else:
            print("\n[Step 5] Legacy taghini_breeder_daily_log: already migrated.")

        # -------------------------------------------------------------
        # STEP 6: Backfill & Update taghini_daily_log Records
        # -------------------------------------------------------------
        print("\n[Step 6] Updating and repairing taghini_daily_log records...")
        if not dry_run:
            cr.execute("""
                UPDATE taghini_daily_log l
                SET farm_id = f.farm_id
                FROM taghini_flock f
                WHERE l.flock_id = f.id AND l.farm_id IS NULL AND f.farm_id IS NOT NULL;

                UPDATE taghini_daily_log l
                SET warehouse_id = COALESCE(f.warehouse_id, fm.warehouse_id)
                FROM taghini_flock f
                LEFT JOIN taghini_farm fm ON f.farm_id = fm.id
                WHERE l.flock_id = f.id AND l.warehouse_id IS NULL;

                UPDATE taghini_daily_log
                SET name = 'LOG/' || TO_CHAR(date, 'YYYY') || '/' || LPAD(id::text, 5, '0')
                WHERE name IS NULL OR name = 'New' OR name = '';

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
            print("  -> taghini_daily_log records repaired (farm, warehouse, feed_product, name).")
        else:
            print("  -> Would repair taghini_daily_log records.")

        # -------------------------------------------------------------
        # STEP 7: Recalculate Mother Batch Allocation Balances
        # -------------------------------------------------------------
        cr.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'taghini_breeder_batch');")
        if cr.fetchone()[0]:
            print("\n[Step 7] Recalculating Mother Batch allocation balances...")
            if not dry_run:
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
                print("  -> Recalculated Mother Batch allocations.")
            else:
                print("  -> Would recalculate Mother Batch allocations.")

        # Commit or Rollback
        if dry_run:
            cr.rollback()
            print("\n>>> DRY RUN COMPLETED: No changes were committed to the database.")
            return
        else:
            cr.commit()
            print("\n>>> ALL MIGRATIONS APPLIED AND COMMITTED SUCCESSFULLY!")

    # -------------------------------------------------------------
    # OPTIONAL: Trigger Odoo Module Upgrade
    # -------------------------------------------------------------
    if trigger_upgrade:
        print("\n=================================================================")
        print(" Triggering Odoo Module Upgrade for 'chicken_farm_module'...")
        print("=================================================================")
        with reg.cursor() as cr:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            mod = env['ir.module.module'].search([('name', '=', 'chicken_farm_module')], limit=1)
            if mod:
                print(f"Current module version in DB: {mod.latest_version}, state: {mod.state}")
                mod.button_immediate_upgrade()
                cr.commit()
                print(f"Successfully upgraded to version: {mod.latest_version} (state: {mod.state})")
            else:
                print("ERROR: chicken_farm_module not found in ir_module_module.")


def main():
    parser = argparse.ArgumentParser(description="Taghini DB Migration & Auto-Upgrade Utility")
    parser.add_argument("-d", "--dbname", required=True, help="Database name (e.g. Taghini_live)")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without committing changes")
    parser.add_argument("--upgrade", action="store_true", help="Immediately run Odoo module upgrade after migration")
    args = parser.parse_args()
    run_migration(args.dbname, dry_run=args.dry_run, trigger_upgrade=args.upgrade)


if __name__ == '__main__':
    main()

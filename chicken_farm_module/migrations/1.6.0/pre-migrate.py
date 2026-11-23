# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pre-migration script for chicken_farm_module v1.6.0:
    Runs BEFORE models and XML files are loaded into PostgreSQL.
    Pre-creates missing stored columns, cleans up legacy constraints,
    fixes NULL foreign keys, and prevents schema conflicts.
    """
    _logger.info("===========================================================")
    _logger.info("[chicken_farm_module] Starting Pre-Migration to v1.6.0...")
    _logger.info("[chicken_farm_module] Installed DB Version: %s", version)
    _logger.info("===========================================================")

    # -------------------------------------------------------------------------
    # 0. PRE-CREATE NEW STORED COLUMNS SO ORM QUERIES NEVER THROW UndefinedColumn
    # -------------------------------------------------------------------------
    _logger.info("[Pre-Migration] Ensuring all required table columns exist...")
    cr.execute("""
        -- taghini_daily_log columns
        ALTER TABLE taghini_daily_log 
            ADD COLUMN IF NOT EXISTS feed_product_id integer REFERENCES product_product(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS farm_id integer REFERENCES taghini_farm(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS warehouse_id integer REFERENCES stock_warehouse(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS name varchar,
            ADD COLUMN IF NOT EXISTS has_escalated_remarks boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS vet_notified boolean DEFAULT false;

        -- taghini_flock columns
        ALTER TABLE taghini_flock 
            ADD COLUMN IF NOT EXISTS warehouse_id integer REFERENCES stock_warehouse(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS pen_model_id integer REFERENCES taghini_pen(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS batch_id integer REFERENCES taghini_chicken_batch(id) ON DELETE SET NULL;

        -- taghini_pen columns
        ALTER TABLE taghini_pen 
            ADD COLUMN IF NOT EXISTS capacity integer DEFAULT 0,
            ADD COLUMN IF NOT EXISTS farm_id integer REFERENCES taghini_farm(id) ON DELETE SET NULL;
    """)

    # -------------------------------------------------------------------------
    # 1. FIX NULL farm_id ON taghini_pen BEFORE NOT NULL CONSTRAINT IS ENFORCED
    # -------------------------------------------------------------------------
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'taghini_pen'
        );
    """)
    if cr.fetchone()[0]:
        cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'taghini_pen' AND column_name = 'farm_id'
            );
        """)
        if cr.fetchone()[0]:
            cr.execute("SELECT count(*) FROM taghini_pen WHERE farm_id IS NULL;")
            null_count = cr.fetchone()[0]
            if null_count > 0:
                _logger.warning("[Pre-Migration] Found %d pens with NULL farm_id. Backfilling...", null_count)
                # Find or create a default farm
                cr.execute("SELECT id FROM taghini_farm ORDER BY id ASC LIMIT 1;")
                farm_row = cr.fetchone()
                if farm_row:
                    default_farm_id = farm_row[0]
                else:
                    cr.execute("SELECT id FROM res_company ORDER BY id ASC LIMIT 1;")
                    comp_id = cr.fetchone()[0]
                    # Find a warehouse for this company
                    cr.execute("SELECT id FROM stock_warehouse WHERE company_id = %s ORDER BY id ASC LIMIT 1;", (comp_id,))
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
                        """, (comp_id, wh_id))
                        default_farm_id = cr.fetchone()[0]
                    else:
                        cr.execute("ALTER TABLE taghini_farm ALTER COLUMN warehouse_id DROP NOT NULL;")
                        cr.execute("""
                            INSERT INTO taghini_farm (name, code, company_id, farm_type, create_date, write_date)
                            VALUES ('Main Farm Site', 'FRM/MAIN', %s, 'mixed', NOW(), NOW())
                            RETURNING id;
                        """, (comp_id,))
                        default_farm_id = cr.fetchone()[0]

                cr.execute("""
                    UPDATE taghini_pen 
                    SET farm_id = %s 
                    WHERE farm_id IS NULL;
                """, (default_farm_id,))
                _logger.info("[Pre-Migration] Backfilled %d pens to farm_id %d.", null_count, default_farm_id)

    # -------------------------------------------------------------------------
    # 2. FIX NULL standard_type ON taghini_farm_standard
    # -------------------------------------------------------------------------
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'taghini_farm_standard' AND column_name = 'standard_type'
        );
    """)
    if cr.fetchone()[0]:
        cr.execute("""
            UPDATE taghini_farm_standard 
            SET standard_type = 'broiler' 
            WHERE standard_type IS NULL;
        """)

    # -------------------------------------------------------------------------
    # 3. FIX NULL farm_type ON taghini_farm
    # -------------------------------------------------------------------------
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'taghini_farm' AND column_name = 'farm_type'
        );
    """)
    if cr.fetchone()[0]:
        cr.execute("""
            UPDATE taghini_farm 
            SET farm_type = 'broiler' 
            WHERE farm_type IS NULL;
        """)

    # -------------------------------------------------------------------------
    # 4. CLEAN UP LEGACY SECURITY RULES BOUND TO DELETED MODEL taghini.breeder.daily.log
    # -------------------------------------------------------------------------
    cr.execute("""
        DELETE FROM ir_rule 
        WHERE model_id IN (
            SELECT id FROM ir_model WHERE model = 'taghini.breeder.daily.log'
        );
    """)
    cr.execute("""
        DELETE FROM ir_model_access 
        WHERE model_id IN (
            SELECT id FROM ir_model WHERE model = 'taghini.breeder.daily.log'
        );
    """)
    cr.execute("""
        DELETE FROM ir_model_data 
        WHERE model = 'ir.model' AND name = 'model_taghini_breeder_daily_log';
    """)

    # -------------------------------------------------------------------------
    # 5. CLEAN UP OBSOLETE ir_ui_view (POSTGRESQL JSONB TYPE SAFE)
    # -------------------------------------------------------------------------
    cr.execute("""
        DELETE FROM ir_ui_view 
        WHERE model = 'taghini.breeder.daily.log'
           OR arch_db::text LIKE '%taghini.breeder.daily.log%';
    """)

    _logger.info("[chicken_farm_module] Pre-Migration to v1.6.0 completed successfully.")

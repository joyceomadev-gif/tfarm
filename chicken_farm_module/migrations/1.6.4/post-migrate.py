# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def _extract_farm_keywords(farm_name, wh_code):
    """Return uppercase match tokens for a farm name and warehouse code."""
    tokens = []
    if farm_name:
        # Take the leading site name before ' - ' (e.g. 'ILE-IGBON', 'OGUNWOLE', 'DARE', 'ORISIUNBARE', 'KUGBA')
        lead = farm_name.split(' - ')[0].strip().upper()
        if lead and lead not in ('MAIN WAREHOUSE', 'MAIN FARM SITE'):
            tokens.append(lead)
            if '-' in lead:
                tokens.append(lead.replace('-', ' '))
    if wh_code:
        code_u = wh_code.strip().upper()
        if code_u and code_u not in ('WH', 'ABAT', 'ARCPT'):
            tokens.append(code_u)
            if code_u == 'OGCBF':
                tokens.append('OGBCBF')
    return tokens


def backfill_farms_and_transactions(cr):
    """
    Create missing taghini.farm records for farm warehouses and associate farm_id
    (plus warehouse_id/company_id where applicable) on all operational transactions.
    """
    # 1. Create missing taghini.farm records for farm warehouses
    cr.execute("""
        SELECT DISTINCT w.id, w.name, w.code, w.company_id
        FROM stock_warehouse w
        WHERE w.id NOT IN (
            SELECT warehouse_id FROM taghini_farm WHERE warehouse_id IS NOT NULL
        )
          AND UPPER(COALESCE(w.name, '')) NOT LIKE '%ABATTOIR%'
          AND (
              UPPER(COALESCE(w.name, '')) LIKE '%FARM%'
              OR EXISTS (
                  SELECT 1
                  FROM taghini_pen p
                  JOIN stock_location l ON l.id = p.location_id
                  WHERE l.warehouse_id = w.id
              )
          )
        ORDER BY w.id;
    """)
    missing_whs = cr.fetchall()

    # Determine next numeric suffix for FRM/YYYY/NNN
    cr.execute("""
        SELECT COALESCE(MAX(
            CASE
                WHEN code ~ '^FRM/[0-9]{4}/[0-9]+$'
                THEN CAST(SPLIT_PART(code, '/', 3) AS integer)
                ELSE 0
            END
        ), 0)
        FROM taghini_farm;
    """)
    seq_num = cr.fetchone()[0] or 0

    for wh_id, wh_name, wh_code, company_id in missing_whs:
        seq_num += 1
        farm_code = f"FRM/2026/{seq_num:03d}"
        farm_type = 'breeder' if 'BREEDER' in (wh_name or '').upper() else 'broiler'
        cr.execute("""
            INSERT INTO taghini_farm (
                name, code, farm_type, active, company_id, warehouse_id, create_date, write_date
            )
            VALUES (%s, %s, %s, TRUE, %s, %s, NOW(), NOW())
            RETURNING id;
        """, (wh_name, farm_code, farm_type, company_id, wh_id))
        new_farm_id = cr.fetchone()[0]
        _logger.info(
            "[Migration 1.6.4] Created taghini.farm '%s' [%s] (id=%d, type=%s) for warehouse_id=%d.",
            wh_name, farm_code, new_farm_id, farm_type, wh_id
        )

    # 2. Associate taghini_pen.farm_id from pen.location_id -> stock_location.warehouse_id -> taghini_farm
    cr.execute("""
        UPDATE taghini_pen p
        SET farm_id = f.id
        FROM stock_location l
        JOIN taghini_farm f ON f.warehouse_id = l.warehouse_id
        WHERE p.location_id = l.id
          AND l.warehouse_id IS NOT NULL
          AND p.farm_id IS DISTINCT FROM f.id;
    """)

    # Load all non-main farms + their warehouse codes for keyword fallback matching
    cr.execute("""
        SELECT f.id, f.name, w.code
        FROM taghini_farm f
        LEFT JOIN stock_warehouse w ON w.id = f.warehouse_id
        WHERE COALESCE(w.code, '') <> 'WH'
        ORDER BY f.id;
    """)
    farm_keywords = []
    ogunwole_farm_id = None
    for f_id, f_name, w_code in cr.fetchall():
        tokens = _extract_farm_keywords(f_name, w_code)
        if tokens:
            farm_keywords.append((f_id, tokens))
        if 'OGUNWOLE' in (f_name or '').upper():
            ogunwole_farm_id = f_id

    # Fallback: match pens without a specific farm warehouse by pen name
    cr.execute("""
        SELECT p.id, p.name
        FROM taghini_pen p
        LEFT JOIN stock_location l ON l.id = p.location_id
        LEFT JOIN stock_warehouse w ON w.id = l.warehouse_id
        WHERE l.warehouse_id IS NULL OR w.code = 'WH';
    """)
    for pen_id, pen_name in cr.fetchall():
        u_name = (pen_name or '').upper()
        for f_id, tokens in farm_keywords:
            if any(tok in u_name for tok in tokens):
                cr.execute("UPDATE taghini_pen SET farm_id = %s WHERE id = %s;", (f_id, pen_id))
                break

    # Sync stored related fields (warehouse_id, company_id) on taghini_pen
    cr.execute("""
        UPDATE taghini_pen p
        SET warehouse_id = f.warehouse_id,
            company_id = f.company_id
        FROM taghini_farm f
        WHERE p.farm_id = f.id
          AND (p.warehouse_id IS DISTINCT FROM f.warehouse_id
               OR p.company_id IS DISTINCT FROM f.company_id);
    """)

    # 3. Associate taghini_flock (farm_id, warehouse_id, company_id) from taghini_pen
    cr.execute("""
        UPDATE taghini_flock flk
        SET farm_id = p.farm_id,
            warehouse_id = p.warehouse_id,
            company_id = p.company_id
        FROM taghini_pen p
        WHERE flk.pen_model_id = p.id
          AND (flk.farm_id IS DISTINCT FROM p.farm_id
               OR flk.warehouse_id IS DISTINCT FROM p.warehouse_id
               OR flk.company_id IS DISTINCT FROM p.company_id);
    """)

    # 4. Associate taghini_chicken_batch.farm_id
    # 4a. From allocated flocks
    cr.execute("""
        UPDATE taghini_chicken_batch b
        SET farm_id = sub.farm_id
        FROM (
            SELECT DISTINCT ON (batch_id) batch_id, farm_id
            FROM taghini_flock
            WHERE batch_id IS NOT NULL AND farm_id IS NOT NULL
            ORDER BY batch_id, id ASC
        ) sub
        WHERE b.id = sub.batch_id
          AND b.farm_id IS DISTINCT FROM sub.farm_id;
    """)

    # 4b. From picking_id -> warehouse -> farm
    cr.execute("""
        UPDATE taghini_chicken_batch b
        SET farm_id = f.id
        FROM stock_picking sp
        LEFT JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
        LEFT JOIN stock_location dl ON dl.id = sp.location_dest_id
        JOIN taghini_farm f ON f.warehouse_id = COALESCE(spt.warehouse_id, dl.warehouse_id)
        WHERE b.picking_id = sp.id
          AND b.farm_id IS NULL;
    """)

    # 4c. Keyword fallback for unallocated batches (e.g. name contains farm name or CYCLE 2A -> Ogunwole)
    cr.execute("SELECT id, name FROM taghini_chicken_batch WHERE farm_id IS NULL;")
    for batch_id, batch_name in cr.fetchall():
        u_name = (batch_name or '').upper()
        matched_farm_id = None
        for f_id, tokens in farm_keywords:
            if any(tok in u_name for tok in tokens):
                matched_farm_id = f_id
                break
        if not matched_farm_id and ogunwole_farm_id and ('CYCLE 2A' in u_name or 'CYCLE 2 A' in u_name):
            matched_farm_id = ogunwole_farm_id
        if matched_farm_id:
            cr.execute("UPDATE taghini_chicken_batch SET farm_id = %s WHERE id = %s;", (matched_farm_id, batch_id))

    # 5. Associate taghini_daily_log (farm_id, warehouse_id) from taghini_flock
    cr.execute("""
        UPDATE taghini_daily_log l
        SET farm_id = flk.farm_id,
            warehouse_id = flk.warehouse_id
        FROM taghini_flock flk
        WHERE l.flock_id = flk.id
          AND (l.farm_id IS DISTINCT FROM flk.farm_id
               OR l.warehouse_id IS DISTINCT FROM flk.warehouse_id);
    """)

    # 6. Associate taghini_harvest.farm_id from flock / breeder_flock
    cr.execute("""
        UPDATE taghini_harvest h
        SET farm_id = flk.farm_id
        FROM taghini_flock flk
        WHERE h.flock_id = flk.id
          AND h.farm_id IS DISTINCT FROM flk.farm_id;
    """)
    cr.execute("""
        UPDATE taghini_harvest h
        SET farm_id = bf.farm_id
        FROM taghini_breeder_flock bf
        WHERE h.breeder_flock_id = bf.id
          AND h.flock_id IS NULL
          AND h.farm_id IS DISTINCT FROM bf.farm_id;
    """)

    # 7. Associate taghini_abattoir_batch.farm_id from taghini_harvest
    cr.execute("""
        UPDATE taghini_abattoir_batch ab
        SET farm_id = h.farm_id
        FROM taghini_harvest h
        WHERE ab.harvest_id = h.id
          AND ab.farm_id IS DISTINCT FROM h.farm_id;
    """)

    # 8. Associate taghini_abattoir_bagging.farm_id from taghini_abattoir_batch
    cr.execute("""
        UPDATE taghini_abattoir_bagging bg
        SET farm_id = ab.farm_id
        FROM taghini_abattoir_batch ab
        WHERE bg.batch_id = ab.id
          AND bg.farm_id IS DISTINCT FROM ab.farm_id;
    """)

    # 9. Associate breeder operational transactions
    cr.execute("""
        UPDATE taghini_breeder_flock bf
        SET farm_id = p.farm_id
        FROM taghini_pen p
        WHERE bf.pen_id = p.id
          AND bf.farm_id IS DISTINCT FROM p.farm_id;
    """)
    cr.execute("""
        UPDATE taghini_breeder_batch bb
        SET farm_id = sub.farm_id
        FROM (
            SELECT DISTINCT ON (batch_id) batch_id, farm_id
            FROM taghini_breeder_flock
            WHERE batch_id IS NOT NULL AND farm_id IS NOT NULL
            ORDER BY batch_id, id ASC
        ) sub
        WHERE bb.id = sub.batch_id
          AND bb.farm_id IS NULL;
    """)
    cr.execute("""
        UPDATE taghini_breeder_batch bb
        SET farm_id = f.id
        FROM stock_picking sp
        LEFT JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
        LEFT JOIN stock_location dl ON dl.id = sp.location_dest_id
        JOIN taghini_farm f ON f.warehouse_id = COALESCE(spt.warehouse_id, dl.warehouse_id)
        WHERE bb.picking_id = sp.id
          AND bb.farm_id IS NULL;
    """)
    cr.execute("""
        UPDATE taghini_breeder_pen_log bpl
        SET farm_id = bf.farm_id
        FROM taghini_breeder_flock bf
        WHERE bpl.flock_id = bf.id
          AND bpl.farm_id IS DISTINCT FROM bf.farm_id;
    """)
    cr.execute("""
        UPDATE taghini_breeder_egg_room er
        SET farm_id = bb.farm_id
        FROM taghini_breeder_batch bb
        WHERE er.batch_id = bb.id
          AND er.farm_id IS DISTINCT FROM bb.farm_id;
    """)
    cr.execute("""
        UPDATE taghini_breeder_hatchery_dispatch hd
        SET farm_id = bb.farm_id
        FROM taghini_breeder_batch bb
        WHERE hd.batch_id = bb.id
          AND hd.farm_id IS DISTINCT FROM bb.farm_id;
    """)


def migrate(cr, version):
    """
    Post-migration script for chicken_farm_module v1.6.4:
    1. Create missing taghini.farm records for farm warehouses.
    2. Associate the correct farm_id (and warehouse_id/company_id) across all
       pens, flocks, batches, daily logs, harvests, abattoir batches, bagging,
       and breeder operational records.
    """
    _logger.info("===========================================================")
    _logger.info("[chicken_farm_module] Starting Post-Migration to v1.6.4...")
    _logger.info("[chicken_farm_module] Installed DB Version: %s", version)
    _logger.info("===========================================================")

    backfill_farms_and_transactions(cr)

    _logger.info("[chicken_farm_module] Post-Migration to v1.6.4 completed successfully.")

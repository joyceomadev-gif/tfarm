# -*- coding: utf-8 -*-

from datetime import datetime, date, timedelta
from odoo import http, fields, _
from odoo.http import request


class TaghiniFarmDashboardController(http.Controller):

    def _get_env(self):
        try:
            return request.env
        except Exception:
            return getattr(self, '_test_env', None)

    @http.route('/taghini/farm/dashboard/data', type='jsonrpc', auth='user')
    def get_dashboard_data(self, **kwargs):
        farm_id = kwargs.get('farm_id')
        try:
            farm_id = int(farm_id) if farm_id else 0
        except (ValueError, TypeError):
            farm_id = 0

        date_preset = kwargs.get('date_preset') or 'all'
        date_from_str = kwargs.get('date_from') or ''
        date_to_str = kwargs.get('date_to') or ''
        status_filter = kwargs.get('status') or 'all'
        stage_filter = kwargs.get('stage') or 'all'
        alert_filter = kwargs.get('alert_level') or 'all'
        active_tab = kwargs.get('tab') or 'flocks'

        env = self._get_env()
        today = fields.Date.context_today(env['taghini.daily.log'])

        # Calculate date boundaries based on preset or custom range
        if date_preset == '30d':
            start_date = today - timedelta(days=30)
            end_date = today
        elif date_preset == 'month':
            start_date = today.replace(day=1)
            end_date = today
        elif date_preset == 'quarter':
            quarter_month = ((today.month - 1) // 3) * 3 + 1
            start_date = today.replace(month=quarter_month, day=1)
            end_date = today
        elif date_preset == 'custom' and (date_from_str or date_to_str):
            try:
                start_date = fields.Date.from_string(date_from_str) if date_from_str else (today - timedelta(days=365))
            except Exception:
                start_date = today - timedelta(days=365)
            try:
                end_date = fields.Date.from_string(date_to_str) if date_to_str else today
            except Exception:
                end_date = today
        else:  # 'all'
            start_date = today - timedelta(days=365)
            end_date = today

        # 1. Available Farms for Filter Dropdown (100% Dynamic)
        all_farms = env['taghini.farm'].search([], order='name asc')
        farms_list = [{'id': 0, 'name': 'All Farms', 'code': 'ALL'}]
        production_farms = []
        for f in all_farms:
            farms_list.append({
                'id': f.id,
                'name': f.name,
                'code': f.code or '',
            })
            if not (f.code in ('WH', False) and 'Main' in (f.name or '')):
                production_farms.append(f)

        if not production_farms:
            production_farms = list(all_farms)

        # 2. Base domain for Flocks
        flock_domain = []
        if status_filter == 'active':
            flock_domain.append(('state', '=', 'active'))
        elif status_filter == 'harvested':
            flock_domain.append(('state', 'in', ['closed', 'harvested']))
        elif status_filter == 'draft':
            flock_domain.append(('state', '=', 'draft'))

        if farm_id:
            flock_domain.append(('farm_id', '=', farm_id))

        all_flocks = env['taghini.flock'].search(flock_domain)

        # Filter by stage in Python
        filtered_flocks = []
        for fl in all_flocks:
            age = fl.current_age or 0
            if stage_filter == 'brooding' and not (1 <= age <= 10):
                continue
            elif stage_filter == 'early_grow' and not (11 <= age <= 20):
                continue
            elif stage_filter == 'late_grow' and not (21 <= age <= 30):
                continue
            elif stage_filter == 'finishing' and not (age >= 31):
                continue
            filtered_flocks.append(fl)

        # Filter by alert in Python if selected
        final_flocks = []
        for fl in filtered_flocks:
            f_placed = fl.quantity_placed or 0
            f_mort = fl.total_mortality or 0
            m_pct = round((f_mort / f_placed * 100), 2) if f_placed > 0 else 0.0
            is_critical = m_pct > 2.0
            if alert_filter == 'critical' and not is_critical:
                continue
            elif alert_filter == 'normal' and is_critical:
                continue
            final_flocks.append(fl)

        flocks = final_flocks

        # 3. Daily Logs within Date Window
        log_domain = [('date', '>=', start_date), ('date', '<=', end_date)]
        if farm_id:
            log_domain.append(('farm_id', '=', farm_id))

        recent_logs = env['taghini.daily.log'].search(log_domain, order='date desc')
        # If no logs in custom window, search recent 500 for metrics
        all_period_logs = recent_logs
        if not all_period_logs and date_preset == 'all':
            fallback_domain = [('farm_id', '=', farm_id)] if farm_id else []
            all_period_logs = env['taghini.daily.log'].search(fallback_domain, order='date desc', limit=500)

        # 4. Abattoir Batches within Date Window
        abt_domain = [('date', '>=', start_date), ('date', '<=', end_date)]
        if farm_id:
            abt_domain.append(('farm_id', '=', farm_id))
        period_batches = env['taghini.abattoir.batch'].search(abt_domain, order='date desc')
        if not period_batches and date_preset == 'all':
            fallback_abt_domain = [('farm_id', '=', farm_id)] if farm_id else []
            period_batches = env['taghini.abattoir.batch'].search(fallback_abt_domain, order='date desc', limit=200)

        # =====================================================================
        # 5. METRIC 1: MORTALITY RATE PER EACH FARM
        # =====================================================================
        mort_labels = []
        mort_rates = []
        mort_counts = []
        mort_placed = []

        # =====================================================================
        # 6. METRIC 2: ABATTOIR YIELD % PER EACH FARM
        # =====================================================================
        yield_labels = []
        yield_rates = []
        yield_output_kg = []
        yield_input_kg = []

        # =====================================================================
        # 7. METRIC 3: ABATTOIR PRODUCTION VOLUME
        # =====================================================================
        volume_farm_labels = []
        volume_farm_weights = []
        volume_farm_birds = []

        # =====================================================================
        # 8. METRIC 4: FARM FEED CONSUMPTION
        # =====================================================================
        feed_labels = []
        feed_actual_bags = []
        feed_expected_bags = []
        feed_actual_kg = []

        # =====================================================================
        # 9. METRIC 5: WEIGHT VARIANCE
        # =====================================================================
        weight_labels = []
        weight_variances_g = []
        weight_actuals_g = []
        weight_expecteds_g = []

        # =====================================================================
        # 10. METRIC 6: ABATTOIR DEFECT BREAKDOWN
        # =====================================================================
        defect_farm_labels = []
        defect_farm_counts = []

        # Detailed breakdown table
        farm_breakdown = []

        # Loop per production farm to calculate all 6 metrics uniformly
        farms_to_process = [f for f in production_farms if (not farm_id or f.id == farm_id)]
        if not farms_to_process:
            farms_to_process = production_farms

        for f in farms_to_process:
            farm_code = f.code or (f.name[:6].upper() if f.name else f"F{f.id}")
            farm_display = f.code or (f.name.split(' - ')[0] if ' - ' in f.name else f.name)

            # Flocks for this farm
            f_flocks = env['taghini.flock'].search([('farm_id', '=', f.id)])
            f_active_flocks = f_flocks.filtered(lambda fl: fl.state == 'active')
            f_placed = sum(f_flocks.mapped('quantity_placed'))
            f_live = sum(f_active_flocks.mapped('current_birds'))

            # Daily logs for this farm
            f_logs = [l for l in all_period_logs if l.farm_id.id == f.id]
            f_mort_from_logs = sum(l.mortality for l in f_logs)
            f_mort_from_flocks = sum(f_flocks.mapped('total_mortality'))
            f_mort = f_mort_from_logs if f_mort_from_logs > 0 else f_mort_from_flocks
            f_mort_pct = round((f_mort / f_placed * 100), 2) if f_placed > 0 else 0.0

            # Feed consumption for this farm
            f_feed_bags = sum(l.feed_consumed_bags for l in f_logs)
            f_feed_g = sum(l.feed_consumed_g for l in f_logs)
            f_feed_kg = round(f_feed_g / 1000.0, 1)
            f_exp_feed_g = sum(l.expected_feed_g for l in f_logs)
            f_exp_feed_bags = round((f_exp_feed_g / 1000.0) / 25.0, 1)

            # Weight variance for this farm
            f_weight_logs = [l for l in f_logs if l.actual_avg_weight > 0]
            if f_weight_logs:
                f_avg_act_wgt = round(sum(l.actual_avg_weight for l in f_weight_logs) / len(f_weight_logs), 1)
                f_avg_exp_wgt = round(sum(l.expected_avg_weight for l in f_weight_logs) / len(f_weight_logs), 1)
                f_avg_var_wgt = round(sum(l.variance_weight for l in f_weight_logs) / len(f_weight_logs), 1)
            else:
                f_avg_act_wgt = 0.0
                f_avg_exp_wgt = 0.0
                f_avg_var_wgt = 0.0

            # Abattoir batches for this farm
            f_batches = [b for b in period_batches if b.farm_id.id == f.id]
            if not f_batches:
                f_batches = env['taghini.abattoir.batch'].search([('farm_id', '=', f.id)], limit=50)

            f_input_wgt = sum(b.input_weight_kg for b in f_batches)
            f_output_wgt = sum(b.total_output_weight_kg for b in f_batches)
            f_birds_proc = sum(b.total_output_qty or b.input_birds or b.birds_arrived or 0 for b in f_batches)

            if f_input_wgt > 0:
                f_yield_pct = round((f_output_wgt / f_input_wgt * 100), 2)
            elif f_batches:
                yields = [getattr(b, 'yield_percentage', 0.0) or 0.0 for b in f_batches if getattr(b, 'yield_percentage', 0.0) > 0]
                f_yield_pct = round(sum(yields) / len(yields), 2) if yields else 0.0
            else:
                f_yield_pct = 0.0

            # Abattoir defects for this farm
            f_doa = sum(b.mortality_arrived or 0 for b in f_batches)
            f_rec_defects = sum(b.defected_birds or 0 for b in f_batches)
            f_qc_defects = sum(b.defects_count or 0 for b in f_batches)
            f_total_defects = f_doa + f_rec_defects + f_qc_defects

            # Status determination
            status = 'Optimal'
            status_color = 'success'
            if f_mort_pct > 3.0 or (f_yield_pct > 0 and f_yield_pct < 68.0):
                status = 'Critical'
                status_color = 'danger'
            elif f_mort_pct > 1.5 or (f_yield_pct > 0 and f_yield_pct < 72.0):
                status = 'Warning'
                status_color = 'warning'

            # Populate Chart Lists
            mort_labels.append(farm_display)
            mort_rates.append(f_mort_pct)
            mort_counts.append(f_mort)
            mort_placed.append(f_placed)

            yield_labels.append(farm_display)
            yield_rates.append(f_yield_pct)
            yield_output_kg.append(round(f_output_wgt, 1))
            yield_input_kg.append(round(f_input_wgt, 1))

            volume_farm_labels.append(farm_display)
            volume_farm_weights.append(round(f_output_wgt, 1))
            volume_farm_birds.append(f_birds_proc)

            feed_labels.append(farm_display)
            feed_actual_bags.append(f_feed_bags)
            feed_expected_bags.append(f_exp_feed_bags)
            feed_actual_kg.append(f_feed_kg)

            weight_labels.append(farm_display)
            weight_variances_g.append(f_avg_var_wgt)
            weight_actuals_g.append(f_avg_act_wgt)
            weight_expecteds_g.append(f_avg_exp_wgt)

            defect_farm_labels.append(farm_display)
            defect_farm_counts.append(f_total_defects)

            farm_breakdown.append({
                'farm_id': f.id,
                'name': f.name,
                'code': farm_code,
                'active_flocks': len(f_active_flocks),
                'live_birds': f_live,
                'mortality': f_mort,
                'mortality_pct': f_mort_pct,
                'yield_pct': f_yield_pct,
                'feed_bags': f_feed_bags,
                'weight_variance': f_avg_var_wgt,
                'defects_count': f_total_defects,
                'production_volume_kg': round(f_output_wgt, 1),
                'status': status,
                'status_color': status_color,
            })

        # Global Abattoir defect category sums
        total_doa = sum(b.mortality_arrived or 0 for b in period_batches)
        total_reception_defects = sum(b.defected_birds or 0 for b in period_batches)
        total_qc_defects = sum(b.defects_count or 0 for b in period_batches)
        out_of_spec_bags = env['taghini.abattoir.bagging.line'].search_count([
            ('penalty_risk', '=', True)
        ])
        grand_total_defects = total_doa + total_reception_defects + total_qc_defects + out_of_spec_bags

        # Overall Abattoir Production Output by Product Series
        series_categories = {
            'Whole Series': 0.0,
            'Chicken Cuts': 0.0,
            'Chicken Parts': 0.0,
            'Residuals': 0.0,
        }
        if period_batches:
            abt_lines = env['taghini.abattoir.line'].search([('batch_id', 'in', period_batches.ids)])
            for line in abt_lines:
                wgt = line.weight_kg or 0.0
                cat = line.category_type
                if cat == 'series':
                    series_categories['Whole Series'] += wgt
                elif cat == 'cuts':
                    series_categories['Chicken Cuts'] += wgt
                elif cat == 'parts':
                    series_categories['Chicken Parts'] += wgt
                elif cat == 'residuals':
                    series_categories['Residuals'] += wgt

        total_production_volume_kg = round(sum(b.total_output_weight_kg for b in period_batches), 1)
        total_birds_processed = sum(b.total_output_qty or b.input_birds or b.birds_arrived or 0 for b in period_batches)
        total_input_weight_kg = round(sum(b.input_weight_kg for b in period_batches), 1)
        overall_yield_pct = round((total_production_volume_kg / total_input_weight_kg * 100), 2) if total_input_weight_kg > 0 else 0.0

        # Global KPIs
        active_flocks_count = len([fl for fl in flocks if fl.state == 'active'])
        total_live_birds = sum(fl.current_birds for fl in flocks if fl.state == 'active')
        total_placed_birds = sum(fl.quantity_placed for fl in flocks)
        total_mortality_count = sum(fl.total_mortality for fl in flocks)
        overall_mortality_rate = round((total_mortality_count / total_placed_birds * 100), 2) if total_placed_birds > 0 else 0.0
        total_feed_bags = sum(feed_actual_bags)
        weighted_logs = [l for l in all_period_logs if l.actual_avg_weight > 0]
        overall_weight_variance = round(sum(l.variance_weight for l in weighted_logs) / len(weighted_logs), 1) if weighted_logs else 0.0

        # Critical Alerts & Escalations
        critical_alerts = len([fl for fl in flocks if (fl.quantity_placed or 0) > 0 and ((fl.total_mortality or 0) / fl.quantity_placed) > 0.02])
        vet_escalations = env['taghini.daily.log'].search_count([
            ('has_escalated_remarks', '=', True),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ] + ([('farm_id', '=', farm_id)] if farm_id else []))
        feed_deficit_pens = env['taghini.daily.log'].search_count([
            ('variance_feed_g', '<', -1000.0),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ] + ([('farm_id', '=', farm_id)] if farm_id else []))

        # Pen Operations
        pen_operations = []
        alerts = []
        for fl in flocks[:25]:
            f_placed = fl.quantity_placed or 0
            f_current = fl.current_birds or 0
            f_mort = fl.total_mortality or 0
            m_pct = round((f_mort / f_placed * 100), 2) if f_placed > 0 else 0.0

            if m_pct > 2.0:
                alerts.append({
                    'pen': fl.pen_model_id.name or fl.name,
                    'farm': fl.farm_id.name or '',
                    'mort_pct': m_pct,
                    'message': f"Mortality spike of {m_pct}% in {fl.pen_model_id.name or fl.name} ({fl.farm_id.name}). Immediate vet inspection recommended.",
                })

            pen_operations.append({
                'id': fl.id,
                'name': fl.name,
                'farm_name': fl.farm_id.name or '',
                'pen_name': fl.pen_model_id.name or '',
                'placed_birds': f_placed,
                'current_birds': f_current,
                'age_day': fl.current_age or 0,
                'mortality_pct': m_pct,
                'state': fl.state,
            })

        # Abattoir Batches List
        abattoir_batches = []
        batches = env['taghini.abattoir.batch'].search(abt_domain if abt_domain else [], order='date desc', limit=20)
        if not batches:
            batches = env['taghini.abattoir.batch'].search([], order='date desc', limit=20)

        for b in batches:
            b_yield = getattr(b, 'yield_percentage', 0.0) or 0.0
            abattoir_batches.append({
                'id': b.id,
                'name': b.name,
                'date': str(b.date) if b.date else '',
                'farm_name': b.farm_id.name if b.farm_id else '',
                'birds_processed': b.total_output_qty or b.input_birds or b.birds_arrived or 0,
                'total_weight': round(b.total_output_weight_kg or 0, 1),
                'yield_pct': round(b_yield, 1),
                'defected_birds': b.defected_birds or 0,
                'mortality_arrived': b.mortality_arrived or 0,
                'state': b.state,
                'has_penalty_risk': b.bagging_id.has_penalty_risk if b.bagging_id else False,
                'bagging_status': b.bagging_id.compliance_summary if b.bagging_id else 'No Bagging',
            })

        # Breeder Batches List
        breeder_batches = []
        brd_domain = []
        b_list = env['taghini.breeder.batch'].search(brd_domain, order='date desc', limit=15)
        for brd in b_list:
            breeder_batches.append({
                'id': brd.id,
                'name': brd.name,
                'farm_name': brd.company_id.name if brd.company_id else '',
                'male_count': brd.stocked_male_qty or brd.shipped_male_qty or 0,
                'female_count': brd.stocked_female_qty or brd.shipped_female_qty or 0,
                'total_birds': brd.stocked_total_qty or 0,
                'state': brd.state,
            })

        # Breeder KPIs & Pen Series
        active_breeder_flocks = env['taghini.breeder.flock'].search([('state', '=', 'active')])
        act_females = sum(active_breeder_flocks.mapped('current_females'))
        act_males = sum(active_breeder_flocks.mapped('current_males'))
        total_act_birds = act_females + act_males
        ratio_mf = round((act_males * 100.0 / act_females), 2) if act_females > 0 else 0.0

        today_breeder_logs = env['taghini.breeder.pen.log'].search([('date', '=', today)])
        today_hatch_eggs = sum(today_breeder_logs.mapped('hatching_eggs'))
        today_tot_eggs = sum(today_breeder_logs.mapped('total_eggs_collected'))
        today_lay_pct = round((today_tot_eggs * 100.0 / act_females), 2) if act_females > 0 else 0.0

        latest_hatch = env['taghini.breeder.hatchery.dispatch'].search([], order='dispatch_date desc, id desc', limit=1)
        latest_hatchability = round(latest_hatch.hatch_pct_of_set * 100.0, 2) if latest_hatch else 0.0
        latest_chicks_hen = latest_hatch.chicks_per_hen_housed if latest_hatch else 0.0

        active_danger_logs = env['taghini.breeder.pen.log'].search([('danger_count', '>', 0), ('date', '>=', today - timedelta(days=7))])
        breeder_danger_count = len(active_danger_logs)

        breeder_kpis = {
            'active_females': act_females,
            'active_males': act_males,
            'total_active_birds': total_act_birds,
            'males_per_100_females': ratio_mf,
            'today_hatching_eggs': today_hatch_eggs,
            'today_total_eggs': today_tot_eggs,
            'today_hen_day_pct': today_lay_pct,
            'latest_hatchability_pct': latest_hatchability,
            'cum_chicks_per_hen': latest_chicks_hen,
            'active_danger_count': breeder_danger_count,
        }

        breeder_flocks = []
        for bf in env['taghini.breeder.flock'].search([], order='start_date desc', limit=20):
            breeder_flocks.append({
                'id': bf.id,
                'name': bf.name,
                'batch_name': bf.batch_id.name,
                'farm_name': bf.farm_id.name if bf.farm_id else '',
                'pen_name': bf.pen_id.name if bf.pen_id else '',
                'current_females': bf.current_females,
                'current_males': bf.current_males,
                'males_per_100_females': bf.males_per_100_females,
                'phase': dict(bf._fields['lifecycle_phase'].selection).get(bf.lifecycle_phase, bf.lifecycle_phase) if bf.lifecycle_phase else '',
                'state': bf.state,
            })

        hatchery_dispatches = []
        for hd in env['taghini.breeder.hatchery.dispatch'].search([], order='dispatch_date desc', limit=10):
            hatchery_dispatches.append({
                'id': hd.id,
                'name': hd.name,
                'dispatch_note_no': hd.dispatch_note_no,
                'dispatch_date': str(hd.dispatch_date) if hd.dispatch_date else '',
                'flock_age_week': hd.flock_age_week,
                'eggs_set': hd.eggs_set,
                'saleable_chicks': hd.saleable_chicks,
                'fertility_pct': round(hd.fertility_pct * 100.0, 1),
                'hatch_pct_of_set': round(hd.hatch_pct_of_set * 100.0, 1),
                'aa_hatch_pct': round(hd.aa_hatch_pct * 100.0, 1),
                'hatch_dev_pts': hd.hatch_dev_pts,
                'state': hd.state,
            })

        breeder_egg_summary = {
            'hatching_eggs': today_hatch_eggs,
            'floor_eggs': sum(today_breeder_logs.mapped('floor_eggs')),
            'double_yolk_eggs': sum(today_breeder_logs.mapped('double_yolk_eggs')),
            'cracked_eggs': sum(today_breeder_logs.mapped('cracked_eggs')),
            'dirty_eggs': sum(today_breeder_logs.mapped('dirty_eggs')),
            'small_eggs': sum(today_breeder_logs.mapped('small_eggs')),
            'misshapen_eggs': sum(today_breeder_logs.mapped('misshapen_eggs')),
            'total_rejects': sum(today_breeder_logs.mapped('total_rejects')),
        }

        # Backward compatibility charts
        stage_counts = {
            'Brooding (1-10d)': 0,
            'Early Grow (11-20d)': 0,
            'Late Grow (21-30d)': 0,
            'Finishing (31-42d)': 0,
            'Heavy / Harvest (43d+)': 0,
        }
        for fl in flocks:
            age = fl.current_age or 0
            if age <= 10:
                stage_counts['Brooding (1-10d)'] += 1
            elif age <= 20:
                stage_counts['Early Grow (11-20d)'] += 1
            elif age <= 30:
                stage_counts['Late Grow (21-30d)'] += 1
            elif age <= 42:
                stage_counts['Finishing (31-42d)'] += 1
            else:
                stage_counts['Heavy / Harvest (43d+)'] += 1

        return {
            'farms': farms_list,
            'selected_farm_id': farm_id,
            'date_preset': date_preset,
            'date_from': str(start_date),
            'date_to': str(end_date),
            'status': status_filter,
            'stage': stage_filter,
            'alert_level': alert_filter,
            'tab': active_tab,

            # Primary KPI Cards (6 Key Operational Figures)
            'kpis': {
                'mortality_rate': overall_mortality_rate,
                'abattoir_yield_pct': overall_yield_pct,
                'production_volume_kg': total_production_volume_kg,
                'birds_processed': total_birds_processed,
                'feed_consumed_bags': total_feed_bags,
                'weight_variance_g': overall_weight_variance,
                'total_defects': grand_total_defects,
                'active_flocks': active_flocks_count,
                'total_live_birds': total_live_birds,
                'critical_alerts': critical_alerts,
                'vet_escalations': vet_escalations,
                'feed_deficit_pens': feed_deficit_pens,
                'out_of_spec_bags': out_of_spec_bags,
            },

            # 1. Mortality Rate per Each Farm
            'mortality_chart': {
                'labels': mort_labels,
                'rates': mort_rates,
                'counts': mort_counts,
                'placed': mort_placed,
            },

            # 2. Abattoir Yield % per Each Farm
            'yield_chart': {
                'labels': yield_labels,
                'yields': yield_rates,
                'output_kg': yield_output_kg,
                'input_kg': yield_input_kg,
            },

            # 3. Abattoir Production Volume
            'volume_chart': {
                'labels': volume_farm_labels,
                'volumes_kg': volume_farm_weights,
                'birds': volume_farm_birds,
                'total_volume_kg': total_production_volume_kg,
                'total_birds': total_birds_processed,
                'categories': list(series_categories.keys()),
                'category_weights': [round(w, 1) for w in series_categories.values()],
            },

            # 4. Farm Feed Consumption
            'feed_chart': {
                'labels': feed_labels,
                'actual_bags': feed_actual_bags,
                'expected_bags': feed_expected_bags,
                'actual_kg': feed_actual_kg,
                'counts': feed_actual_bags,  # backwards compatibility
            },

            # 5. Weight Variance
            'weight_chart': {
                'labels': weight_labels,
                'variance_g': weight_variances_g,
                'actual_g': weight_actuals_g,
                'expected_g': weight_expecteds_g,
            },

            # 6. Abattoir Defect Breakdown
            'defect_chart': {
                'labels': [
                    'Dead on Arrival (DOA)',
                    'Reception Defects',
                    'Processing Rejects',
                    'Bagging Out-of-Spec',
                ],
                'counts': [total_doa, total_reception_defects, total_qc_defects, out_of_spec_bags],
                'farm_labels': defect_farm_labels,
                'farm_counts': defect_farm_counts,
                'total_defects': grand_total_defects,
            },

            # Backward compatibility chart structures
            'stage_chart': {
                'labels': list(stage_counts.keys()),
                'counts': list(stage_counts.values()),
            },
            'compliance_chart': {
                'labels': ['Compliant', 'Warning', 'Critical'],
                'counts': [
                    len([f for f in flocks if (f.quantity_placed or 0) > 0 and ((f.total_mortality or 0) / f.quantity_placed) <= 0.01]),
                    len([f for f in flocks if (f.quantity_placed or 0) > 0 and 0.01 < ((f.total_mortality or 0) / f.quantity_placed) <= 0.02]),
                    len([f for f in flocks if (f.quantity_placed or 0) > 0 and ((f.total_mortality or 0) / f.quantity_placed) > 0.02]),
                ],
            },

            'farm_breakdown': farm_breakdown,
            'pen_operations': pen_operations,
            'abattoir_batches': abattoir_batches,
            'breeder_batches': breeder_batches,
            'breeder_kpis': breeder_kpis,
            'breeder_flocks': breeder_flocks,
            'hatchery_dispatches': hatchery_dispatches,
            'breeder_egg_summary': breeder_egg_summary,
            'alerts': alerts,
        }

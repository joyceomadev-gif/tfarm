# -*- coding: utf-8 -*-
import base64
import io
from datetime import datetime, date

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from odoo import models, fields, api, _
from odoo.exceptions import UserError


def generate_111_col_excel_workbook(env, logs, title_prefix="Breeder Pen Operations Ledger"):
    """
    Generates a production-grade 111-column Arbor Acres Plus Breeder Operations Ledger
    formatted in OpenPyXL with multi-level grouped headers, frozen panes, formula summaries,
    and cell styling.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "111-Col Daily Ledger"
    ws.views.sheetView[0].showGridLines = True

    # Palette
    c_navy = '1B4F72'       # Title & Header
    c_blue_sec = '2471A3'   # Females
    c_teal_sec = '117864'   # Males
    c_green_sec = '1E8449'  # Feed
    c_slate_sec = '2E4053'  # Water/Env
    c_amber_sec = 'B7950B'  # Lighting
    c_purple_sec = '6C3483' # Weights
    c_coral_sec = '922B21'  # Eggs
    c_brown_sec = '784212'  # Health
    c_grey_sec = '34495E'   # Flags & Audit

    border_thin = Border(
        left=Side(style='thin', color='D4D4D4'),
        right=Side(style='thin', color='D4D4D4'),
        top=Side(style='thin', color='D4D4D4'),
        bottom=Side(style='thin', color='D4D4D4')
    )
    border_double_bottom = Border(
        left=Side(style='thin', color='D4D4D4'),
        right=Side(style='thin', color='D4D4D4'),
        top=Side(style='thin', color='D4D4D4'),
        bottom=Side(style='double', color='1B4F72')
    )
    zebra_fill = PatternFill(start_color='F8F9F9', end_color='F8F9F9', fill_type='solid')
    danger_fill = PatternFill(start_color='FADBD8', end_color='FADBD8', fill_type='solid')
    warning_fill = PatternFill(start_color='FCF3CF', end_color='FCF3CF', fill_type='solid')
    ok_fill = PatternFill(start_color='D4EFDF', end_color='D4EFDF', fill_type='solid')

    font_title = Font(name='Calibri', size=15, bold=True, color='1B4F72')
    font_subtitle = Font(name='Calibri', size=10, italic=True, color='566573')
    font_sec = Font(name='Calibri', size=10, bold=True, color='FFFFFF')
    font_col = Font(name='Calibri', size=9, bold=True, color='FFFFFF')
    font_data = Font(name='Calibri', size=9)
    font_data_bold = Font(name='Calibri', size=9, bold=True)
    font_total = Font(name='Calibri', size=10, bold=True, color='1B4F72')

    align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    align_left = Alignment(horizontal='left', vertical='center')
    align_right = Alignment(horizontal='right', vertical='center')

    # Title Rows
    company_name = env.company.name or "Taghini Farm Management"
    ws['A1'] = f"{company_name} - {title_prefix} (111-Column Operational Ledger)"
    ws['A1'].font = font_title
    ws['A2'] = f"Generated on {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Operational Records: {len(logs)}"
    ws['A2'].font = font_subtitle
    ws.row_dimensions[1].height = 24
    ws.row_dimensions[2].height = 18

    # 10 Major Operational Sections: (Title, Color, StartCol, EndCol)
    sections = [
        ("SECTION 1: TIMING & LIFECYCLE", c_navy, 1, 5),
        ("SECTION 2: FEMALE POPULATION (HENS)", c_blue_sec, 6, 16),
        ("SECTION 3: MALE POPULATION (COCKS)", c_teal_sec, 17, 28),
        ("SECTION 4: FEED (SEX-SEPARATE)", c_green_sec, 29, 41),
        ("SECTION 5: WATER & ENVIRONMENT", c_slate_sec, 42, 50),
        ("SECTION 6: LIGHTING", c_amber_sec, 51, 54),
        ("SECTION 7: SAMPLE BODY WEIGHTS", c_purple_sec, 55, 66),
        ("SECTION 8: EGG COLLECTION & GRADING", c_coral_sec, 67, 86),
        ("SECTION 9: HEALTH & ADMIN", c_brown_sec, 87, 93),
        ("SECTION 10: AUDIT FLAGS & METADATA", c_grey_sec, 94, 103),
    ]

    for sec_title, sec_color, start_c, end_c in sections:
        ws.merge_cells(start_row=4, start_column=start_c, end_row=4, end_column=end_c)
        cell = ws.cell(row=4, column=start_c, value=sec_title)
        fill = PatternFill(start_color=sec_color, end_color=sec_color, fill_type='solid')
        cell.font = font_sec
        cell.alignment = align_center
        for c in range(start_c, end_c + 1):
            ws.cell(row=4, column=c).fill = fill
            ws.cell(row=4, column=c).border = border_thin

    ws.row_dimensions[4].height = 22

    # Column Definitions: (Field, Header Label, Format, Align, Width)
    # Formats: 'text', 'int', 'float1', 'float2', 'pct1', 'pct2', 'pct4', 'bool'
    columns = [
        # Sec 1: Timing
        ('name', "Log ID", 'text', align_center, 16),
        ('date', "Date", 'text', align_center, 12),
        ('age_day', "Age (Days)", 'int', align_right, 11),
        ('age_week', "Age (Wks)", 'int', align_right, 10),
        ('phase', "Phase", 'text', align_center, 14),

        # Sec 2: Female Population
        ('opening_females', "Opening Females", 'int', align_right, 14),
        ('female_mortality', "Female Mort.", 'int', align_right, 12),
        ('female_culls', "Female Culls", 'int', align_right, 12),
        ('sex_error_removals', "Sex-Error Removals", 'int', align_right, 16),
        ('females_in', "Females In", 'int', align_right, 12),
        ('females_out', "Females Out", 'int', align_right, 12),
        ('closing_females', "Closing Females", 'int', align_right, 14),
        ('female_daily_mort_pct', "F. Daily Mort %", 'pct4', align_right, 14),
        ('female_cum_mortality', "F. Cum Mort", 'int', align_right, 13),
        ('female_cum_mort_pct_placed', "F. Cum Mort % Placed", 'pct2', align_right, 17),
        ('female_cum_culls_sex_errors', "F. Cum Culls+Errors", 'int', align_right, 16),

        # Sec 3: Male Population
        ('opening_males', "Opening Males", 'int', align_right, 13),
        ('male_mortality', "Male Mort.", 'int', align_right, 11),
        ('male_culls', "Male Culls", 'int', align_right, 11),
        ('males_in', "Males In", 'int', align_right, 11),
        ('males_out', "Males Out", 'int', align_right, 11),
        ('closing_males', "Closing Males", 'int', align_right, 13),
        ('male_daily_mort_pct', "M. Daily Mort %", 'pct4', align_right, 14),
        ('male_cum_mortality', "M. Cum Mort", 'int', align_right, 13),
        ('male_cum_mort_pct_placed', "M. Cum Mort % Placed", 'pct2', align_right, 17),
        ('males_per_100_females', "Males/100 Females", 'float2', align_right, 15),
        ('main_cause_of_death', "Main Cause of Death", 'text', align_left, 20),
        ('post_mortem_done', "Post-Mortem Done", 'bool', align_center, 14),

        # Sec 4: Feed
        ('feed_name', "Feed Type", 'text', align_left, 18),
        ('feed_batch_no', "Feed Batch No.", 'text', align_center, 15),
        ('planned_nil_feed_day', "Planned Nil Feed", 'bool', align_center, 14),
        ('female_feed_kg', "Female Feed (kg)", 'float1', align_right, 15),
        ('female_feed_g_per_bird', "Female g/bird", 'float1', align_right, 13),
        ('aa_female_feed_g', "AA Female Feed (g)", 'float1', align_right, 16),
        ('female_feed_var_pct', "Female Feed Var %", 'pct2', align_right, 15),
        ('male_feed_kg', "Male Feed (kg)", 'float1', align_right, 14),
        ('male_feed_g_per_bird', "Male g/bird", 'float1', align_right, 12),
        ('aa_male_feed_g', "AA Male Feed (g)", 'float1', align_right, 15),
        ('male_feed_var_pct', "Male Feed Var %", 'pct2', align_right, 14),
        ('female_cleanup_hours', "Clean-Up Time (hrs)", 'float1', align_right, 16),
        ('sex_separate_feeding_ok', "Sex-Separate Feed OK", 'bool', align_center, 16),

        # Sec 5: Water & Environment
        ('water_consumed_l', "Water Consumed (L)", 'float1', align_right, 16),
        ('water_ml_per_bird', "Water ml/bird", 'float1', align_right, 13),
        ('water_feed_ratio', "Water:Feed Ratio", 'float2', align_right, 14),
        ('min_temp', "Min Temp (°C)", 'float1', align_right, 13),
        ('max_temp', "Max Temp (°C)", 'float1', align_right, 13),
        ('max_rh', "Max RH (%)", 'float1', align_right, 12),
        ('litter_score', "Litter Score (1-5)", 'int', align_center, 14),
        ('curtain_position', "Curtain Position", 'text', align_center, 14),
        ('footbath_changed', "Footbath Changed", 'bool', align_center, 14),

        # Sec 6: Lighting
        ('light_on_time_str', "Lights ON", 'text', align_center, 11),
        ('light_off_time_str', "Lights OFF", 'text', align_center, 11),
        ('light_hours', "Light Hours", 'float2', align_right, 12),
        ('light_intensity_lux', "Light Intensity (lux)", 'float1', align_right, 16),

        # Sec 7: Sample Body Weights
        ('female_sample_n', "F. Sample (n)", 'int', align_right, 12),
        ('female_avg_bw_g', "Female Avg BW (g)", 'float1', align_right, 15),
        ('female_cv_pct', "Female CV %", 'pct2', align_right, 13),
        ('female_uniformity_pct', "Female Uniformity %", 'pct1', align_right, 16),
        ('aa_female_bw_g', "AA Female BW (g)", 'float1', align_right, 15),
        ('female_bw_dev_pct', "Female BW Dev %", 'pct2', align_right, 15),
        ('male_sample_n', "M. Sample (n)", 'int', align_right, 12),
        ('male_avg_bw_g', "Male Avg BW (g)", 'float1', align_right, 14),
        ('male_cv_pct', "Male CV %", 'pct2', align_right, 12),
        ('male_uniformity_pct', "Male Uniformity %", 'pct1', align_right, 15),
        ('aa_male_bw_g', "AA Male BW (g)", 'float1', align_right, 14),
        ('male_bw_dev_pct', "Male BW Dev %", 'pct2', align_right, 14),

        # Sec 8: Egg Production & Grading
        ('total_eggs_collected', "Total Eggs", 'int', align_right, 13),
        ('hatching_eggs', "Hatching Eggs", 'int', align_right, 13),
        ('floor_eggs', "Floor Eggs", 'int', align_right, 11),
        ('double_yolk_eggs', "Double-Yolk", 'int', align_right, 12),
        ('cracked_eggs', "Cracked Eggs", 'int', align_right, 12),
        ('dirty_eggs', "Dirty Eggs", 'int', align_right, 11),
        ('small_eggs', "Small Eggs", 'int', align_right, 11),
        ('misshapen_eggs', "Misshapen Eggs", 'int', align_right, 14),
        ('total_rejects', "Total Rejects", 'int', align_right, 13),
        ('avg_egg_weight_g', "Avg Egg Wt (g)", 'float1', align_right, 14),
        ('hen_day_pct', "Hen-Day %", 'pct2', align_right, 12),
        ('aa_hen_week_pct', "AA Hen-Week %", 'pct2', align_right, 14),
        ('hen_day_var_pts', "Hen-Day Var (pts)", 'float2', align_right, 15),
        ('hatching_egg_pct', "Hatching Egg %", 'pct2', align_right, 14),
        ('aa_hatching_egg_pct', "AA Hatch Egg %", 'pct2', align_right, 14),
        ('floor_egg_pct', "Floor Egg %", 'pct2', align_right, 12),
        ('reject_pct', "Reject %", 'pct2', align_right, 11),
        ('aa_egg_weight_g', "AA Egg Wt (g)", 'float1', align_right, 13),
        ('cum_eggs_per_hen', "Cum Eggs/Hen", 'float2', align_right, 14),
        ('cum_hatching_eggs_per_hen', "Cum Hatch/Hen", 'float2', align_right, 14),

        # Sec 9: Health & Admin
        ('medication_name', "Medication Administered", 'text', align_left, 22),
        ('vet_prescription_no', "Prescription No.", 'text', align_center, 15),
        ('vaccine_name', "Vaccine Name", 'text', align_left, 18),
        ('vaccine_batch_no', "Vaccine Batch", 'text', align_center, 14),
        ('vaccine_route', "Vaccine Route", 'text', align_center, 13),
        ('clinical_remarks', "Clinical Remarks", 'text', align_left, 24),
        ('recorded_by', "Recorded By", 'text', align_center, 14),

        # Sec 10: Audit Flags & Meta
        ('row_status', "Row Status", 'text', align_center, 13),
        ('danger_count', "Danger Count", 'int', align_right, 12),
        ('error_count', "Error Count", 'int', align_right, 12),
        ('danger_flags', "Danger Flags (D01-D27)", 'text', align_left, 30),
        ('data_errors', "Data Errors (E01-E20)", 'text', align_left, 25),
        ('state', "Log Status", 'text', align_center, 12),
        ('batch_name', "Mother Batch", 'text', align_left, 16),
        ('pen_name', "Pen / House", 'text', align_left, 14),
        ('farm_name', "Farm Site", 'text', align_left, 16),
        ('company_name', "Company", 'text', align_left, 16),
    ]

    # Write Row 5 (Column Headers)
    sub_fill = PatternFill(start_color='2C3E50', end_color='2C3E50', fill_type='solid')
    for col_idx, (fld, label, fmt, aln, width) in enumerate(columns, start=1):
        cell = ws.cell(row=5, column=col_idx, value=label)
        cell.font = font_col
        cell.fill = sub_fill
        cell.alignment = align_center
        cell.border = border_thin
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[5].height = 28

    # Format mapping
    num_formats = {
        'int': '#,##0',
        'float1': '#,##0.0',
        'float2': '#,##0.00',
        'pct1': '0.0%',
        'pct2': '0.00%',
        'pct4': '0.0000%',
    }

    # Data Rows
    current_row = 6
    sorted_logs = logs.sorted(key=lambda r: (r.date or date.min, r.id))

    for log in sorted_logs:
        # Pre-extract complex / related strings
        def _float_time_str(val):
            if val is False or val is None:
                return ""
            hrs = int(val)
            mins = int(round((val - hrs) * 60))
            return f"{hrs:02d}:{mins:02d}"

        field_vals = {
            'name': log.name or '',
            'date': str(log.date) if log.date else '',
            'age_day': log.age_day or 0,
            'age_week': log.age_week or 0,
            'phase': dict(log._fields['phase'].selection).get(log.phase, log.phase or ''),

            'opening_females': log.opening_females or 0,
            'female_mortality': log.female_mortality or 0,
            'female_culls': log.female_culls or 0,
            'sex_error_removals': log.sex_error_removals or 0,
            'females_in': log.females_in or 0,
            'females_out': log.females_out or 0,
            'closing_females': log.closing_females or 0,
            'female_daily_mort_pct': log.female_daily_mort_pct or 0.0,
            'female_cum_mortality': log.female_cum_mortality or 0,
            'female_cum_mort_pct_placed': log.female_cum_mort_pct_placed or 0.0,
            'female_cum_culls_sex_errors': log.female_cum_culls_sex_errors or 0,

            'opening_males': log.opening_males or 0,
            'male_mortality': log.male_mortality or 0,
            'male_culls': log.male_culls or 0,
            'males_in': log.males_in or 0,
            'males_out': log.males_out or 0,
            'closing_males': log.closing_males or 0,
            'male_daily_mort_pct': log.male_daily_mort_pct or 0.0,
            'male_cum_mortality': log.male_cum_mortality or 0,
            'male_cum_mort_pct_placed': log.male_cum_mort_pct_placed or 0.0,
            'males_per_100_females': log.males_per_100_females or 0.0,
            'main_cause_of_death': log.main_cause_of_death or '',
            'post_mortem_done': "YES" if log.post_mortem_done else "NO",

            'feed_name': log.feed_product_id.display_name if log.feed_product_id else '',
            'feed_batch_no': log.feed_batch_no or '',
            'planned_nil_feed_day': "YES" if log.planned_nil_feed_day else "NO",
            'female_feed_kg': log.female_feed_kg or 0.0,
            'female_feed_g_per_bird': log.female_feed_g_per_bird or 0.0,
            'aa_female_feed_g': log.aa_female_feed_g or 0.0,
            'female_feed_var_pct': log.female_feed_var_pct or 0.0,
            'male_feed_kg': log.male_feed_kg or 0.0,
            'male_feed_g_per_bird': log.male_feed_g_per_bird or 0.0,
            'aa_male_feed_g': log.aa_male_feed_g or 0.0,
            'male_feed_var_pct': log.male_feed_var_pct or 0.0,
            'female_cleanup_hours': log.female_cleanup_hours or 0.0,
            'sex_separate_feeding_ok': "OK" if log.sex_separate_feeding_ok else "FAIL",

            'water_consumed_l': log.water_consumed_l or 0.0,
            'water_ml_per_bird': log.water_ml_per_bird or 0.0,
            'water_feed_ratio': log.water_feed_ratio or 0.0,
            'min_temp': log.min_temp or 0.0,
            'max_temp': log.max_temp or 0.0,
            'max_rh': log.max_rh or 0.0,
            'litter_score': log.litter_score or 1,
            'curtain_position': log.curtain_position or '',
            'footbath_changed': "YES" if log.footbath_changed else "NO",

            'light_on_time_str': _float_time_str(log.light_on_time),
            'light_off_time_str': _float_time_str(log.light_off_time),
            'light_hours': log.light_hours or 0.0,
            'light_intensity_lux': log.light_intensity_lux or 0.0,

            'female_sample_n': log.female_sample_n or 0,
            'female_avg_bw_g': log.female_avg_bw_g or 0.0,
            'female_cv_pct': log.female_cv_pct or 0.0,
            'female_uniformity_pct': log.female_uniformity_pct or 0.0,
            'aa_female_bw_g': log.aa_female_bw_g or 0.0,
            'female_bw_dev_pct': log.female_bw_dev_pct or 0.0,
            'male_sample_n': log.male_sample_n or 0,
            'male_avg_bw_g': log.male_avg_bw_g or 0.0,
            'male_cv_pct': log.male_cv_pct or 0.0,
            'male_uniformity_pct': log.male_uniformity_pct or 0.0,
            'aa_male_bw_g': log.aa_male_bw_g or 0.0,
            'male_bw_dev_pct': log.male_bw_dev_pct or 0.0,

            'total_eggs_collected': log.total_eggs_collected or 0,
            'hatching_eggs': log.hatching_eggs or 0,
            'floor_eggs': log.floor_eggs or 0,
            'double_yolk_eggs': log.double_yolk_eggs or 0,
            'cracked_eggs': log.cracked_eggs or 0,
            'dirty_eggs': log.dirty_eggs or 0,
            'small_eggs': log.small_eggs or 0,
            'misshapen_eggs': log.misshapen_eggs or 0,
            'total_rejects': log.total_rejects or 0,
            'avg_egg_weight_g': log.avg_egg_weight_g or 0.0,
            'hen_day_pct': log.hen_day_pct or 0.0,
            'aa_hen_week_pct': log.aa_hen_week_pct or 0.0,
            'hen_day_var_pts': log.hen_day_var_pts or 0.0,
            'hatching_egg_pct': log.hatching_egg_pct or 0.0,
            'aa_hatching_egg_pct': log.aa_hatching_egg_pct or 0.0,
            'floor_egg_pct': log.floor_egg_pct or 0.0,
            'reject_pct': log.reject_pct or 0.0,
            'aa_egg_weight_g': log.aa_egg_weight_g or 0.0,
            'cum_eggs_per_hen': log.cum_eggs_per_hen or 0.0,
            'cum_hatching_eggs_per_hen': log.cum_hatching_eggs_per_hen or 0.0,

            'medication_name': log.medication_product_id.display_name if log.medication_product_id else '',
            'vet_prescription_no': log.vet_prescription_no or '',
            'vaccine_name': log.vaccine_name or '',
            'vaccine_batch_no': log.vaccine_batch_no or '',
            'vaccine_route': log.vaccine_route or '',
            'clinical_remarks': log.clinical_remarks or '',
            'recorded_by': log.recorded_by or '',

            'row_status': log.row_status.upper() if log.row_status else 'OK',
            'danger_count': log.danger_count or 0,
            'error_count': log.error_count or 0,
            'danger_flags': log.danger_flags or '',
            'data_errors': log.data_errors or '',
            'state': 'POSTED' if log.state == 'posted' else 'DRAFT',
            'batch_name': log.batch_id.name if log.batch_id else '',
            'pen_name': log.pen_id.name if log.pen_id else '',
            'farm_name': log.farm_id.name if log.farm_id else '',
            'company_name': log.company_id.name if log.company_id else '',
        }

        # Zebra fill
        row_fill = zebra_fill if (current_row % 2 == 0) else None

        for col_idx, (fld, label, fmt, aln, width) in enumerate(columns, start=1):
            val = field_vals.get(fld, '')
            cell = ws.cell(row=current_row, column=col_idx, value=val)
            cell.font = font_data
            cell.alignment = aln
            cell.border = border_thin

            if row_fill:
                cell.fill = row_fill

            # Format cell
            if fmt in num_formats:
                cell.number_format = num_formats[fmt]

            # Highlight Status cell
            if fld == 'row_status':
                if val == 'DANGER':
                    cell.fill = danger_fill
                    cell.font = font_data_bold
                elif val == 'FIX_ERRORS':
                    cell.fill = warning_fill
                    cell.font = font_data_bold
                elif val == 'OK':
                    cell.fill = ok_fill

        ws.row_dimensions[current_row].height = 19
        current_row += 1

    # Summary Row at the bottom
    tot_row = current_row
    ws.cell(row=tot_row, column=1, value="TOTALS / LIFECYCLE SUMMARY").font = font_total
    ws.merge_cells(start_row=tot_row, start_column=1, end_row=tot_row, end_column=5)

    # Calculate Totals for key metrics
    sum_cols = {
        7: "SUM",   # Female mort
        8: "SUM",   # Female culls
        18: "SUM",  # Male mort
        19: "SUM",  # Male culls
        32: "SUM",  # Female feed kg
        36: "SUM",  # Male feed kg
        42: "SUM",  # Water L
        67: "SUM",  # Total eggs
        68: "SUM",  # Hatching eggs
        69: "SUM",  # Floor eggs
        70: "SUM",  # Double yolk
        71: "SUM",  # Cracked
        72: "SUM",  # Dirty
        73: "SUM",  # Small
        74: "SUM",  # Misshapen
        75: "SUM",  # Total rejects
    }

    if len(logs) > 0:
        first_r = 6
        last_r = current_row - 1
        for col_idx in range(1, len(columns) + 1):
            cell = ws.cell(row=tot_row, column=col_idx)
            cell.font = font_total
            cell.border = border_double_bottom

            if col_idx in sum_cols:
                col_let = get_column_letter(col_idx)
                cell.value = f"=SUM({col_let}{first_r}:{col_let}{last_r})"
                cell.number_format = '#,##0'
                cell.alignment = align_right

    ws.row_dimensions[tot_row].height = 24

    # Freeze Panes: keep header (rows 1-5) and Date/Age (cols A-D) visible!
    ws.freeze_panes = 'E6'

    # Save to buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


class TaghiniBreederExcelExportWizard(models.TransientModel):
    _name = 'taghini.breeder.excel.export.wizard'
    _description = 'Export Breeder 111-Column Performance Ledger'

    flock_id = fields.Many2one(
        'taghini.breeder.flock',
        string='Breeder Pen Series',
        help='Export records for a specific pen series, or leave blank to export all matching criteria.'
    )
    batch_id = fields.Many2one(
        'taghini.breeder.batch',
        string='Mother Batch',
        help='Optional filter by mother batch.'
    )
    farm_id = fields.Many2one(
        'taghini.farm',
        string='Farm Site',
        help='Optional filter by farm site.'
    )
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    state_filter = fields.Selection([
        ('all', 'All (Draft & Posted)'),
        ('posted', 'Posted Only'),
        ('draft', 'Draft Only'),
    ], string='Log Status', default='all', required=True)

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        if self.batch_id and not self.farm_id:
            self.farm_id = self.batch_id.farm_id

    @api.onchange('flock_id')
    def _onchange_flock_id(self):
        if self.flock_id:
            self.batch_id = self.flock_id.batch_id
            self.farm_id = self.flock_id.farm_id

    def action_export_excel(self):
        self.ensure_one()
        domain = []
        if self.flock_id:
            domain.append(('flock_id', '=', self.flock_id.id))
        elif self.batch_id:
            domain.append(('batch_id', '=', self.batch_id.id))
        elif self.farm_id:
            domain.append(('farm_id', '=', self.farm_id.id))

        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))

        if self.state_filter == 'posted':
            domain.append(('state', '=', 'posted'))
        elif self.state_filter == 'draft':
            domain.append(('state', '=', 'draft'))

        logs = self.env['taghini.breeder.pen.log'].search(domain, order='date asc, id asc')
        if not logs:
            raise UserError(_("No breeder daily operations logs match the selected filter criteria."))

        title_info = "Breeder Daily Operations"
        if self.flock_id:
            title_info = f"{self.flock_id.name} ({self.flock_id.pen_id.name})"
        elif self.batch_id:
            title_info = f"Batch {self.batch_id.name}"

        file_bytes = generate_111_col_excel_workbook(self.env, logs, title_prefix=title_info)
        b64_data = base64.b64encode(file_bytes)

        flock_suffix = self.flock_id.name.replace('/', '_') if self.flock_id else 'All_Pens'
        filename = f"Breeder_111Col_Ledger_{flock_suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': b64_data,
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

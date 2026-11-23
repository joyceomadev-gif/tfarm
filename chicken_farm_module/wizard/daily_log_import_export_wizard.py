# -*- coding: utf-8 -*-
import base64
import csv
import io
import re
from datetime import datetime, date

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class TaghiniDailyLogImportExportWizard(models.TransientModel):
    _name = 'taghini.daily.log.import.export.wizard'
    _description = 'Import & Export Daily Farm Logs'

    mode = fields.Selection([
        ('export', 'Export Daily Logs'),
        ('import', 'Import Daily Logs'),
        ('template', 'Download Import Template'),
    ], string='Action', default='export', required=True)

    step = fields.Selection([
        ('config', 'Configure'),
        ('result', 'Completed'),
    ], default='config', string='Step')

    # -------------------------------------------------------------------------
    # EXPORT CRITERIA
    # -------------------------------------------------------------------------
    flock_id = fields.Many2one(
        'taghini.flock',
        string='Flock / Pen Series',
        help='Select a specific flock or leave blank to export across flocks.'
    )
    farm_id = fields.Many2one(
        'taghini.farm',
        string='Farm Location',
        help='Optional filter by farm location.'
    )
    date_from = fields.Date(
        string='Date From',
        help='Filter logs from this date inclusive.'
    )
    date_to = fields.Date(
        string='Date To',
        help='Filter logs up to this date inclusive.'
    )
    state_filter = fields.Selection([
        ('all', 'All Logs (Draft & Posted)'),
        ('draft', 'Draft Logs Only'),
        ('done', 'Posted Logs Only'),
    ], string='Log Status', default='all')

    export_format = fields.Selection([
        ('xlsx', 'Excel (.xlsx) - Formatted Workbook'),
        ('csv', 'CSV (.csv) - Comma Delimited'),
    ], string='Export Format', default='xlsx', required=True)

    selected_log_ids = fields.Many2many(
        'taghini.daily.log',
        string='Selected Logs',
        help='Specific daily logs selected from the list view for export.'
    )
    selected_log_count = fields.Integer(
        string='Selected Logs Count',
        compute='_compute_selected_log_count'
    )

    # -------------------------------------------------------------------------
    # IMPORT OPTIONS
    # -------------------------------------------------------------------------
    import_file = fields.Binary(
        string='Upload File (.xlsx or .csv)',
        help='Upload a spreadsheet (.xlsx) or CSV (.csv) containing daily log entries.'
    )
    import_filename = fields.Char(string='File Name')
    target_flock_id = fields.Many2one(
        'taghini.flock',
        string='Default Flock / Pen Series',
        help='Flock to assign if not specified in each row of the imported file.'
    )
    on_existing = fields.Selection([
        ('update', 'Update existing draft logs for the same date'),
        ('skip', 'Skip duplicates (keep existing logs unchanged)'),
        ('error', 'Raise error if a log already exists on the same date'),
    ], string='Duplicate Handling', default='update', required=True)
    auto_post = fields.Boolean(
        string='Auto-Post Stock Moves after Import',
        default=False,
        help='If checked, newly imported logs will immediately execute stock moves (feed, meds, mortalities).'
    )

    # -------------------------------------------------------------------------
    # TEMPLATE OPTIONS
    # -------------------------------------------------------------------------
    template_flock_id = fields.Many2one(
        'taghini.flock',
        string='Sample Flock for Template',
        help='Pre-fills sample data with this flock name and pen.'
    )
    template_format = fields.Selection([
        ('xlsx', 'Excel (.xlsx) - with Instructions Sheet'),
        ('csv', 'CSV (.csv) - Plain Template'),
    ], string='Template Format', default='xlsx', required=True)

    # -------------------------------------------------------------------------
    # OUTPUT / RESULT
    # -------------------------------------------------------------------------
    file_output = fields.Binary(string='Download File', readonly=True)
    file_name = fields.Char(string='Output Filename', readonly=True)
    result_summary = fields.Text(string='Summary', readonly=True)
    error_details = fields.Text(string='Error Details', readonly=True)

    @api.depends('selected_log_ids')
    def _compute_selected_log_count(self):
        for record in self:
            record.selected_log_count = len(record.selected_log_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        active_ids = self.env.context.get('active_ids')

        # Opened from taghini.flock form
        if active_model == 'taghini.flock' and active_id:
            flock = self.env['taghini.flock'].browse(active_id)
            res.update({
                'flock_id': flock.id,
                'target_flock_id': flock.id,
                'template_flock_id': flock.id,
                'farm_id': flock.farm_id.id if flock.farm_id else False,
            })

        # Opened from taghini.daily.log list with selected records
        elif active_model == 'taghini.daily.log' and active_ids:
            res.update({
                'selected_log_ids': [(6, 0, active_ids)],
                'mode': 'export',
            })
            # If all selected logs belong to the same flock, prefill flock_id
            logs = self.env['taghini.daily.log'].browse(active_ids)
            flocks = logs.mapped('flock_id')
            if len(flocks) == 1:
                res['flock_id'] = flocks.id
                res['target_flock_id'] = flocks.id
                res['template_flock_id'] = flocks.id

        return res

    # =========================================================================
    # ACTION: EXPORT DAILY LOGS
    # =========================================================================
    def action_export(self):
        self.ensure_one()
        logs = self._get_logs_to_export()
        if not logs:
            raise UserError(_("No daily logs match the selected filter criteria."))

        timestamp = fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
        flock_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', self.flock_id.name[:20]) if self.flock_id else 'all_flocks'
        base_name = f"Daily_Logs_{flock_slug}_{timestamp}"

        if self.export_format == 'xlsx':
            file_data = self._generate_excel_export(logs)
            filename = f"{base_name}.xlsx"
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            file_data = self._generate_csv_export(logs)
            filename = f"{base_name}.csv"
            mimetype = 'text/csv'

        b64_data = base64.b64encode(file_data)
        self.write({
            'file_output': b64_data,
            'file_name': filename,
            'step': 'result',
            'result_summary': _("Successfully exported %d daily log records.") % len(logs),
            'error_details': False,
        })

        # Return action to download file directly via browser
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': b64_data,
            'type': 'binary',
            'mimetype': mimetype,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def _get_logs_to_export(self):
        if self.selected_log_ids:
            return self.selected_log_ids.sorted(key=lambda l: (l.flock_id.name or '', l.date or date.min, l.id or 0), reverse=True)

        domain = []
        if self.flock_id:
            domain.append(('flock_id', '=', self.flock_id.id))
        elif self.farm_id:
            domain.append(('farm_id', '=', self.farm_id.id))

        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))

        if self.state_filter and self.state_filter != 'all':
            domain.append(('state', '=', self.state_filter))

        return self.env['taghini.daily.log'].search(domain, order='date desc, id desc')

    # =========================================================================
    # EXCEL EXPORT BUILDER
    # =========================================================================
    def _generate_excel_export(self, logs):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Daily Operations Logs"
        ws.views.sheetView[0].showGridLines = True

        # Styles
        title_font = Font(name='Calibri', size=14, bold=True, color='1B4F72')
        subtitle_font = Font(name='Calibri', size=10, italic=True, color='5D6D7E')
        header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='1B4F72', end_color='1B4F72', fill_type='solid')
        header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

        data_font = Font(name='Calibri', size=10)
        border_thin = Border(
            left=Side(style='thin', color='D4D4D4'),
            right=Side(style='thin', color='D4D4D4'),
            top=Side(style='thin', color='D4D4D4'),
            bottom=Side(style='thin', color='D4D4D4')
        )
        zebra_fill = PatternFill(start_color='F8F9F9', end_color='F8F9F9', fill_type='solid')

        # Title Rows
        company_name = self.env.company.name or "Taghini Farm Management"
        ws['A1'] = f"{company_name} - Daily Operations Logs Export"
        ws['A1'].font = title_font
        ws['A2'] = f"Generated on {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Records: {len(logs)}"
        ws['A2'].font = subtitle_font
        ws.row_dimensions[1].height = 24
        ws.row_dimensions[2].height = 18

        headers = [
            ("Log ID", 16),
            ("Flock ID", 15),
            ("Date", 12),
            ("Flock / Pen Series", 30),
            ("Pen Location", 18),
            ("Farm", 18),
            ("Age (Days)", 11),
            ("Start Birds", 12),
            ("Mortality", 11),
            ("Daily Mort %", 12),
            ("Cumm Mortality", 14),
            ("Cumm Mort %", 13),
            ("Feed Type", 22),
            ("Feed Consumed (Bags)", 18),
            ("Feed Consumed (g)", 17),
            ("Feed / Bird (g)", 14),
            ("Expected Feed (g)", 16),
            ("Feed Var (g)", 14),
            ("Water (L)", 12),
            ("Actual Avg Wgt (g)", 16),
            ("Expected Avg Wgt (g)", 18),
            ("Wgt Var (g)", 13),
            ("Light (Hrs)", 11),
            ("Light Period", 14),
            ("Vaccine", 16),
            ("Medications Administered", 26),
            ("Standard Remarks / Symptoms", 26),
            ("Clinical Notes / Remarks", 28),
            ("Store Items Received", 22),
            ("Farm Activities", 24),
            ("Farm Observations", 24),
            ("Status", 10),
        ]

        header_row_idx = 4
        ws.row_dimensions[header_row_idx].height = 28

        for col_idx, (col_name, _) in enumerate(headers, start=1):
            cell = ws.cell(row=header_row_idx, column=col_idx, value=col_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = border_thin

        # Data Rows
        for row_idx, log in enumerate(logs, start=5):
            ws.row_dimensions[row_idx].height = 20
            row_fill = zebra_fill if row_idx % 2 == 0 else PatternFill(fill_type=None)

            # Medications string
            med_list = []
            for m in log.medication_line_ids:
                uom_name = m.uom_id.name or ''
                med_list.append(f"{m.product_id.name} ({m.quantity} {uom_name} - {m.administration_route or 'water'})")
            if not med_list and log.medication_product_id:
                med_list.append(f"{log.medication_product_id.name} ({log.medication_qty})")
            med_str = "; ".join(med_list)

            # Remarks string
            remark_str = ", ".join(log.remark_ids.mapped('name'))

            row_data = [
                log.name or '',
                log.flock_id.flock_code or '',
                str(log.date or ''),
                log.flock_id.name or '',
                log.pen_id.name or '',
                log.farm_id.name or '',
                log.age_day or 0,
                log.birds_count or 0,
                log.mortality or 0,
                (log.daily_mortality_percent or 0.0),
                log.cumm_mortality or 0,
                (log.cumm_mortality_percent or 0.0),
                log.feed_product_id.name or '',
                log.feed_consumed_bags or 0,
                log.feed_consumed_g or 0.0,
                log.feed_per_bird_g or 0.0,
                log.expected_feed_g or 0.0,
                log.variance_feed_g or 0.0,
                log.water_consumed or 0.0,
                log.actual_avg_weight or 0.0,
                log.expected_avg_weight or 0.0,
                log.variance_weight or 0.0,
                log.light_hours or 0.0,
                log.light_period or '',
                log.vaccine_name or '',
                med_str,
                remark_str,
                log.remarks or '',
                log.store_items_received or '',
                log.farm_activities or '',
                log.farm_observations or '',
                dict(log._fields['state'].selection).get(log.state, log.state or 'Draft'),
            ]

            for col_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = data_font
                cell.border = border_thin
                if row_fill.fill_type:
                    cell.fill = row_fill

                # Number formatting
                if col_idx in (10, 12):  # Percentage columns
                    cell.number_format = '0.00%'
                    cell.alignment = Alignment(horizontal='right')
                elif col_idx in (7, 8, 9, 11, 14):  # Integer columns
                    cell.number_format = '#,##0'
                    cell.alignment = Alignment(horizontal='right')
                elif col_idx in (15, 16, 17, 18, 19, 20, 21, 22, 23):  # Float columns
                    cell.number_format = '#,##0.00'
                    cell.alignment = Alignment(horizontal='right')
                elif col_idx in (1, 2, 3, 32):  # IDs, Date & Status
                    cell.alignment = Alignment(horizontal='center')
                else:
                    cell.alignment = Alignment(horizontal='left')

        # Set Column Widths
        for col_idx, (_, col_width) in enumerate(headers, start=1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = col_width

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    # =========================================================================
    # CSV EXPORT BUILDER
    # =========================================================================
    def _generate_csv_export(self, logs):
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        headers = [
            "Log ID", "Flock ID", "Date", "Flock", "Pen Location", "Farm", "Age Days",
            "Start Birds", "Mortality", "Daily Mort %", "Cumm Mortality", "Cumm Mort %",
            "Feed Type", "Feed Bags", "Feed Consumed (g)", "Feed / Bird (g)", "Expected Feed (g)", "Feed Var (g)",
            "Water (L)", "Actual Avg Wgt (g)", "Expected Avg Wgt (g)", "Wgt Var (g)",
            "Light (Hrs)", "Light Period", "Vaccine", "Medications",
            "Remarks / Symptoms", "Notes", "Store Items Received", "Farm Activities", "Farm Observations", "Status"
        ]
        writer.writerow(headers)

        for log in logs:
            med_list = []
            for m in log.medication_line_ids:
                uom_name = m.uom_id.name or ''
                med_list.append(f"{m.product_id.name} ({m.quantity} {uom_name} - {m.administration_route or 'water'})")
            if not med_list and log.medication_product_id:
                med_list.append(f"{log.medication_product_id.name} ({log.medication_qty})")
            med_str = "; ".join(med_list)

            remark_str = ", ".join(log.remark_ids.mapped('name'))

            writer.writerow([
                log.name or '',
                log.flock_id.flock_code or '',
                str(log.date or ''),
                log.flock_id.name or '',
                log.pen_id.name or '',
                log.farm_id.name or '',
                log.age_day or 0,
                log.birds_count or 0,
                log.mortality or 0,
                f"{(log.daily_mortality_percent or 0.0) * 100:.2f}%",
                log.cumm_mortality or 0,
                f"{(log.cumm_mortality_percent or 0.0) * 100:.2f}%",
                log.feed_product_id.name or '',
                log.feed_consumed_bags or 0,
                log.feed_consumed_g or 0.0,
                log.feed_per_bird_g or 0.0,
                log.expected_feed_g or 0.0,
                log.variance_feed_g or 0.0,
                log.water_consumed or 0.0,
                log.actual_avg_weight or 0.0,
                log.expected_avg_weight or 0.0,
                log.variance_weight or 0.0,
                log.light_hours or 0.0,
                log.light_period or '',
                log.vaccine_name or '',
                med_str,
                remark_str,
                log.remarks or '',
                log.store_items_received or '',
                log.farm_activities or '',
                log.farm_observations or '',
                log.state or 'draft',
            ])

        return output.getvalue().encode('utf-8-sig')

    # =========================================================================
    # ACTION: DOWNLOAD TEMPLATE
    # =========================================================================
    def action_download_template(self):
        self.ensure_one()
        flock = self.template_flock_id or self.target_flock_id or self.flock_id
        if not flock:
            flock = self.env['taghini.flock'].search([('state', '=', 'active')], limit=1)
            if not flock:
                flock = self.env['taghini.flock'].search([], limit=1)

        flock_name = flock.name if flock else "SAMPLE FLOCK - PEN 1"

        if self.template_format == 'xlsx':
            file_data = self._generate_excel_template(flock_name)
            filename = "Daily_Log_Import_Template.xlsx"
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            file_data = self._generate_csv_template(flock_name)
            filename = "Daily_Log_Import_Template.csv"
            mimetype = 'text/csv'

        b64_data = base64.b64encode(file_data)
        self.write({
            'file_output': b64_data,
            'file_name': filename,
            'step': 'result',
            'result_summary': _("Template generated successfully. Download the file below, populate your daily operational data, and import it back into the system."),
            'error_details': False,
        })

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': b64_data,
            'type': 'binary',
            'mimetype': mimetype,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def _generate_excel_template(self, sample_flock_name):
        wb = openpyxl.Workbook()

        # Sheet 1: Data Entry
        ws = wb.active
        ws.title = "Daily Logs"
        ws.views.sheetView[0].showGridLines = True

        header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        req_fill = PatternFill(start_color='1B4F72', end_color='1B4F72', fill_type='solid')   # Navy for required
        opt_fill = PatternFill(start_color='2874A6', end_color='2874A6', fill_type='solid')   # Teal for optional
        sample_font = Font(name='Calibri', size=10, italic=True, color='5D6D7E')
        border_thin = Border(
            left=Side(style='thin', color='D4D4D4'),
            right=Side(style='thin', color='D4D4D4'),
            top=Side(style='thin', color='D4D4D4'),
            bottom=Side(style='thin', color='D4D4D4')
        )

        headers = [
            ("Date", req_fill, 14),
            ("Flock", req_fill, 34),
            ("Mortality", opt_fill, 12),
            ("Feed Bags", opt_fill, 13),
            ("Water (L)", opt_fill, 13),
            ("Actual Avg Weight (g)", opt_fill, 20),
            ("Light Hours", opt_fill, 13),
            ("Light Period", opt_fill, 16),
            ("Vaccine", opt_fill, 18),
            ("Medication", opt_fill, 22),
            ("Medication Qty", opt_fill, 15),
            ("Medication Route", opt_fill, 17),
            ("Remarks / Symptoms", opt_fill, 26),
            ("Notes", opt_fill, 30),
            ("Store Items Received", opt_fill, 22),
            ("Farm Activities", opt_fill, 24),
            ("Farm Observations", opt_fill, 24),
        ]

        ws.row_dimensions[1].height = 28
        for col_idx, (col_name, fill_color, col_width) in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = header_font
            cell.fill = fill_color
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.border = border_thin
            ws.column_dimensions[get_column_letter(col_idx)].width = col_width

        # Sample rows
        sample_rows = [
            [
                str(date.today()), sample_flock_name, 2, 8, 350.0, 1480.0, 18.0,
                "18:00 - 06:00", "Gumboro", "Oxytetracycline", 2.0, "water",
                "Normal", "Morning inspection completed; flock vigorous and active.",
                "8 bags Starter Feed", "Feed distributed, water lines flushed", "Litter dry and clean"
            ],
            [
                str(date.today()), sample_flock_name, 0, 8, 360.0, 1510.0, 18.0,
                "18:00 - 06:00", "", "", 0.0, "water",
                "", "Evening routine normal, house temperature 24°C.",
                "", "Weight sampling 50 birds", "No coughing or abnormal signs"
            ],
        ]

        for row_idx, srow in enumerate(sample_rows, start=2):
            ws.row_dimensions[row_idx].height = 20
            for col_idx, val in enumerate(srow, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = sample_font
                cell.border = border_thin

        # Sheet 2: Field Instructions & Guide
        ws_info = wb.create_sheet(title="Instructions & Field Guide")
        ws_info.views.sheetView[0].showGridLines = True
        ws_info.column_dimensions['A'].width = 24
        ws_info.column_dimensions['B'].width = 16
        ws_info.column_dimensions['C'].width = 65

        info_header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        info_header_fill = PatternFill(start_color='1B4F72', end_color='1B4F72', fill_type='solid')

        info_headers = ["Field Name", "Required?", "Description & Guidance"]
        ws_info.row_dimensions[1].height = 26
        for col_idx, name in enumerate(info_headers, start=1):
            cell = ws_info.cell(row=1, column=col_idx, value=name)
            cell.font = info_header_font
            cell.fill = info_header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')

        guidelines = [
            ("Date", "YES", "Format: YYYY-MM-DD (e.g. 2026-11-18) or Excel date format."),
            ("Flock", "Conditional", "Exact flock / batch name. If left blank, uses the Default Flock selected on the import wizard."),
            ("Mortality", "Optional", "Integer number of dead birds removed from pen today (default: 0). Automatically updates cumulative mortality % and creates scrap moves when posted."),
            ("Feed Bags", "Optional", "Integer count of 25kg bags consumed (e.g. 8). Feed grams (Bags * 25,000g), feed/bird, breed curve expectations, and variances are computed automatically."),
            ("Water (L)", "Optional", "Total liters of water consumed by the flock today."),
            ("Actual Avg Weight (g)", "Optional", "Average bird sample weight in grams (e.g. 1450.0). Variance against breed standard curve is computed automatically."),
            ("Light Hours", "Optional", "Lighting duration in hours (e.g. 18.0)."),
            ("Light Period", "Optional", "Lighting window text (e.g. 18:00 - 06:00)."),
            ("Vaccine", "Optional", "Vaccination administered today (e.g. Gumboro, Lasota, Newcastle)."),
            ("Medication", "Optional", "Name of medication / supplement administered. Automatically matched against product catalog."),
            ("Medication Qty", "Optional", "Dose quantity given (e.g. 2.0)."),
            ("Medication Route", "Optional", "One of: water, feed, injection, spray, oral, other. Defaults to 'water'."),
            ("Remarks / Symptoms", "Optional", "Standard clinical observations or symptoms. Separate multiple items with comma (e.g. 'Coughing, Wet Litter'). If an item requires veterinary escalation, the assigned vet is automatically alerted."),
            ("Notes", "Optional", "Free-form clinical observations or incident report text."),
            ("Store Items Received", "Optional", "List of feed, consumables, or store requisitions received into the pen."),
            ("Farm Activities", "Optional", "Description of maintenance, cleaning, sorting, or vaccination work performed."),
            ("Farm Observations", "Optional", "Housing condition, temperature, ventilation, and flock behavior."),
        ]

        for row_idx, (fname, freq, fdesc) in enumerate(guidelines, start=2):
            ws_info.row_dimensions[row_idx].height = 20
            c1 = ws_info.cell(row=row_idx, column=1, value=fname)
            c2 = ws_info.cell(row=row_idx, column=2, value=freq)
            c3 = ws_info.cell(row=row_idx, column=3, value=fdesc)
            for c in (c1, c2, c3):
                c.font = Font(name='Calibri', size=10)
                c.border = border_thin
            c1.font = Font(name='Calibri', size=10, bold=True)
            c2.alignment = Alignment(horizontal='center')

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    def _generate_csv_template(self, sample_flock_name):
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        headers = [
            "Date", "Flock", "Mortality", "Feed Bags", "Water (L)",
            "Actual Avg Weight (g)", "Light Hours", "Light Period",
            "Vaccine", "Medication", "Medication Qty", "Medication Route",
            "Remarks / Symptoms", "Notes", "Store Items Received", "Farm Activities", "Farm Observations"
        ]
        writer.writerow(headers)

        writer.writerow([
            str(date.today()), sample_flock_name, 2, 8, 350.0, 1480.0, 18.0,
            "18:00 - 06:00", "Gumboro", "Oxytetracycline", 2.0, "water",
            "Normal", "Morning inspection completed; flock active.",
            "8 bags Starter Feed", "Feed distributed, water lines checked", "Litter clean and dry"
        ])

        return output.getvalue().encode('utf-8-sig')

    # =========================================================================
    # ACTION: IMPORT DAILY LOGS
    # =========================================================================
    def action_import(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_("Please select an Excel (.xlsx) or CSV (.csv) file to import."))

        filename = (self.import_filename or '').lower()
        file_bytes = base64.b64decode(self.import_file)

        rows = []
        if filename.endswith('.csv'):
            rows = self._parse_csv_file(file_bytes)
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            rows = self._parse_excel_file(file_bytes)
        else:
            # Auto-detect format by attempting openpyxl first, then CSV
            try:
                rows = self._parse_excel_file(file_bytes)
            except Exception:
                try:
                    rows = self._parse_csv_file(file_bytes)
                except Exception as e:
                    raise UserError(_("Unable to determine file format. Please upload a valid .xlsx or .csv file: %s") % str(e))

        if not rows:
            raise UserError(_("The uploaded file contains no data rows to import."))

        result = self._process_import_rows(rows)
        self.write({
            'step': 'result',
            'result_summary': result['summary'],
            'error_details': result['error_log'],
            'file_output': False,
            'file_name': False,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # =========================================================================
    # FILE PARSERS
    # =========================================================================
    def _parse_csv_file(self, file_bytes):
        # Decode trying common encodings
        content = None
        for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
            try:
                content = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            raise UserError(_("Could not decode the CSV file. Please save it with UTF-8 encoding."))

        # Detect delimiter (comma, semicolon, or tab)
        sample = content[:2048]
        delimiter = ','
        if ';' in sample and sample.count(';') > sample.count(','):
            delimiter = ';'
        elif '\t' in sample and sample.count('\t') > sample.count(','):
            delimiter = '\t'

        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        raw_rows = [row for row in reader if any(field.strip() for field in row)]
        if not raw_rows:
            return []

        header_row = raw_rows[0]
        data_rows = raw_rows[1:]

        # Map headers
        header_map = self._map_headers(header_row)

        parsed_rows = []
        for row_idx, r in enumerate(data_rows, start=2):
            row_dict = {}
            for col_idx, val in enumerate(r):
                if col_idx in header_map:
                    row_dict[header_map[col_idx]] = val.strip() if isinstance(val, str) else val
            parsed_rows.append((row_idx, row_dict))

        return parsed_rows

    def _parse_excel_file(self, file_bytes):
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        # Select first sheet or sheet titled 'Daily Logs'
        ws = wb['Daily Logs'] if 'Daily Logs' in wb.sheetnames else wb.active

        raw_rows = []
        for row in ws.iter_rows(values_only=True):
            if any(cell is not None and str(cell).strip() != '' for cell in row):
                raw_rows.append(list(row))

        if not raw_rows:
            return []

        header_row = raw_rows[0]
        data_rows = raw_rows[1:]
        header_map = self._map_headers(header_row)

        parsed_rows = []
        for row_idx, r in enumerate(data_rows, start=2):
            row_dict = {}
            for col_idx, val in enumerate(r):
                if col_idx in header_map:
                    row_dict[header_map[col_idx]] = val
            parsed_rows.append((row_idx, row_dict))

        return parsed_rows

    def _map_headers(self, header_row):
        """Maps varying user column names to standardized dictionary keys."""
        mapping = {}
        canonical = {
            'logid': 'log_name',
            'log_id': 'log_name',
            'flockid': 'flock_code',
            'flock_id': 'flock_code',
            'flockcode': 'flock_code',
            'flock_code': 'flock_code',
            'date': 'date',
            'logdate': 'date',
            'log_date': 'date',
            'flock': 'flock',
            'flockname': 'flock',
            'flock_name': 'flock',
            'batch': 'flock',
            'pen_series': 'flock',
            'mortality': 'mortality',
            'dead_birds': 'mortality',
            'dead': 'mortality',
            'feedbags': 'feed_consumed_bags',
            'feed_consumed_bags': 'feed_consumed_bags',
            'feed_bags': 'feed_consumed_bags',
            'bags': 'feed_consumed_bags',
            'water': 'water_consumed',
            'water_consumed': 'water_consumed',
            'water_l': 'water_consumed',
            'waterl': 'water_consumed',
            'actual_avg_weight': 'actual_avg_weight',
            'actualavgweight': 'actual_avg_weight',
            'actualavgweightg': 'actual_avg_weight',
            'avg_weight': 'actual_avg_weight',
            'avgweight': 'actual_avg_weight',
            'weight': 'actual_avg_weight',
            'weight_g': 'actual_avg_weight',
            'weightg': 'actual_avg_weight',
            'light_hours': 'light_hours',
            'lighthours': 'light_hours',
            'light': 'light_hours',
            'light_period': 'light_period',
            'lightperiod': 'light_period',
            'vaccine': 'vaccine_name',
            'vaccine_name': 'vaccine_name',
            'medication': 'medication_product',
            'medication_product': 'medication_product',
            'medicine': 'medication_product',
            'medication_qty': 'medication_qty',
            'med_qty': 'medication_qty',
            'dose': 'medication_qty',
            'medication_route': 'medication_route',
            'route': 'medication_route',
            'medication_notes': 'medication_notes',
            'remarks': 'remarks_tags',
            'symptoms': 'remarks_tags',
            'notes': 'remarks_text',
            'clinical_notes': 'remarks_text',
            'comments': 'remarks_text',
            'store_items': 'store_items_received',
            'store_items_received': 'store_items_received',
            'farm_activities': 'farm_activities',
            'activities': 'farm_activities',
            'farm_observations': 'farm_observations',
            'observations': 'farm_observations',
        }

        for col_idx, col_name in enumerate(header_row):
            if not col_name:
                continue
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', str(col_name)).lower()
            if cleaned in canonical:
                mapping[col_idx] = canonical[cleaned]
            else:
                # Fuzzy partial matching
                for key, target in canonical.items():
                    if key in cleaned:
                        mapping[col_idx] = target
                        break

        return mapping

    # =========================================================================
    # IMPORT PROCESSING ENGINE
    # =========================================================================
    def _process_import_rows(self, rows):
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []

        flock_cache = {}
        product_cache = {}
        remark_cache = {}

        processed_logs = self.env['taghini.daily.log']

        for row_idx, data in rows:
            # 1. Parse Date
            raw_date = data.get('date')
            parsed_date = self._parse_date(raw_date)
            if not parsed_date:
                errors.append(_("Row %d: Missing or invalid Date '%s'. Expected format YYYY-MM-DD.") % (row_idx, str(raw_date)))
                continue

            # 2. Resolve Flock
            raw_flock = data.get('flock')
            raw_flock_code = data.get('flock_code')
            flock = None

            if raw_flock_code:
                code_str = str(raw_flock_code).strip()
                if code_str in flock_cache:
                    flock = flock_cache[code_str]
                else:
                    flock = self.env['taghini.flock'].search([('flock_code', '=ilike', code_str)], limit=1)
                    if flock:
                        flock_cache[code_str] = flock

            if not flock and raw_flock:
                flock_str = str(raw_flock).strip()
                if flock_str in flock_cache:
                    flock = flock_cache[flock_str]
                else:
                    # Match exact, flock_code, case-insensitive, or ID
                    flock = self.env['taghini.flock'].search([
                        '|', ('name', '=', flock_str), ('flock_code', '=ilike', flock_str)
                    ], limit=1)
                    if not flock:
                        flock = self.env['taghini.flock'].search([('name', '=ilike', flock_str)], limit=1)
                    if not flock:
                        flock = self.env['taghini.flock'].search([('name', 'ilike', flock_str)], limit=1)
                    if not flock and flock_str.isdigit():
                        flock = self.env['taghini.flock'].browse(int(flock_str)).exists()

                    if flock:
                        flock_cache[flock_str] = flock

            if not flock and self.target_flock_id:
                flock = self.target_flock_id

            if not flock:
                errors.append(_("Row %d: Flock '%s' not found. Please provide a valid flock name or select a Default Flock in the wizard.") % (row_idx, str(raw_flock or '')))
                continue

            # 3. Parse Numerical & Text Values
            try:
                mortality = int(float(data.get('mortality') or 0))
            except (ValueError, TypeError):
                mortality = 0

            try:
                feed_bags = int(float(data.get('feed_consumed_bags') or 0))
            except (ValueError, TypeError):
                feed_bags = 0

            try:
                water_consumed = float(data.get('water_consumed') or 0.0)
            except (ValueError, TypeError):
                water_consumed = 0.0

            try:
                actual_avg_weight = float(data.get('actual_avg_weight') or 0.0)
            except (ValueError, TypeError):
                actual_avg_weight = 0.0

            try:
                light_hours = float(data.get('light_hours') or 0.0)
            except (ValueError, TypeError):
                light_hours = 0.0

            light_period = str(data.get('light_period') or '').strip()
            vaccine_name = str(data.get('vaccine_name') or '').strip()
            remarks_text = str(data.get('remarks_text') or '').strip()
            store_items = str(data.get('store_items_received') or '').strip()
            activities = str(data.get('farm_activities') or '').strip()
            observations = str(data.get('farm_observations') or '').strip()

            # 4. Resolve Standard Remarks / Symptoms (Many2many)
            remark_ids = []
            raw_remarks = data.get('remarks_tags')
            if raw_remarks:
                tag_names = [t.strip() for t in str(raw_remarks).replace(';', ',').split(',') if t.strip()]
                for tag_name in tag_names:
                    if tag_name in remark_cache:
                        r_rec = remark_cache[tag_name]
                    else:
                        r_rec = self.env['taghini.farm.remark'].search([
                            '|', ('name', '=ilike', tag_name), ('code', '=ilike', tag_name)
                        ], limit=1)
                        if not r_rec:
                            r_rec = self.env['taghini.farm.remark'].search([
                                ('name', 'ilike', tag_name)
                            ], limit=1)
                        remark_cache[tag_name] = r_rec
                    if r_rec:
                        remark_ids.append(r_rec.id)

            # 5. Resolve Medication
            med_product_name = data.get('medication_product')
            med_product = None
            if med_product_name:
                p_str = str(med_product_name).strip()
                if p_str in product_cache:
                    med_product = product_cache[p_str]
                else:
                    med_product = self.env['product.product'].search([
                        '|', ('name', '=ilike', p_str), ('default_code', '=ilike', p_str)
                    ], limit=1)
                    if not med_product:
                        med_product = self.env['product.product'].search([
                            ('name', 'ilike', p_str)
                        ], limit=1)
                    product_cache[p_str] = med_product

            try:
                med_qty = float(data.get('medication_qty') or 1.0)
            except (ValueError, TypeError):
                med_qty = 1.0

            med_route = str(data.get('medication_route') or 'water').strip().lower()
            if med_route not in ('water', 'feed', 'injection', 'spray', 'oral', 'other'):
                med_route = 'water'
            med_notes = str(data.get('medication_notes') or '').strip()

            # 6. Check Duplicate
            existing_log = self.env['taghini.daily.log'].search([
                ('flock_id', '=', flock.id),
                ('date', '=', parsed_date),
            ], limit=1)

            if existing_log:
                if self.on_existing == 'skip':
                    skipped_count += 1
                    continue
                elif self.on_existing == 'error':
                    errors.append(_("Row %d: A daily log already exists for flock '%s' on %s.") % (row_idx, flock.name, parsed_date))
                    continue
                elif self.on_existing == 'update':
                    if existing_log.state == 'done':
                        errors.append(_("Row %d: Daily log for flock '%s' on %s is already Posted and cannot be modified.") % (row_idx, flock.name, parsed_date))
                        continue

                    # Update existing record
                    vals = {
                        'mortality': mortality,
                        'feed_consumed_bags': feed_bags,
                        'water_consumed': water_consumed,
                        'actual_avg_weight': actual_avg_weight,
                        'light_hours': light_hours,
                        'light_period': light_period or existing_log.light_period,
                        'vaccine_name': vaccine_name or existing_log.vaccine_name,
                        'remarks': remarks_text or existing_log.remarks,
                        'store_items_received': store_items or existing_log.store_items_received,
                        'farm_activities': activities or existing_log.farm_activities,
                        'farm_observations': observations or existing_log.farm_observations,
                    }
                    if remark_ids:
                        vals['remark_ids'] = [(6, 0, remark_ids)]

                    if med_product:
                        vals['medication_product_id'] = med_product.id
                        vals['medication_qty'] = med_qty
                        # Update or add medication line
                        vals['medication_line_ids'] = [(0, 0, {
                            'product_id': med_product.id,
                            'quantity': med_qty,
                            'administration_route': med_route,
                            'notes': med_notes,
                        })]

                    existing_log.write(vals)
                    updated_count += 1
                    processed_logs |= existing_log
                    continue

            # 7. Create New Record
            vals = {
                'flock_id': flock.id,
                'date': parsed_date,
                'mortality': mortality,
                'feed_consumed_bags': feed_bags,
                'water_consumed': water_consumed,
                'actual_avg_weight': actual_avg_weight,
                'light_hours': light_hours,
                'light_period': light_period,
                'vaccine_name': vaccine_name,
                'remarks': remarks_text,
                'store_items_received': store_items,
                'farm_activities': activities,
                'farm_observations': observations,
                'state': 'draft',
            }

            if remark_ids:
                vals['remark_ids'] = [(6, 0, remark_ids)]

            if med_product:
                vals['medication_product_id'] = med_product.id
                vals['medication_qty'] = med_qty
                vals['medication_line_ids'] = [(0, 0, {
                    'product_id': med_product.id,
                    'quantity': med_qty,
                    'administration_route': med_route,
                    'notes': med_notes,
                })]

            try:
                new_log = self.env['taghini.daily.log'].create(vals)
                created_count += 1
                processed_logs |= new_log
            except Exception as e:
                errors.append(_("Row %d: Failed to create log - %s") % (row_idx, str(e)))

        # 8. Auto-Post Stock Moves if Requested
        posted_count = 0
        post_errors = []
        if self.auto_post and processed_logs:
            for log in processed_logs.filtered(lambda l: l.state == 'draft'):
                try:
                    log.action_post_log()
                    posted_count += 1
                except Exception as e:
                    post_errors.append(f"Log ID {log.id} ({log.flock_id.name} - {log.date}): {str(e)}")

        # 9. Format Summary & Diagnostics
        summary_lines = [
            _("✅ Import Process Completed"),
            _("• Total Rows Read: %d") % len(rows),
            _("• Records Created: %d") % created_count,
            _("• Records Updated: %d") % updated_count,
            _("• Records Skipped: %d") % skipped_count,
            _("• Errors / Warnings: %d") % len(errors),
        ]
        if self.auto_post:
            summary_lines.append(_("• Stock Scraps & Moves Posted: %d") % posted_count)
            if post_errors:
                summary_lines.append(_("• Auto-Post Warnings: %d") % len(post_errors))

        error_log = ""
        if errors or post_errors:
            error_sections = []
            if errors:
                error_sections.append("=== ROW VALIDATION ERRORS ===\n" + "\n".join(errors))
            if post_errors:
                error_sections.append("=== AUTO-POST STOCK WARNINGS ===\n" + "\n".join(post_errors))
            error_log = "\n\n".join(error_sections)

        return {
            'summary': "\n".join(summary_lines),
            'error_log': error_log,
        }

    def _parse_date(self, raw_val):
        """Converts raw excel/csv values to YYYY-MM-DD string."""
        if not raw_val:
            return None
        if isinstance(raw_val, (date, datetime)):
            return raw_val.strftime('%Y-%m-%d')

        val_str = str(raw_val).strip()
        if not val_str:
            return None

        # Standard formats
        formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%d-%m-%Y',
            '%Y/%m/%d',
            '%d.%m.%Y',
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue

        # Check ISO date pattern YYYY-MM-DD
        m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', val_str)
        if m:
            y, month, d = m.groups()
            return f"{int(y):04d}-{int(month):02d}-{int(d):02d}"

        return None

    # =========================================================================
    # RESET WIZARD
    # =========================================================================
    def action_reset(self):
        self.write({
            'step': 'config',
            'file_output': False,
            'file_name': False,
            'result_summary': False,
            'error_details': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

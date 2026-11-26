import math
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AbattoirBagging(models.Model):
    """
    Bagging process: groups abattoir output lines into physical bags,
    validates them against the Taghini Foods Grading Checklist, and
    moves them to Freezer / Cold Room locations.
    """
    _name = 'taghini.abattoir.bagging'
    _description = 'Abattoir Bagging & Freezer Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Bagging Reference', required=True,
                       copy=False, readonly=True, default='New')
    date = fields.Date(string='Bagging Date', default=fields.Date.context_today, required=True)

    batch_id = fields.Many2one(
        'taghini.abattoir.batch', string='Production Batch',
        required=True, ondelete='cascade',
        domain=[('state', 'in', ['production', 'done'])],
        help="The abattoir production batch this bagging is derived from."
    )
    farm_id = fields.Many2one(
        'taghini.farm', string='Farm',
        related='batch_id.farm_id', store=True, readonly=True
    )
    abattoir_id = fields.Many2one(
        'taghini.abattoir', string='Abattoir',
        related='batch_id.abattoir_id', store=True, readonly=True
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        related='batch_id.company_id', store=True, readonly=True
    )

    # --- SEQUENTIAL HARVEST & PRODUCTION DETAILS ---
    harvest_id = fields.Many2one(
        'taghini.harvest', string='Source Harvest',
        related='batch_id.harvest_id', store=True, readonly=True
    )
    flock_id = fields.Many2one(
        'taghini.flock', string='Broiler Flock',
        related='harvest_id.flock_id', store=True, readonly=True
    )
    breeder_flock_id = fields.Many2one(
        'taghini.breeder.flock', string='Breeder Flock',
        related='harvest_id.breeder_flock_id', store=True, readonly=True
    )
    pen_id = fields.Many2one(
        'taghini.pen', string='Source Pen',
        related='harvest_id.pen_id', store=True, readonly=True
    )
    birds_received = fields.Integer(
        string='Birds Received (Harvest)',
        related='harvest_id.birds_received', store=True, readonly=True
    )
    total_live_weight = fields.Float(
        string='Harvest Live Weight (Kg)',
        related='harvest_id.total_live_weight', store=True, readonly=True
    )
    production_output_weight_kg = fields.Float(
        string='Production Output (Kg)',
        related='batch_id.total_output_weight_kg', store=True, readonly=True
    )
    visual_quality = fields.Selection(
        related='harvest_id.visual_quality', string='Harvest Visual Quality', readonly=True
    )
    feather_condition = fields.Selection(
        related='harvest_id.feather_condition', string='Feather Condition', readonly=True
    )
    harvest_notes = fields.Text(
        related='harvest_id.notes', string='Harvest Notes', readonly=True
    )
    packaging_supervisor_id = fields.Many2one(
        'res.users', string='Packaging/Cold Room Supervisor',
        related='batch_id.packaging_supervisor_id', store=True, readonly=True
    )
    qa_shopfloor_id = fields.Many2one(
        'res.users', string='QA on Shopfloor',
        related='batch_id.qa_shopfloor_id', store=True, readonly=True
    )

    # --- TAGHINI GRADING CHECKLIST CONFIG ---
    checklist_id = fields.Many2one(
        'taghini.grading.checklist', string='Grading Checklist Standard',
        default=lambda self: self._get_default_checklist(),
        help="Grading specification used to validate pieces-per-bag and weight ranges."
    )
    checklist_notice = fields.Text(
        string='Notice', related='checklist_id.notice', readonly=True
    )

    # Header-level destination location
    destination_location_id = fields.Many2one(
        'stock.location', string='Destination (Cold Room / Freezer)',
        domain="[('usage', '=', 'internal')]",
        help="Destination location for all bagged goods. Auto-filled from the Abattoir's Freezer/Storage location."
    )

    line_ids = fields.One2many(
        'taghini.abattoir.bagging.line', 'bagging_id', string='Bagging Lines'
    )

    # QA Temperature readings
    qa_temp_line_ids = fields.One2many(
        'taghini.abattoir.bagging.qa', 'bagging_id', string='QA Temperature Readings'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Bags Confirmed'),
        ('moved', 'Moved to Freezer/Cold Room'),
    ], string='Bagging Status', default='draft', tracking=True)

    total_bags = fields.Integer(
        string='Total Bags', compute='_compute_totals', store=True
    )
    total_expected_bags = fields.Integer(
        string='Total Expected Bags', compute='_compute_totals', store=True
    )
    total_bag_difference = fields.Integer(
        string='Bag Difference', compute='_compute_totals', store=True
    )
    total_weight_kg = fields.Float(
        string='Total Weight (Kg)', compute='_compute_totals', store=True
    )

    # Grading Compliance & Exception Tracking
    has_penalty_risk = fields.Boolean(
        string='Has Penalty Risk', compute='_compute_grading_compliance', store=True,
        help="Flagged True if any bagging line violates the Taghini Grading Checklist."
    )
    non_compliant_count = fields.Integer(
        string='Out of Spec Lines', compute='_compute_grading_compliance', store=True
    )
    compliance_summary = fields.Char(
        string='Grading Compliance', compute='_compute_grading_compliance', store=True
    )

    @api.model
    def _get_default_checklist(self):
        default_std = self.env['taghini.grading.checklist'].search([('is_default', '=', True)], limit=1)
        if not default_std:
            default_std = self.env['taghini.grading.checklist'].search([], limit=1)
        return default_std

    @api.depends('line_ids.no_bags', 'line_ids.expected_bags', 'line_ids.bag_difference', 'line_ids.weight_kg')
    def _compute_totals(self):
        for rec in self:
            rec.total_bags = sum(rec.line_ids.mapped('no_bags'))
            rec.total_expected_bags = sum(rec.line_ids.mapped('expected_bags'))
            rec.total_bag_difference = sum(rec.line_ids.mapped('bag_difference'))
            rec.total_weight_kg = sum(rec.line_ids.mapped('weight_kg'))

    @api.depends('line_ids.penalty_risk', 'line_ids.compliance_status')
    def _compute_grading_compliance(self):
        for rec in self:
            bad_lines = rec.line_ids.filtered(lambda l: l.penalty_risk)
            rec.has_penalty_risk = bool(bad_lines)
            rec.non_compliant_count = len(bad_lines)
            if not rec.line_ids:
                rec.compliance_summary = "No Lines"
            elif not bad_lines:
                rec.compliance_summary = "100% Compliant (All Bags Within Taghini Specs)"
            else:
                rec.compliance_summary = f"{len(bad_lines)} line(s) out of specification - Exception / Penalty Risk!"

    def _get_default_destination_location(self, batch):
        if not batch:
            return False
        farm = batch.farm_id
        abattoir = batch.abattoir_id or (farm.default_abattoir_id if farm else False)
        return (
            (abattoir.freezer_location_id if abattoir else False)
            or (abattoir.storage_location_id if abattoir else False)
            or (batch.harvest_id.flock_id.standard_id.storage_location_id if batch.harvest_id.flock_id else False)
        )

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        """When user selects a Production Batch in Bagging, auto-populate destination and lines."""
        for rec in self:
            if rec.batch_id:
                if not rec.destination_location_id:
                    rec.destination_location_id = rec._get_default_destination_location(rec.batch_id)
                if not rec.line_ids and rec.batch_id.line_ids:
                    rec.line_ids = [
                        (0, 0, {
                            'product_id': l.product_id.id,
                            'quantity': l.quantity,
                            'weight_kg': l.weight_kg,
                            'no_bags': 0,
                        })
                        for l in rec.batch_id.line_ids
                    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('taghini.bagging') or 'New'
            if not vals.get('destination_location_id') and vals.get('batch_id'):
                batch = self.env['taghini.abattoir.batch'].browse(vals['batch_id'])
                dest = self._get_default_destination_location(batch)
                if dest:
                    vals['destination_location_id'] = dest.id
        records = super().create(vals_list)
        for rec in records:
            if rec.batch_id and not rec.batch_id.bagging_id:
                rec.batch_id.bagging_id = rec.id
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'batch_id' in vals:
            for rec in self:
                if rec.batch_id and not rec.batch_id.bagging_id:
                    rec.batch_id.bagging_id = rec.id
        return res

    def unlink(self):
        for rec in self:
            if rec.state == 'moved':
                raise UserError(_("You cannot delete a Bagging record that has already been moved to Freezer/Cold Room."))
        return super().unlink()

    def action_auto_fill_bags(self):
        """Auto-populates 'Actual Bags' from Expected Bags based on the Grading Checklist."""
        self.ensure_one()
        for line in self.line_ids:
            if line.expected_bags > 0:
                line.no_bags = line.expected_bags
            elif line.quantity and not line.no_bags:
                line.no_bags = int(math.ceil(line.quantity / 20.0))

    def action_confirm_bagging(self):
        """Confirm bagging lines - bags are ready for freezer."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Please add at least one bagging line before confirming."))

        unbagged = self.line_ids.filtered(lambda l: l.no_bags <= 0)
        if unbagged:
            names = ", ".join(unbagged.mapped('product_id.name'))
            raise UserError(_("Please specify the 'Actual Bags' for: %s") % names)

        if self.has_penalty_risk:
            bad_lines = self.line_ids.filtered(lambda l: l.penalty_risk)
            details = "<br/>".join([
                f"• <b>{l.product_id.name}</b>: {l.compliance_notes}"
                for l in bad_lines
            ])
            body = _(
                "<b>⚠️ Taghini Grading Checklist Non-Compliance Alert</b><br/>"
                "The following bagging lines deviate from the official grading checklist:<br/>"
                "%(details)s<br/>"
                "<i>NB: The above information must be strictly adhered to, failure to do so would attract penalty.</i>"
            ) % {'details': details}
            self.message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )

        self.state = 'confirmed'

    def action_move_to_freezer(self):
        """
        Move bagged goods to the destination location (Freezer / Cold Room).
        Requires Production Batch to be posted to stock first; skips self-transfers.
        """
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_("Please confirm the bagging first."))
        if self.batch_id.state != 'done':
            raise UserError(_("Please 'Post to Stock' on the Production Batch before moving bagged goods to Freezer/Cold Room."))

        farm = self.batch_id.farm_id
        abattoir = self.abattoir_id or (farm.default_abattoir_id if farm else False)
        source_storage = (
            abattoir.storage_location_id if abattoir else False
        )
        dest = self.destination_location_id or self._get_default_destination_location(self.batch_id)
        if not dest:
            raise UserError(_(
                "No destination location set. Set 'Destination (Cold Room / Freezer)' on this bagging record "
                "or configure Storage/Freezer locations on the Abattoir."
            ))

        production_loc = self.env['stock.location'].search([
            ('usage', '=', 'production'),
            ('company_id', 'in', [self.company_id.id, False])
        ], limit=1)

        source_loc = source_storage or production_loc
        if not source_loc:
            raise UserError(_("Could not find a source Storage or Virtual Production location."))

        stock_move_obj = self.env['stock.move']
        moved_count = 0

        if source_loc.id != dest.id:
            for line in self.line_ids:
                qty = line.weight_kg if self._is_weight_uom(line.product_id.uom_id) else line.quantity
                if qty <= 0:
                    continue

                move = stock_move_obj.sudo().create({
                    'name': f"{self.name} → {dest.name}",
                    'product_id': line.product_id.product_variant_id.id,
                    'product_uom_qty': qty,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': source_loc.id,
                    'location_dest_id': dest.id,
                    'date': fields.Datetime.now(),
                    'company_id': self.company_id.id,
                    'origin': self.name,
                    'state': 'draft',
                })
                move._action_confirm()
                move._action_assign()
                if not move.move_line_ids:
                    self.env['stock.move.line'].sudo().create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'quantity': qty,
                    })
                else:
                    for ml in move.move_line_ids:
                        ml.quantity = ml.quantity_product_uom
                move.picked = True
                move._action_done()
                moved_count += 1

        self.state = 'moved'
        msg = (
            f'{self.total_bags} bags ({self.total_weight_kg:.2f} Kg) transferred to {dest.name}.'
            if moved_count
            else f'{self.total_bags} bags ({self.total_weight_kg:.2f} Kg) confirmed in {dest.name} (already in destination location).'
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Moved to Freezer / Cold Room'),
                'message': msg,
                'type': 'success',
                'sticky': False,
            }
        }

    def _is_weight_uom(self, uom):
        if not uom:
            return False
        if hasattr(uom, 'category_id') and uom.category_id:
            if uom.category_id.name.lower() in ['weight', 'poids', 'mass', 'gewicht']:
                return True
        if uom.name and any(w in uom.name.lower() for w in ['kg', 'gram', 'lb', 'oz']):
            return True
        return False


class AbattoirBaggingLine(models.Model):
    """
    One line per product in the bagging process.
    Auto-populated from AbattoirLine and validated against Taghini Grading Checklist.
    """
    _name = 'taghini.abattoir.bagging.line'
    _description = 'Bagging Line'

    bagging_id = fields.Many2one('taghini.abattoir.bagging', string='Bagging', ondelete='cascade')
    checklist_id = fields.Many2one(
        'taghini.grading.checklist', related='bagging_id.checklist_id', readonly=True
    )

    product_id = fields.Many2one('product.template', string='Product', required=True)
    category_type = fields.Selection(
        related='product_id.abattoir_type', string='Category', store=True, readonly=True
    )
    quantity = fields.Integer(string='Pieces / Birds')
    weight_kg = fields.Float(string='Total Weight (Kg)')
    avg_unit_weight = fields.Float(string='Avg Unit Wgt (Kg)', compute='_compute_avg_unit', store=True)

    # --- TAGHINI GRADING CHECKLIST INTEGRATION ---
    grading_line_id = fields.Many2one(
        'taghini.grading.checklist.line', string='Grading Series Spec',
        compute='_compute_grading_line', store=True, readonly=False,
        help="Matched series from Taghini Grading Checklist."
    )
    pieces_per_bag_spec = fields.Integer(
        string='Pieces/Bag Spec', related='grading_line_id.pieces_per_bag', readonly=True
    )
    expected_range_display = fields.Char(
        string='Expected Sack Wgt Range', related='grading_line_id.display_range', readonly=True
    )
    expected_bags = fields.Integer(
        string='Expected Bags', compute='_compute_grading_metrics', store=True,
        help="Calculated: ceil(Pieces / Pieces-Per-Bag Spec)"
    )

    no_bags = fields.Integer(string='Actual Bags (Sacks)')

    bag_difference = fields.Integer(
        string='Difference (Act - Exp)', compute='_compute_grading_metrics', store=True,
        help="Actual Bags minus Expected Bags."
    )
    avg_bag_weight = fields.Float(
        string='Avg Bag Wgt (Kg)', compute='_compute_grading_metrics', store=True,
        help="Calculated: Total Weight / Actual Bags"
    )

    compliance_status = fields.Selection([
        ('compliant', 'Compliant'),
        ('underweight', 'Underweight Bag (Below Spec)'),
        ('overweight', 'Overweight Bag (Above Spec)'),
        ('pieces_mismatch', 'Pieces / Bag Count Mismatch'),
        ('na', 'No Spec / General Parts'),
    ], string='Grading Status', compute='_compute_grading_metrics', store=True)

    penalty_risk = fields.Boolean(
        string='Penalty Risk', compute='_compute_grading_metrics', store=True
    )
    compliance_notes = fields.Char(
        string='Compliance Details', compute='_compute_grading_metrics', store=True
    )

    @api.depends('quantity', 'weight_kg')
    def _compute_avg_unit(self):
        for line in self:
            line.avg_unit_weight = (line.weight_kg / line.quantity) if line.quantity else 0.0

    @api.depends('product_id', 'product_id.grading_line_id', 'bagging_id.checklist_id', 'avg_unit_weight')
    def _compute_grading_line(self):
        for line in self:
            if line.product_id.grading_line_id:
                line.grading_line_id = line.product_id.grading_line_id
                continue

            checklist = line.bagging_id.checklist_id or self.env['taghini.grading.checklist'].search([('is_default', '=', True)], limit=1)
            if not checklist:
                line.grading_line_id = False
                continue

            matched = False
            prod_name = (line.product_id.name or '').lower()

            if 'head' in prod_name and 'leg' in prod_name:
                matched = checklist.line_ids.filtered(lambda l: l.is_head_and_leg)[:1]

            if not matched:
                for cl_line in checklist.line_ids:
                    cl_key = (cl_line.name or '').split('/')[0].strip().lower()
                    if cl_key and cl_key in prod_name:
                        matched = cl_line
                        break

            if not matched and line.avg_unit_weight > 0 and line.category_type in ('series', 'cuts'):
                for cl_line in checklist.line_ids:
                    if cl_line.unit_weight_min <= line.avg_unit_weight <= cl_line.unit_weight_max:
                        matched = cl_line
                        break

            line.grading_line_id = matched or False

    @api.depends('quantity', 'weight_kg', 'no_bags', 'grading_line_id',
                 'grading_line_id.pieces_per_bag', 'grading_line_id.expected_bag_weight_min',
                 'grading_line_id.expected_bag_weight_max')
    def _compute_grading_metrics(self):
        for line in self:
            spec_pcs = line.grading_line_id.pieces_per_bag if line.grading_line_id else 0
            if spec_pcs > 0 and line.quantity > 0:
                line.expected_bags = int(math.ceil(line.quantity / spec_pcs))
            else:
                line.expected_bags = 0

            line.bag_difference = (line.no_bags - line.expected_bags) if (line.no_bags > 0 and line.expected_bags > 0) else 0
            line.avg_bag_weight = round(line.weight_kg / line.no_bags, 2) if line.no_bags > 0 else 0.0

            if not line.grading_line_id:
                line.compliance_status = 'na'
                line.penalty_risk = False
                line.compliance_notes = 'No grading rule assigned'
                continue

            spec = line.grading_line_id
            if line.no_bags <= 0:
                line.compliance_status = 'na'
                line.penalty_risk = False
                line.compliance_notes = f"Target: {spec.pieces_per_bag} pcs/bag | Exp: {spec.display_range or ''}"
                continue

            pcs_mismatch = False
            actual_pcs_per_bag = 0.0
            if line.quantity > 0 and spec_pcs > 0:
                actual_pcs_per_bag = line.quantity / line.no_bags
                if abs(actual_pcs_per_bag - spec_pcs) > 1.5:
                    pcs_mismatch = True

            min_wgt = spec.expected_bag_weight_min
            max_wgt = spec.expected_bag_weight_max
            avg_w = line.avg_bag_weight

            if min_wgt > 0 and avg_w < (min_wgt - 0.2):
                line.compliance_status = 'underweight'
                line.penalty_risk = True
                line.compliance_notes = (
                    f"Avg {avg_w:.2f} kg/bag is below target {spec.display_range or f'{min_wgt}-{max_wgt} kg'}. Penalty Risk!"
                )
            elif max_wgt > 0 and avg_w > (max_wgt + 0.2):
                line.compliance_status = 'overweight'
                line.penalty_risk = True
                line.compliance_notes = (
                    f"Avg {avg_w:.2f} kg/bag exceeds target {spec.display_range or f'{min_wgt}-{max_wgt} kg'}. Penalty Risk!"
                )
            elif pcs_mismatch:
                line.compliance_status = 'pieces_mismatch'
                line.penalty_risk = True
                line.compliance_notes = (
                    f"Packed {line.no_bags} bags for {line.quantity} pcs (avg {actual_pcs_per_bag:.1f} pcs/bag) vs standard {spec_pcs} pcs/bag. Penalty Risk!"
                )
            else:
                line.compliance_status = 'compliant'
                line.penalty_risk = False
                line.compliance_notes = f"Compliant: {spec_pcs} pcs/bag ({avg_w:.2f} kg/bag within {spec.display_range or 'spec'})"


class AbattoirBaggingQA(models.Model):
    """
    QA Temperature check per product after freezer arrival.
    """
    _name = 'taghini.abattoir.bagging.qa'
    _description = 'Bagging QA Temperature Reading'

    bagging_id = fields.Many2one('taghini.abattoir.bagging', string='Bagging', ondelete='cascade')
    product_id = fields.Many2one('product.template', string='Product', required=True)
    storage_class = fields.Selection([
        ('frozen', 'Frozen (≤ -18°C)'),
        ('chilled', 'Chilled (≤ 4°C)'),
    ], string='Storage Class', default='frozen', required=True)
    temperature_celsius = fields.Float(string='Temperature (°C)', required=True)
    recorded_at = fields.Datetime(string='Recorded At', default=fields.Datetime.now)
    is_within_spec = fields.Boolean(
        string='Within Spec', compute='_compute_spec', store=True,
        help="Flagged True if temperature is ≤ -18°C (frozen) or ≤ 4°C (chilled)."
    )
    notes = fields.Char(string='QA Notes')

    @api.depends('temperature_celsius', 'storage_class')
    def _compute_spec(self):
        for rec in self:
            if rec.storage_class == 'chilled':
                rec.is_within_spec = rec.temperature_celsius <= 4.0
            else:
                rec.is_within_spec = rec.temperature_celsius <= -18.0

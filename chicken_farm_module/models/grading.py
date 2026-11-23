from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TaghiniGradingChecklist(models.Model):
    """
    Master Grading Checklist defining weight series, target pieces per bag,
    and expected bag weight ranges according to Taghini Foods standards.
    """
    _name = 'taghini.grading.checklist'
    _description = 'Taghini Grading Checklist Standard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'is_default desc, name asc'

    name = fields.Char(string='Checklist Name', required=True, tracking=True)
    code = fields.Char(string='Code', default='TF-GRADE-01')
    active = fields.Boolean(default=True)
    is_default = fields.Boolean(
        string='Default Standard', default=False, tracking=True,
        help="If set, this standard is automatically used for bagging validations."
    )
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company
    )

    notice = fields.Text(
        string='Compliance Notice',
        default="NB: The above information must be strictly adhered to, failure to do so would attract penalty.",
        help="Policy notice shown on checklists and bagging screens."
    )

    line_ids = fields.One2many(
        'taghini.grading.checklist.line', 'checklist_id',
        string='Grading Checklist Lines'
    )

    line_count = fields.Integer(string='Series Count', compute='_compute_line_count')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.constrains('is_default')
    def _check_default(self):
        for rec in self:
            if rec.is_default:
                others = self.search([('id', '!=', rec.id), ('is_default', '=', True)])
                if others:
                    others.write({'is_default': False})


class TaghiniGradingChecklistLine(models.Model):
    """
    Individual series weight bracket in Taghini Foods Grading Checklist.
    Example: 1.2 Series (1.20 - 1.29 kg), 20 pieces/bag, expected range 24.00 - 25.80 kg.
    """
    _name = 'taghini.grading.checklist.line'
    _description = 'Grading Checklist Series Line'
    _order = 'sequence asc, unit_weight_min asc'

    checklist_id = fields.Many2one(
        'taghini.grading.checklist', string='Checklist', required=True, ondelete='cascade'
    )
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Series / SKU', required=True, help="e.g. 1.2, 1.2CUT4, 1.4, Head and Leg")
    code = fields.Char(string='Series Code')

    # Unit weight bracket for single bird / piece (Kg)
    unit_weight_min = fields.Float(string='Unit Wgt Min (Kg)', digits=(16, 3))
    unit_weight_max = fields.Float(string='Unit Wgt Max (Kg)', digits=(16, 3))

    # Packaging rules
    pieces_per_bag = fields.Integer(
        string='Pieces in Bag (Sack)', required=True, default=20,
        help="Strict piece count per bag (e.g. 20, 15, or 12 pieces)."
    )

    # Expected bag weight range (Kg)
    expected_bag_weight_min = fields.Float(string='Exp Bag Wgt Min (Kg)', digits=(16, 2))
    expected_bag_weight_max = fields.Float(string='Exp Bag Wgt Max (Kg)', digits=(16, 2))
    display_range = fields.Char(
        string='Expected Range Text',
        help="Text formatted range from official sheet, e.g. '24-25 (24.00-25.80)'"
    )

    is_underweight = fields.Boolean(string='Underweight Class', default=False)
    is_head_and_leg = fields.Boolean(
        string='Head and Leg Composite', default=False,
        help="Special composite specification: Head 18kg + Leg 12kg = 20kg/bag."
    )

    notes = fields.Char(string='Notes / Cut variants')

    def name_get(self):
        result = []
        for line in self:
            label = f"{line.name} ({line.pieces_per_bag} pcs/bag | {line.display_range or f'{line.expected_bag_weight_min}-{line.expected_bag_weight_max} kg'})"
            result.append((line.id, label))
        return result

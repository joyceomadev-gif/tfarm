from odoo import models, fields, api

class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    custom_open_count = fields.Integer(
        string='Open Tickets to Handle', 
        compute='_compute_custom_counts'
    )
    custom_unassigned_count = fields.Integer(
        string='Unassigned (to handle)', 
        compute='_compute_custom_counts'
    )
    custom_urgent_count = fields.Integer(
        string='Urgent', 
        compute='_compute_custom_counts'
    )

    def _compute_custom_counts(self):
        for record in self:
            # Base domain excluding stages 13 (Resolved) and 15 (Closed)
            base_domain = [
                ('team_id', '=', record.id),
                ('stage_id', 'not in', [13, 15])
            ]
            
            # .sudo() bypasses user access rights checks [cite: 13, 28]
            record.custom_open_count = self.env['helpdesk.ticket'].sudo().search_count(base_domain)
            
            record.custom_unassigned_count = self.env['helpdesk.ticket'].sudo().search_count(
                base_domain + [('user_id', '=', False)] # Excludes tickets with an assigned employee [cite: 26, 32]
            )
            
            record.custom_urgent_count = self.env['helpdesk.ticket'].sudo().search_count(
                base_domain + [('priority', '=', '3')] # Counts tickets with priority '3' (Urgent) [cite: 39, 42]
            )
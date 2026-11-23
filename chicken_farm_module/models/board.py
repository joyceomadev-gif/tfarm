from odoo import models, api

class TaghiniBoard(models.AbstractModel):
    _inherit = 'board.board'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super().get_view(view_id, view_type, **options)
        if view_type == 'form':
            v_id = view_id or res.get('id')
            if v_id:
                custom_view = self.env['ir.ui.view.custom'].sudo().search([
                    ('user_id', '=', self.env.uid),
                    ('ref_id', '=', v_id)
                ], limit=1)
                if custom_view:
                    res['custom_view_id'] = custom_view.id
        return res

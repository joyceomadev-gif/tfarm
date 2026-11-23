from odoo.addons.web.controllers.view import View
from odoo.http import route, request

class TaghiniView(View):

    @route('/web/view/edit_custom', type='jsonrpc', auth="user")
    def edit_custom(self, custom_id=None, arch='', **kwargs):
        if not custom_id:
            # Fallback: search or create custom view for current user
            custom_view = request.env['ir.ui.view.custom'].sudo().search([
                ('user_id', '=', request.env.uid)
            ], limit=1, order='write_date desc')
            if not custom_view:
                dash_view = request.env.ref('chicken_farm_module.board_taghini_dashboard', raise_if_not_found=False)
                ref_id = dash_view.id if dash_view else False
                custom_view = request.env['ir.ui.view.custom'].sudo().create({
                    'user_id': request.env.uid,
                    'ref_id': ref_id,
                    'arch': arch,
                })
            else:
                custom_view.write({'arch': arch})
            return {'result': True}
        return super().edit_custom(custom_id, arch)

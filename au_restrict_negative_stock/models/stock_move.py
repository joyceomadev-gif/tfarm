from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_round


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        for move in self:
            product = move.product_id

            # Match the Odoo 19 done flow: only validate moves that will really be completed.
            if move.state == 'cancel' or (move.quantity <= 0 and not move.is_inventory) or not move.picked:
                continue

            # Skip non-storable products and configured exceptions.
            if not product.is_storable:
                continue

            if (product.allow_negative_stock or
                product.categ_id.allow_negative_stock or
                move.location_id.allow_negative_stock or
                move.location_dest_id.allow_negative_stock):
                continue

            # Available stock is expressed in the product's default UoM.
            qty_on_hand = product.with_context(location=move.location_id.id).qty_available
            required_qty = move.quantity * move.product_uom.factor / product.uom_id.factor
            required_qty = float_round(required_qty, precision_rounding=product.uom_id.rounding)
            if float_compare(qty_on_hand, required_qty, precision_rounding=product.uom_id.rounding) < 0:
                raise UserError(_(
                    "Operation not allowed!\n\n"
                    "Product: %s\n"
                    "Available: %.2f %s\n"
                    "Required: %.2f %s\n\n"
                    "This move would cause negative stock."
                ) % (
                    product.display_name,
                    qty_on_hand, product.uom_id.name,
                    required_qty, product.uom_id.name
                ))

        return super()._action_done(cancel_backorder=cancel_backorder)

from collections import defaultdict
from odoo import models

from .negative_stock_utils import (
    get_available_quantity,
    get_required_quantity,
    is_negative_stock_allowed,
    is_negative_stock_blocked,
    raise_negative_stock_error,
)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        for picking in self.filtered(lambda stock_picking: stock_picking.picking_type_code == 'outgoing'):
            source_location = picking.location_id

            grouped_moves = defaultdict(float)
            product_by_key = {}
            
            # FIXED: Replaced move_ids_without_package with move_ids
            for move in picking.move_ids.filtered(
                lambda stock_move: stock_move.state != 'cancel'
                and stock_move.quantity > 0
                and stock_move.picked
                and stock_move.product_id.is_storable
                and stock_move.location_id.usage == 'internal'
                and stock_move.location_dest_id.usage != 'internal'
                and not is_negative_stock_allowed(stock_move.product_id, stock_move.location_id)
            ):
                key = (move.product_id.id, source_location.id)
                product_by_key[key] = move.product_id
                grouped_moves[key] += get_required_quantity(move.quantity, move.product_uom, move.product_id.uom_id)

            for key, required_qty in grouped_moves.items():
                product = product_by_key[key]
                qty_on_hand = get_available_quantity(product, source_location)
                if is_negative_stock_blocked(product, source_location, qty_on_hand, required_qty):
                    raise_negative_stock_error(product, qty_on_hand, required_qty)

        return super().button_validate()
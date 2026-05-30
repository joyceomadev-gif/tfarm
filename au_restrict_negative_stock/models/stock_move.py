from collections import defaultdict

from odoo import models

from .negative_stock_utils import (
    get_available_quantity,
    get_required_quantity,
    is_negative_stock_allowed,
    is_negative_stock_blocked,
    raise_negative_stock_error,
)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        outgoing_moves = self.filtered(
            lambda move: move.state != 'cancel'
            and move.quantity > 0
            and move.picked
            and move.product_id.is_storable
            and move.location_id.usage == 'internal'
            and move.location_dest_id.usage != 'internal'
            and not is_negative_stock_allowed(move.product_id, move.location_id)
        )

        grouped_moves = defaultdict(float)
        move_by_key = {}
        for move in outgoing_moves:
            key = (move.location_id.id, move.product_id.id)
            move_by_key[key] = move
            grouped_moves[key] += get_required_quantity(move.quantity, move.product_uom, move.product_id.uom_id)

        for key, required_qty in grouped_moves.items():
            move = move_by_key[key]
            qty_on_hand = get_available_quantity(move.product_id, move.location_id)
            if is_negative_stock_blocked(move.product_id, move.location_id, qty_on_hand, required_qty):
                raise_negative_stock_error(move.product_id, qty_on_hand, required_qty)

        return super()._action_done(cancel_backorder=cancel_backorder)

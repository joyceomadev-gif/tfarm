from collections import defaultdict

from odoo import models

from .negative_stock_utils import (
    get_available_quantity,
    get_required_quantity,
    is_negative_stock_allowed,
    is_negative_stock_blocked,
    raise_negative_stock_error,
)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        for order in self.filtered(lambda sale_order: sale_order.state in ('draft', 'sent')):
            warehouse = order.warehouse_id
            picking_type = warehouse.out_type_id if warehouse else False
            if not picking_type:
                continue

            source_location = picking_type.default_location_src_id or warehouse.lot_stock_id

            if not source_location or picking_type.code != 'outgoing':
                continue

            grouped_lines = defaultdict(float)
            product_by_key = {}
            for line in order.order_line.filtered(lambda sale_line: sale_line.product_id.is_storable):
                product = line.product_id
                if is_negative_stock_allowed(product, source_location):
                    continue

                key = (product.id, source_location.id)
                product_by_key[key] = product
                grouped_lines[key] += get_required_quantity(line.product_uom_qty, line.product_uom, product.uom_id)

            for key, required_qty in grouped_lines.items():
                product = product_by_key[key]
                qty_on_hand = get_available_quantity(product, source_location)
                if is_negative_stock_blocked(product, source_location, qty_on_hand, required_qty):
                    raise_negative_stock_error(product, qty_on_hand, required_qty)

        return super().action_confirm()

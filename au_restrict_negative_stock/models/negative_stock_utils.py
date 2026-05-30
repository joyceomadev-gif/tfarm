from odoo import _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


def is_negative_stock_allowed(product, location):
    return (
        product.allow_negative_stock
        or product.categ_id.allow_negative_stock
        or location.allow_negative_stock
    )


def get_required_quantity(quantity, source_uom, product_uom):
    return quantity * source_uom.factor / product_uom.factor


def get_available_quantity(product, location):
    return product.with_context(location=location.id).qty_available


def raise_negative_stock_error(product, available_qty, required_qty):
    raise UserError(_(
        "Operation not allowed!\n\n"
        "Product: %s\n"
        "Available: %.2f %s\n"
        "Required: %.2f %s\n\n"
        "This move would cause negative stock."
    ) % (
        product.display_name,
        available_qty, product.uom_id.name,
        required_qty, product.uom_id.name,
    ))


def is_negative_stock_blocked(product, location, available_qty, required_qty):
    return (
        not is_negative_stock_allowed(product, location)
        and float_compare(
            available_qty,
            required_qty,
            precision_rounding=product.uom_id.rounding,
        ) < 0
    )

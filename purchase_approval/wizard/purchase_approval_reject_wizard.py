# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PurchaseApprovalRejectWizard(models.TransientModel):
    _name = 'purchase.approval.reject.wizard'
    _description = 'Purchase Order Approval Rejection Wizard'

    order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True,
        readonly=True
    )
    reason = fields.Text(
        string='Rejection Reason',
        required=True,
        help='State clearly why this purchase order approval is being rejected.'
    )

    def action_reject(self):
        """Reject the purchase order approval request and revert RFQ to draft."""
        self.ensure_one()
        if not self.env.user.has_group('purchase_approval.group_purchase_approver'):
            raise UserError(_("Only users with the 'PO Approver' access right can reject this order."))

        order = self.order_id

        order.write({
            'state': 'draft',
            'rejection_reason': self.reason,
        })

        # Silently unlink pending approval activities to prevent duplicate chatter entries
        approval_activities = order.activity_ids.filtered(
            lambda a: 'PO Approval Required' in (a.summary or '')
        )
        approval_activities.unlink()

        # Single clear rejection notice in chatter
        order.message_post(
            body=Markup(
                "<b>Approval Rejected</b> by %s &bull; <b>Reason:</b> %s"
            ) % (self.env.user.name, self.reason),
            subtype_xmlid='mail.mt_comment'
        )

        return {'type': 'ir.actions.act_window_close'}

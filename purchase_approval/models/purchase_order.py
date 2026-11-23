# -*- coding: utf-8 -*-
from markupsafe import Markup
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Clean fields without tracking noise (these are already visible in the Approval Details tab)
    approval_requester_id = fields.Many2one(
        'res.users',
        string='Approval Requested By',
        readonly=True,
        copy=False,
        help='User who requested approval for this purchase order.'
    )
    approval_request_date = fields.Datetime(
        string='Approval Requested On',
        readonly=True,
        copy=False
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        copy=False,
        help='PO Approver who validated this order.'
    )
    approval_date = fields.Datetime(
        string='Approved On',
        readonly=True,
        copy=False
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        readonly=True,
        copy=False
    )
    is_approver = fields.Boolean(
        string='Is Approver',
        compute='_compute_is_approver'
    )
    can_request_approval = fields.Boolean(
        string='Can Request Approval',
        compute='_compute_can_request_approval'
    )

    def _compute_is_approver(self):
        is_approver = self.env.user.has_group('purchase_approval.group_purchase_approver')
        for order in self:
            order.is_approver = is_approver

    def _compute_can_request_approval(self):
        for order in self:
            order.can_request_approval = order.state in ('draft', 'sent') and bool(order.order_line)

    def _get_approval_access_url(self):
        """Return direct URL to view and approve this purchase order in Odoo."""
        self.ensure_one()
        base_url = self.get_base_url()
        return f"{base_url}/odoo/purchase/{self.id}"

    def action_request_approval(self):
        """Transition RFQ to 'to approve' and dispatch notification to PO Approvers."""
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        approver_group = self.env.ref('purchase_approval.group_purchase_approver')
        mail_template = self.env.ref('purchase_approval.email_template_po_approval_request', raise_if_not_found=False)

        for order in self:
            if not order.order_line:
                raise UserError(_("You cannot request approval for an empty order. Please add at least one line."))
            if order.state not in ('draft', 'sent'):
                raise UserError(_("Approval can only be requested when the order is in RFQ or RFQ Sent status."))

            order.write({
                'state': 'to approve',
                'approval_requester_id': self.env.user.id,
                'approval_request_date': fields.Datetime.now(),
                'rejection_reason': False,
            })

            currency_symbol = order.currency_id.symbol or order.currency_id.name or ''

            # Single clean, human-readable log in chatter
            order.message_post(
                body=Markup(
                    "<b>Approval Requested</b> by %s &bull; Total: <b>%s %s</b>"
                ) % (self.env.user.name, f"{order.amount_total:,.2f}", currency_symbol),
                subtype_xmlid='mail.mt_note',
            )

            # Locate active approvers
            group_users = getattr(approver_group, 'all_user_ids', None) or getattr(approver_group, 'user_ids', None) or getattr(approver_group, 'users', self.env['res.users'])
            approvers = group_users.filtered(lambda u: u.active and u.id != self.env.user.id)
            if not approvers:
                approvers = group_users.filtered(lambda u: u.active)

            # Schedule activity and dispatch notification email for approvers
            for approver in approvers:
                # 1. In-app activity
                existing_activity = self.env['mail.activity'].search([
                    ('res_model', '=', 'purchase.order'),
                    ('res_id', '=', order.id),
                    ('user_id', '=', approver.id),
                    ('summary', '=like', 'PO Approval Required%')
                ], limit=1)

                if not existing_activity:
                    order.activity_schedule(
                        activity_type_id=activity_type.id if activity_type else False,
                        summary=_("PO Approval Required: %s") % order.name,
                        note=_(
                            "Approval requested by %s for %s (%s %s). Please review."
                        ) % (
                            self.env.user.name,
                            order.name,
                            f"{order.amount_total:,.2f}",
                            currency_symbol
                        ),
                        user_id=approver.id,
                    )

                # 2. Email notification to approver (safely queued in mail.mail)
                approver_email = approver.email or (approver.partner_id and approver.partner_id.email)
                if mail_template and approver_email:
                    try:
                        mail_template.send_mail(
                            order.id,
                            email_values={
                                'email_to': approver_email,
                                'recipient_ids': [(4, approver.partner_id.id)],
                            },
                            force_send=False,
                        )
                    except Exception:
                        pass
        return True

    def button_approve(self, force=False):
        """Approve order and clean up approval activities without clutter."""
        if not self.env.user.has_group('purchase_approval.group_purchase_approver'):
            raise UserError(_("Only users with the 'PO Approver' access right can approve this order."))

        for order in self:
            order.write({
                'approved_by_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })

            # Silently unlink pending review activities so chatter is not spammed with multiple "To-Do done" entries
            approval_activities = order.activity_ids.filtered(
                lambda a: 'PO Approval Required' in (a.summary or '')
            )
            approval_activities.unlink()

            # Single clear message in chatter
            order.message_post(
                body=Markup("<b>Purchase Order approved</b> by %s.") % self.env.user.name,
                subtype_xmlid='mail.mt_comment'
            )

        return super().button_approve(force=force)

    def button_confirm(self):
        """Require approval before converting RFQ to PO unless confirmed by an Approver."""
        is_approver = self.env.user.has_group('purchase_approval.group_purchase_approver')

        for order in self:
            if order.state in ('draft', 'sent'):
                if not is_approver:
                    raise UserError(_(
                        "Approval is required before creating a Purchase Order. "
                        "Please click 'Request Approval' to submit this RFQ for review."
                    ))
                else:
                    order.write({
                        'approved_by_id': self.env.user.id,
                        'approval_date': fields.Datetime.now(),
                    })
        return super().button_confirm()

    def action_open_reject_wizard(self):
        """Open popup wizard for approver to enter rejection reason."""
        self.ensure_one()
        if not self.env.user.has_group('purchase_approval.group_purchase_approver'):
            raise UserError(_("Only users with the 'PO Approver' access right can reject this order."))
        return {
            'name': _('Reject Purchase Order Approval'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.approval.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
            }
        }

    def button_cancel(self):
        """Clear pending approval activities if order is cancelled."""
        for order in self:
            if order.state == 'to approve':
                approval_activities = order.activity_ids.filtered(
                    lambda a: 'PO Approval Required' in (a.summary or '')
                )
                approval_activities.unlink()
        return super().button_cancel()

    def button_draft(self):
        """Reset approval fields if reset to draft."""
        res = super().button_draft()
        for order in self:
            order.write({
                'approved_by_id': False,
                'approval_date': False,
                'approval_requester_id': False,
                'approval_request_date': False,
            })
        return res

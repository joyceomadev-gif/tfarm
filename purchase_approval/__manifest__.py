# -*- coding: utf-8 -*-
{
    'name': 'Purchase Order Approval Workflow',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Purchase',
    'summary': 'Approval workflow between RFQ and Purchase Order with notifications',
    'description': """
Purchase Order Approval Workflow
=================================
This module introduces a strict approval gate between Request for Quotation (RFQ)
and Purchase Order (PO) creation:

Key Features:
-------------
1. Require Approval: Buyers cannot directly confirm RFQs into Purchase Orders.
   Instead, they click "Request Approval" to move the RFQ to 'To Approve' state.
2. Dedicated PO Approver Access Right: Adds a new security group 'PO Approver'.
   Only authorized approvers (and Purchase Managers) can approve or reject POs.
3. Automated Notifications: When approval is requested, all users with PO Approver
   rights automatically receive an Odoo activity and chatter notification.
4. One-Click Approval & Rejection:
   - Approvers can approve with one click, confirming the PO and logging approval details.
   - Approvers can reject with a mandatory rejection reason via a popup wizard,
     returning the order to Draft and notifying the requester.
5. Audit & Tracking: Automatically records requester, request date, approver,
   approval date, and rejection reason with full chatter audit trail.
6. Search Filters: Pre-configured filters for 'Waiting Approval' and 'My Approval Requests'.
    """,
    'author': 'Custom Development',
    'website': 'https://your-company.com',
    'license': 'LGPL-3',
    'depends': [
        'purchase',
        'purchase_stock',
        'mail',
    ],
    'data': [
        'security/purchase_approval_security.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'wizard/purchase_approval_reject_wizard_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

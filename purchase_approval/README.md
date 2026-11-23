# Purchase Order Approval Workflow (`purchase_approval`)

A lightweight, robust Odoo module that inserts an approval step between **Request for Quotation (RFQ)** and **Purchase Order (PO)**.

---

## Features

1. **Mandatory Approval Before PO Creation**:
   - Buyers can create RFQs, add products, and set prices.
   - Instead of confirming the order directly into a Purchase Order, regular buyers must click **"Request Approval"**.
   - The order enters the **"To Approve"** state.
   - Direct confirmation is blocked for regular users; only users with the **PO Approver** access right can confirm or approve.

2. **Dedicated "PO Approver" Access Right**:
   - A dedicated security group **PO Approver** (`purchase_approval.group_purchase_approver`) is added under the Purchase category.
   - Users with **Purchase / Administrator** (Manager) automatically inherit PO Approver permissions.
   - Individual users can be granted PO Approver rights independently in **Settings > Users & Companies > Users**.

3. **Automated Approver Notifications**:
   - When **"Request Approval"** is clicked, all active users with the **PO Approver** role automatically receive:
     - An Odoo **Activity** (Todo) appearing in their systray clock menu with vendor and amount details.
     - A log entry in the order's **Chatter**.

4. **One-Click Approve & Rejection with Feedback**:
   - **Approve Order**: Validates the PO, converts state to `purchase` (PO), clears pending approval activities, and notifies the requester.
   - **Reject**: Opens a popup wizard prompting for a mandatory rejection reason. Resets the RFQ back to `draft` for revisions and alerts the requester with the reason.

5. **Visual Audit & Search Filters**:
   - Statusbar clearly displays: `RFQ` ➔ `RFQ Sent` ➔ `To Approve` ➔ `Purchase Order`.
   - Dedicated **Approval Details** tab on the purchase order tracking requester, request date, approver, approval date, and rejection reason.
   - Informational status banners at the top of the form for orders awaiting approval or previously rejected.
   - Custom search filters:
     - **Waiting Approval** (`state = 'to approve'`)
     - **My Approval Requests**
     - **Approved by Me**

---

## Installation & Configuration

### 1. Update Apps List
1. In Odoo, activate **Developer Mode** (`Settings > General Settings > Developer Tools`).
2. Go to **Apps > Update Apps List** and click **Update**.
3. Search for `Purchase Order Approval Workflow` (or `purchase_approval`).
4. Click **Activate / Install**.

### 2. Configure User Roles
1. Go to **Settings > Users & Companies > Users**.
2. Open a user profile (e.g., a Finance Director or Purchasing Lead).
3. Under the **Purchase** section, assign:
   - **PO Approver**: To allow reviewing, approving, and rejecting orders awaiting approval.
   - Regular buyers should have **User** (Purchase User) access only.

---

## Workflow Step-by-Step

```
[RFQ (Draft / Sent)] 
        │
        ▼ (Buyer clicks "Request Approval")
[To Approve] ─── (Approver notified via Activity & Chatter)
        │
   ┌────┴───────────────────────────┐
   │                                │
   ▼ (Approver clicks "Approve")    ▼ (Approver clicks "Reject" + enters reason)
[Purchase Order Confirmed]       [Reverted to RFQ Draft with Rejection Note]
```

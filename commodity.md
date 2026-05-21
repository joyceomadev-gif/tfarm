# Functional Specification & Technical Documentation: Commodity Trading Module (`commodity_trading`)

This documentation provides a comprehensive, detailed overview of the custom **Commodity Trading** application engineered for **Odoo 19 Enterprise**. It maps out the business logic, complex commodity accounting requirements, physical-financial supply chain reconciliations, and quality control systems without containing any code implementations.

---

## 1. Core Architectural Concepts & Business Philosophy

Traditional Enterprise Resource Planning (ERP) systems handle inventory and invoicing using static values: a product is received at a set cost, and it is sold at a fixed price. In global commodity markets (such as Cocoa trading), this model breaks down. 

Physical delivery and financial pricing are completely decoupled. A contract can be signed for 200 Metric Tons (MT) of Cocoa before the commodity is even harvested. Physical shipments might arrive at the warehouse in fragments over several months. Meanwhile, the actual financial price of those tons is locked in sequentially by traders using hedging, market fixations, and provisional pricing over entirely different dates.

This module bridges that gap. It allows the company to receive and ship physical stock based on scale weights, run strict laboratory quality parameters to penalize suppliers financially, and true-up customer accounts cleanly using sequential market price fixations—all managed inside a centralized contract dashboard.

---

## 2. Structural Model Breakdown

### 2.1 Commodity Customer & Vendor Contracts
The contract serves as the ultimate financial and operational anchor for all downstream activities. Every purchase order, sales order, warehouse delivery, and invoice must reference a specific contract to maintain clean traceability.

* **Multi-Currency Ledger System**: Global commodity trading often involves multiple economic environments. This module handles three distinct currency vectors simultaneously:
    1.  **Contract Currency**: Typically the market base currency (e.g., Great Britain Pounds - GBP), used to benchmark terminal market prices and differentials.
    2.  **Sales Currency**: The currency in which the buyer is officially invoiced (e.g., United States Dollars - USD).
    3.  **Procurement Currency**: The local currency used for purchasing from suppliers or smallholder farmers (e.g., Nigerian Naira - NGN).
* **Pricing Formula Mechanics**: Contracts do not utilize standard static price fields. Instead, prices are derived dynamically using a terminal market price combined with a contract-specific premium or discount known as the **Differential** (Market Price ± Differential).
* **The Live Balance Ledger**: The contract maintains a real-time, stored balance sheet dividing physical inventory metrics from financial pricing states:
    * *Total Delivered (Payable MT)*: The exact cumulative weight validated by warehouse scales that your company is legally obligated to pay for or collect revenue on.
    * *Total Fixed Quantity*: The amount of tonnage that has officially transitioned from fluctuating market prices to locked, finalized financial pricing.
    * *Unpriced Delivered Quantity*: A crucial exposure risk metric tracking exactly how many physical tons have already crossed your warehouse gates but remain vulnerable to market fluctuations because their final price hasn't been locked.

### 2.2 Price Fixation Architecture
Price fixations represent the financial execution of the contract. Traders can divide a single physical contract into separate pricing events based on market opportunities. The module accommodates three advanced market execution scenarios:

1.  **Provisional Pricing (Scenario 1)**: Allows traders to issue an advance invoice at an agreed percentage (e.g., 70%) of the current market price. This acts as an initial cash-flow injection pending the final price lock. Crucially, this provisional price doubles as a **Stop-Loss**. If the global market plummets to the level of the provisional price, the system treats it as the absolute final price to mitigate financial downside.
2.  **Part Fixation (Scenario 2)**: Handles partial pricing structures. If 100 MT have been physically delivered, a trader can execute a part-fixation to lock the final or provisional price for only a fraction (e.g., 60 MT) of the shipment, leaving the remaining 40 MT floating on the market.
3.  **Final Price Fixation (Scenario 3)**: Represents the absolute final pricing execution for a specified quantity. It overrides any prior provisional arrangements and establishes the final legal debt.

---

## 3. Procurement Workflow & Control Systems

### 3.1 Strict Procurement Authorization Loop
To enforce corporate compliance and prevent unauthorized purchasing exposure, the module introduces a rigid administrative approval phase into Odoo's native purchase flow.

* **Odoo 19 Three-Tier Access Management**: Utilizing Odoo 19’s updated security compliance layout, access rights are segregated using a dedicated **Privilege layer** bridging structural functional categories to end-user access profiles. Users must be explicitly assigned to the *Commodity PO Approver* profile to execute procurement confirmations.
* **Automated Verification Tasks**: When a procurement officer logs a new Purchase Request, the system shifts the document into a custom `Draft Request` phase and automatically deploys a native Odoo activity task to the dashboards of all authorized approvers. 
* **Enforced Gatekeeping**: Standard Odoo order confirmation features are programmatically suppressed. The system completely blocks the order from creating physical warehouse receipts until a verified member of the approval group reviews the transaction and signs off via an explicit `Approve Request` action.

### 3.2 Dual-Line Automated Vendor Billing
When raw materials fail quality standards, businesses must penalize suppliers without manipulating physical warehouse asset ledgers. This module achieves that via an automated billing split engine.

Upon executing the customized billing action directly from a confirmed Purchase Order, the engine scans all linked warehouse receipts and formats the vendor bill into exactly **two distinct lines**:
1.  **Line 1 (Payable Weight)**: The net premium tons accepted by the laboratory, billed at the full contract purchase price.
2.  **Line 2 (Quality Penalty)**: The exact tonnage deducted due to quality failures, registered on the bill at a **$0.00 unit price**. This guarantees that the supplier sees the physical deduction on their voucher, internal financial records reconcile to zero financial asset creation for bad stock, and standard system billing loops remain clean.

---

## 4. Warehouse & Laboratory Management

### 4.1 Weighbridge Capturing and Physical Deductions
The module features a dedicated warehouse weighbridge control desk embedded straight into incoming shipments. This dashboard manages raw scale inputs and converts them into pristine inventory records.

* **Scale Reconciliations**: The system records initial gross weights (`Weighbridge IN`) and empty truck weights (`Weighbridge OUT`) to capture the crude material weight.
* **Physical Tare Deductions**: A standard tare reduction is calculated dynamically based on bag counts (e.g., 1kg per bag deduction) alongside a moisture discount percentage factor to strip out excess water weight.
* **Stock Synchronization**: To ensure inventory accuracy, the module overrides standard validation loops. The moment a warehouse worker validates a receipt, the system forces Odoo's underlying stock valuation layers to record the processed `Net Weight` as the true physical asset increase.

### 4.2 Grouped Laboratory Testing Matrix
The module incorporates a complete Laboratory Information Management System (LIMS) directly inside Odoo purchase receipts. It features a two-step validation process that completely detaches human guesswork from quality penalties.

To pass laboratory inspection, an incoming lot of Cocoa must satisfy a strict, multi-tiered mathematical rule matrix. The fields are logically arranged into four distinct testing blocks:

* **1. The ADM Group (Admixture)**: Tracks physical impurities. Individual limits require *Sieve* to be $\le 2\%$, *Foreign Matter (FM)* to be strictly $< 2\%$, and *Flat Beans* to be $\le 2\%$. Additionally, the absolute combined sum of these three fields must never exceed a threshold of $3.5$.
* **2. The CRM Group**: Tracks internal structural defects. Individual limits require *BB (Broken Beans)* to be $\le 2\%$, *Fragments* to be $\le 2\%$, and *Clusters* to be $\le 2\%$. The combined sum of the CRM group must also never exceed a maximum of $3.5$.
* **3. The TD Group (Total Defects)**: Monitors major organic decay. Lot inputs map *Mouldy Beans* and *Insect-damaged Beans*. Both items are capped individually at $\le 5\%$, and their combined sum cannot exceed $5\%$.
* **4. The Bean Bloc**: Represents core commodity physical characteristics. It mandates that *Slaty Beans* remain $\le 7\%$, *Moisture Content* must be strictly low ($< 8\%$), and the *Bean Count* (the quantity of beans per 100g sample) must be high ($\ge 200$) to guarantee bean size standards.

#### **The Two-Step Laboratory Workflow**
To prevent data-entry manipulation, background calculations are disabled.
1.  **Step 1: Evaluation**: The lab technician types raw values into the matrix and clicks **"Evaluate QC Results"**. The engine runs the entire logic checks simultaneously. If every single condition in all four groups is perfectly satisfied, the receipt is awarded a green **Passed** badge, and the system permanently locks the lot from financial deductions. If even one parameter breaches a limit, the receipt is slapped with a red **Failed** badge.
2.  **Step 2: Financial Finalization**: A failed status prompts the system to unlock a hidden `Quality Discount Weight` input field. A logistics manager reviews the failure and inputs the financial weight penalty. Once satisfied, they click **"Finalize QC Penalty"**. This permanently freezes the laboratory screen, converting the page into an immutable, read-only audit record that cannot be tampered with by warehouse staff.
3.  **UI Separation**: Quality control tabs, weighbridge groups, and related constraints are programmatically hidden from outbound customer shipments (sales deliveries), restoring standard native Odoo delivery metrics on the client-facing side.

---

## 5. Sales & Advanced True-Up Invoicing Engine

### 5.1 The Two-Line Accounting "True-Up" Mechanism
When a contract is delivered and priced in stages, invoicing can become an accounting nightmare. For instance, if a contract is for 100 MT and 40 MT are initially shipped under a Provisional Price window, the client is invoiced for those 40 MT at the low provisional rate. When the remaining 60 MT are finally delivered and a higher Final Price is locked across the entire contract, standard systems often double-bill or rely on chaotic refund credits.

This module introduces a highly sophisticated **Difference True-Up Engine** directly inside the Sales Order billing action to resolve this seamlessly:

When a final fixation is linked to a prior provisional fixation, clicking "Create Invoice" bypasses standard line mapping and constructs a clean, dual-line invoice based on the exact price gaps:
* **Line 1 (Final Value Realization)**: Captures the newly shipped/priced quantity (e.g., 60 MT) and bills it cleanly at the full new Final Price.
* **Line 2 (Provisional Price Difference)**: Maps the original provisional quantity (e.g., 40 MT) that the customer already has in their possession. It calculates the exact positive financial difference ($Final Price - Provisional Price$) and bills just that outstanding balance. 
* *Result*: The customer is never double-billed, inventory volumes remain perfectly positive, and the total value paid across both invoices perfectly equals 100 MT at the absolute Final Market Price.

### 5.2 Consolidated Commercial ETG Document Design
International commodity buyers expect an institutional-grade **Consolidated Commercial Invoice** summarizing the entire lifecycle of a contract, rather than a generic financial invoice. This module features a bespoke QWeb report engine that builds this document natively.

* **Enforced Safety Pre-checks**: The system safeguards against incomplete documentation. If a trader attempts to print the consolidated invoice while a contract fixation is still sitting in a draft or un-invoiced state, the system halts execution and issues a strict warning.
* **Bespoke Letterhead & Brand Assets**: The layout skips standard Odoo template styles completely to achieve pixel-perfect fidelity with institutional standards. It integrates absolute CSS rendering to pin a prominent green brand accent ribbon to the top right corner and pulls the corporate identity logo directly from settings.
* **Table-Driven Structural Grid Alignment**: Traditional Odoo templates use fluid CSS columns that break and misalign during PDF translation via `wkhtmltopdf`. This module utilizes strict structural HTML percentage-based tables. This layout forces legal registry numbers, company data, customer addresses, and invoice metrics to remain perfectly aligned across from each other.
* **Live Accounting Aggregation**: The itemized billing matrix does not simply mirror the contract input screen. It queries your actual posted general ledger records (`account.move.line`). It pulls the actual quantities and descriptions billed across past transactions, calculates a live weighted average price achieved across all partial shipments, and appends a dedicated financial summary calculating the standard **95% Value Receivable Summary Balance** at the base of the page.
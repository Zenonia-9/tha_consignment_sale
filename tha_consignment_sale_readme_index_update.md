# Task: Update THA Consignment Sale README and Odoo Description Assets

## Goal

Update `tha_consignment_sale` so its screenshots and GIF are visible in both:

1. GitHub / repository `README.md`
2. Odoo module description page using `static/description/index.html`

After finishing, commit the changes.

---

## Module

```text
tha_consignment_sale
```

## Asset source
structure:

```text
tha_consignment_sale/
├── README.md
├── static/
│   └── description/
│       ├── index.html
│       ├── screenshots/
│       │   ├── 01_consignment_shop_partner_setup.jpg
│       │   ├── 02_consignment_warehouse_setup.jpg
│       │   ├── 03_consignment_order_list.jpg
│       │   ├── 04_consignment_order_form.jpg
│       │   ├── 05_transfer_smart_button_status.jpg
│       │   ├── 06_partial_transfer_backorder.jpg
│       │   ├── 07_consignment_transfers_list.jpg
│       │   ├── 08_consignment_settlement_list.jpg
│       │   ├── 09_create_invoice_commission_bill_buttons.jpg
│       │   ├── 10_created_invoice_and_commission_bill.jpg
│       │   ├── 11_consignment_return_form.jpg
│       │   ├── 12_consignment_order_print_wizard.jpg
│       │   └── 13_consignment_order_pdf_report.jpg
│       └── demo/
│           └── 01_order_workflow_with_backorder.gif
```

---

## README.md update instructions

Update the module `README.md` to include a new section after the overview/features section.

Add this section:

```markdown
## Demo

### Consignment order workflow with partial transfer and backorder

![Consignment order workflow with backorder](static/description/demo/01_order_workflow_with_backorder.gif)

This demo shows the main workflow: creating a consignment order, confirming it, validating a partial stock transfer, creating a backorder, and returning to the consignment order where the transfer status/count remains linked to the consignment workflow.

## Screenshots

### 1. Consignment shop setup

![Consignment shop setup](static/description/screenshots/01_consignment_shop_partner_setup.jpg)

### 2. Consignment warehouse setup

![Consignment warehouse setup](static/description/screenshots/02_consignment_warehouse_setup.jpg)

### 3. Consignment order list

![Consignment order list](static/description/screenshots/03_consignment_order_list.jpg)

### 4. Consignment order form

![Consignment order form](static/description/screenshots/04_consignment_order_form.jpg)

### 5. Transfer smart button and transfer status

![Transfer smart button and transfer status](static/description/screenshots/05_transfer_smart_button_status.jpg)

### 6. Partial transfer and backorder

![Partial transfer and backorder](static/description/screenshots/06_partial_transfer_backorder.jpg)

### 7. Consignment transfers list

![Consignment transfers list](static/description/screenshots/07_consignment_transfers_list.jpg)

### 8. Consignment settlement list

![Consignment settlement list](static/description/screenshots/08_consignment_settlement_list.jpg)

### 9. Invoice and commission bill actions

![Invoice and commission bill actions](static/description/screenshots/09_create_invoice_commission_bill_buttons.jpg)

### 10. Created invoice and commission bill

![Created invoice and commission bill](static/description/screenshots/10_created_invoice_and_commission_bill.jpg)

### 11. Consignment return form

![Consignment return form](static/description/screenshots/11_consignment_return_form.jpg)

### 12. Consignment order print wizard

![Consignment order print wizard](static/description/screenshots/12_consignment_order_print_wizard.jpg)

### 13. Consignment order PDF report

![Consignment order PDF report](static/description/screenshots/13_consignment_order_pdf_report.jpg)
```

Keep the existing README content if it already has installation/configuration sections. Do not remove useful existing content.

---

## static/description/index.html instructions

Create this file if it does not exist:

```text
tha_consignment_sale/static/description/index.html
```

If it already exists, update it so the demo GIF and screenshots are visible.

Use this content as the base:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>THA Consignment Sale</title>
    <style>
        body {
            font-family: Arial, Helvetica, sans-serif;
            color: #222;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background: #ffffff;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 32px 18px;
        }
        h1, h2, h3 {
            color: #111827;
        }
        .hero {
            padding: 28px;
            border-radius: 14px;
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            margin-bottom: 28px;
        }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background: #e0f2fe;
            color: #075985;
            font-size: 13px;
            margin-right: 6px;
            margin-bottom: 6px;
        }
        .media-card {
            margin: 28px 0;
            padding: 18px;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            background: #ffffff;
        }
        .media-card img {
            width: 100%;
            max-width: 100%;
            height: auto;
            border-radius: 10px;
            border: 1px solid #e5e7eb;
        }
        ul {
            padding-left: 22px;
        }
    </style>
</head>
<body>
<div class="container">
    <section class="hero">
        <h1>THA Consignment Sale</h1>
        <p>
            A complete Odoo 19 consignment workflow covering consignment orders, stock transfers,
            partial deliveries, backorders, settlements, customer invoices, commission bills,
            returns, and printable reports.
        </p>
        <div>
            <span class="badge">Odoo 19</span>
            <span class="badge">Inventory</span>
            <span class="badge">Accounting</span>
            <span class="badge">QWeb Reports</span>
            <span class="badge">Backorder Workflow</span>
        </div>
    </section>

    <section>
        <h2>Main Features</h2>
        <ul>
            <li>Consignment shop setup on partner records.</li>
            <li>Consignment source and destination warehouse configuration.</li>
            <li>Consignment order workflow with automatic stock transfer creation.</li>
            <li>Backorder-aware transfer tracking using linked consignment pickings.</li>
            <li>Settlement workflow for sold consignment stock.</li>
            <li>Customer invoice and commission vendor bill creation.</li>
            <li>Return workflow for unsold consignment stock.</li>
            <li>A4/A5 QWeb PDF reports with print wizard support.</li>
        </ul>
    </section>

    <section class="media-card">
        <h2>Workflow Demo</h2>
        <h3>Consignment order with partial transfer and backorder</h3>
        <img src="demo/01_order_workflow_with_backorder.gif" alt="Consignment order workflow with partial transfer and backorder">
    </section>

    <section>
        <h2>Screenshots</h2>

        <div class="media-card">
            <h3>1. Consignment shop setup</h3>
            <img src="screenshots/01_consignment_shop_partner_setup.jpg" alt="Consignment shop partner setup">
        </div>

        <div class="media-card">
            <h3>2. Consignment warehouse setup</h3>
            <img src="screenshots/02_consignment_warehouse_setup.jpg" alt="Consignment warehouse setup">
        </div>

        <div class="media-card">
            <h3>3. Consignment order list</h3>
            <img src="screenshots/03_consignment_order_list.jpg" alt="Consignment order list">
        </div>

        <div class="media-card">
            <h3>4. Consignment order form</h3>
            <img src="screenshots/04_consignment_order_form.jpg" alt="Consignment order form">
        </div>

        <div class="media-card">
            <h3>5. Transfer smart button and status</h3>
            <img src="screenshots/05_transfer_smart_button_status.jpg" alt="Transfer smart button and transfer status">
        </div>

        <div class="media-card">
            <h3>6. Partial transfer and backorder</h3>
            <img src="screenshots/06_partial_transfer_backorder.jpg" alt="Partial transfer and backorder">
        </div>

        <div class="media-card">
            <h3>7. Consignment transfers list</h3>
            <img src="screenshots/07_consignment_transfers_list.jpg" alt="Consignment transfers list">
        </div>

        <div class="media-card">
            <h3>8. Consignment settlement list</h3>
            <img src="screenshots/08_consignment_settlement_list.jpg" alt="Consignment settlement list">
        </div>

        <div class="media-card">
            <h3>9. Invoice and commission bill actions</h3>
            <img src="screenshots/09_create_invoice_commission_bill_buttons.jpg" alt="Invoice and commission bill actions">
        </div>

        <div class="media-card">
            <h3>10. Created invoice and commission bill</h3>
            <img src="screenshots/10_created_invoice_and_commission_bill.jpg" alt="Created invoice and commission bill">
        </div>

        <div class="media-card">
            <h3>11. Consignment return form</h3>
            <img src="screenshots/11_consignment_return_form.jpg" alt="Consignment return form">
        </div>

        <div class="media-card">
            <h3>12. Consignment order print wizard</h3>
            <img src="screenshots/12_consignment_order_print_wizard.jpg" alt="Consignment order print wizard">
        </div>

        <div class="media-card">
            <h3>13. Consignment order PDF report</h3>
            <img src="screenshots/13_consignment_order_pdf_report.jpg" alt="Consignment order PDF report">
        </div>
    </section>
</div>
</body>
</html>
```

---

## Commit instructions

Before committing, check changes:

```bash
git status
```

Do not include unrelated changes. Then commit:

```bash
git add tha_consignment_sale/README.md \
        tha_consignment_sale/static/description/index.html \
        tha_consignment_sale/static/description/screenshots \
        tha_consignment_sale/static/description/demo

git commit -m "docs: add consignment sale screenshots and demo"
```

If this module is inside a repository that uses a different path, adjust the path but keep the same commit message.

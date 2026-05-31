# Consignment Sale

![Odoo 19](https://img.shields.io/badge/Odoo-19.0-875A7B?style=flat-square)
![License](https://img.shields.io/badge/License-LGPL--3-blue?style=flat-square)
![Category](https://img.shields.io/badge/Category-Inventory-4ECDC4?style=flat-square)

Consignment workflow for Odoo 19: orders, transfers, settlements, commissions and returns.

## Highlights

- Issue consignment orders and create the related stock transfers.
- Record settlements that generate stock out, customer invoices and commission bills.
- Handle consignment returns and link them to original consignments.
- Ships with sequences, picking types and a commission product template.

## Workflow

1. Configure a partner as a consignment shop (enable the flag and set a consignment location, pricelist and commission %).
2. Create a Consignment Order and confirm it to generate the issue transfer to the shop.
3. Create a Consignment Settlement to record sold items; confirm to create stock out and then create the customer invoice and commission bill.
4. Process Consignment Returns to return unsold items back to stock.

## Technical Notes

- Key models:
	- `models/consignment_mixin.py` — shared helpers and sequence logic.
	- `models/consignment_order.py` — consignment order and order lines.
	- `models/consignment_settlement.py` — settlement, invoice and commission creation.
	- `models/consignment_return.py` — return flows.
	- `models/res_partner.py` — partner fields: `is_consignment_shop`, `consignment_location_id`, `consignment_pricelist_id`, `commission_rate`.
	- `models/stock_warehouse.py`, `models/stock_picking.py` — warehouse & picking helpers.
- Data:
	- `data/consignment_data.xml` — sequences, picking types and the `Consignment Commission` product template.
- Views and security:
	- `views/` contains forms, trees and menu items (orders, settlements, returns, transfers).
	- `security/ir.model.access.csv` and `security/consignment_security.xml` control access rights.

## Module Layout

```text
tha_consignment_sale/
|-- models/
|-- data/
|-- security/
|-- views/
|-- __init__.py
`-- __manifest__.py
```

## Dependencies

- `stock`
- `account`
- `contacts`
- `product`

## Installation

1. Place the module in your custom addons path.
2. Restart Odoo and update the Apps list.
3. Install **Consignment Sale**.

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

## License

LGPL-3

## Author

Thein Htoo Aung

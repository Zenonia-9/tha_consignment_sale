{
    "name": "Consignment Sale",
    "summary": "Order-driven consignment deliveries, settlements, returns, and commission flow",
    "version": "19.0.1.0.0",
    "category": "Inventory",
    "author": "Thein Htoo Aung",
    "license": "LGPL-3",
    "depends": ["stock", "account", "contacts", "product", "sale"],
    "description": """
Consignment Sale
================

This module implements a consignment workflow for Odoo 19.

Features
- Create Sales-Order-style consignment orders and issue deliveries to consignment shops.
- Create draft consignment settlements directly from confirmed consignment orders.
- Track delivery returns from related stock returns without a standalone return document.
- Create customer invoices and commission bills from confirmed settlements.
- Auto-creates required sequences, picking types and a commission product.

Installation
1. Place this module in your addons path.
2. Update the apps list and install "Consignment Sale".
""",
    "data": [
        "security/ir.model.access.csv",
        "security/consignment_security.xml",
        "data/consignment_data.xml",
        "data/report_attachment.xml",
        "wizard/consignment_order_print_wizard_views.xml",
        "wizard/consignment_settlement_create_wizard_views.xml",
        "views/res_partner_views.xml",
        "views/stock_warehouse_views.xml",
        "views/account_move_views.xml",
        "views/consignment_order_views.xml",
        "views/consignment_settlement_views.xml",
        "views/stock_picking_views.xml",
        "views/menu_views.xml",
        "report/paperformat.xml",
        "report/consignment_order_report.xml",
    ],
    "installable": True,
    "application": False,
}

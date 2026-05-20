{
    "name": "THA Consignment Sale",
    "summary": "Consignment orders, settlement, commission, and return flow",
    "version": "19.0.1.0.0",
    "category": "Inventory",
    "author": "Thein Htoo Aung",
    "license": "LGPL-3",
    "depends": ["stock", "account", "contacts", "product"],
    "description": """
THA Consignment Sale
=====================

This module implements a consignment workflow for Odoo 19.

Features
- Create consignment orders and issue transfers to consignment shops.
- Record consignment settlements: stock out, customer invoice and commission bill.
- Handle consignment returns and related transfers.
- Auto-creates required sequences, picking types and a commission product.

Installation
1. Place this module in your addons path.
2. Update the apps list and install "THA Consignment Sale".
""",
    "data": [
        "security/ir.model.access.csv",
        "security/consignment_security.xml",
        "data/consignment_data.xml",
        "wizard/consignment_order_print_wizard_views.xml",
        "views/res_partner_views.xml",
        "views/stock_warehouse_views.xml",
        "views/consignment_order_views.xml",
        "views/consignment_settlement_views.xml",
        "views/consignment_return_views.xml",
        "views/stock_picking_views.xml",
        "views/menu_views.xml",
        "report/paperformat.xml",
        "report/consignment_order_layout.xml",
        "report/consignment_order_report.xml",
    ],
    "installable": True,
    "application": False,
}

# THA Consignment Sale

THA Consignment Sale is an Odoo 19 module that provides a simple consignment workflow for shops and warehouses.

## Features

- Create consignment orders (issue transfers to shops).
- Record consignment settlements (stock out, customer invoice and commission bill).
- Handle consignment returns and related transfers.
- Auto-created sequences, picking types and a commission product template.

## Requirements

- Odoo 19.0
- Modules: `stock`, `account`, `contacts`, `product`

## Installation

1. Place this module directory under your Odoo `addons` path.
2. Restart Odoo and update the Apps list.
3. Install "THA Consignment Sale".

## Usage

- Configure a consignment shop: open the Contact record, enable **Is Consignment Shop**, set **Consignment Location**, **Consignment Pricelist** and **Commission %**.
- Menus: Inventory → Consignment → Consignment Orders / Consignment Transfers / Consignment Settlements / Consignment Returns.
- Create a consignment order and confirm it to create the issue transfer.
- Create a settlement and confirm it to generate stock out; then create the customer invoice and commission bill as needed.

## Data created by the module

- Sequences: `seq_consignment_order`, `seq_consignment_settlement`, `seq_consignment_return`, picking sequences.
- Picking types: Consignment Issue, Consignment Sold, Consignment Return.
- Product template: `Consignment Commission` (product_consignment_commission).

## License

LGPL-3

## Author

Thein Htoo Aung

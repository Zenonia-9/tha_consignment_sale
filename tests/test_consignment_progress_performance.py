from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestConsignmentProgressPerformance(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search([
            ("company_id", "=", cls.company.id),
        ], limit=1)
        cls.partner = cls.env["res.partner"].create({
            "name": "Consignment Batch Customer",
            "is_consignment_shop": True,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Consignment Batch Product",
            "type": "consu",
        })
        cls.unit_uom = cls.product.uom_id
        cls.dozen_uom = cls.env.ref("uom.product_uom_dozen")

    def _create_order(self):
        return self.env["tha.consignment.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "user_id": self.env.user.id,
            "source_warehouse_id": self.warehouse.id,
            "source_location_id": self.warehouse.lot_stock_id.id,
            "destination_warehouse_id": self.warehouse.id,
            "destination_location_id": self.warehouse.lot_stock_id.id,
            "currency_id": self.company.currency_id.id,
        })

    def _create_order_line(self, order, *, product=None, quantity=10.0, display_type=False):
        values = {
            "order_id": order.id,
            "display_type": display_type,
            "name": "Batch line",
        }
        if not display_type:
            product = product or self.product
            values.update({
                "product_id": product.id,
                "product_uom_id": product.uom_id.id,
                "product_uom_qty": quantity,
            })
        return self.env["tha.consignment.order.line"].create(values)

    def _create_picking(self, order, *, return_of=False):
        return self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.out_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.warehouse.lot_stock_id.id,
            "partner_id": self.partner.id,
            "tha_consignment_order_id": order.id,
            "return_id": return_of.id if return_of else False,
        })

    def _create_done_move(
        self,
        picking,
        *,
        quantity,
        order_line=False,
        origin_move=False,
        uom=False,
    ):
        return self.env["stock.move"].create({
            "product_id": self.product.id,
            "product_uom_qty": quantity,
            "quantity": quantity,
            "product_uom": (uom or self.unit_uom).id,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
            "picking_id": picking.id,
            "state": "done",
            "tha_consignment_order_line_id": order_line.id if order_line else False,
            "origin_returned_move_id": origin_move.id if origin_move else False,
        })

    def _create_settlement_line(self, order, order_line, quantity, *, state="draft", invoice=False):
        settlement = self.env["tha.consignment.settlement"].create({
            "order_id": order.id,
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "currency_id": self.company.currency_id.id,
            "state": state,
            "invoice_id": invoice.id if invoice else False,
        })
        return self.env["tha.consignment.settlement.line"].create({
            "settlement_id": settlement.id,
            "order_line_id": order_line.id,
            "product_id": self.product.id,
            "product_uom_id": self.unit_uom.id,
            "product_uom_qty": quantity,
        })

    def test_batched_progress_preserves_linked_and_legacy_quantities(self):
        order = self._create_order()
        line = self._create_order_line(order)
        display_line = self._create_order_line(order, display_type="line_note")
        delivery = self._create_picking(order)
        linked_delivery = self._create_done_move(delivery, quantity=4.0, order_line=line)
        self._create_done_move(delivery, quantity=2.0)
        returned = self._create_picking(order, return_of=delivery)
        self._create_done_move(returned, quantity=1.0, origin_move=linked_delivery)
        self._create_done_move(returned, quantity=1.0)

        active_invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_date": fields.Date.today(),
        })
        cancelled_invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_date": fields.Date.today(),
        })
        cancelled_invoice.button_cancel()
        self._create_settlement_line(order, line, 3.0, invoice=active_invoice)
        self._create_settlement_line(order, line, 1.0, invoice=cancelled_invoice)
        self._create_settlement_line(order, line, 2.0, state="cancel")

        (line | display_line)._compute_progress_quantities()

        self.assertEqual(line.qty_delivered, 6.0)
        self.assertEqual(line.qty_returned, 2.0)
        self.assertEqual(line.qty_settled, 4.0)
        self.assertEqual(line.qty_invoiced, 3.0)
        self.assertEqual(line.remaining_qty, 4.0)
        self.assertFalse(display_line.qty_delivered)
        self.assertFalse(display_line.remaining_qty)

    def test_unique_product_fallback_and_uom_conversion(self):
        unique_order = self._create_order()
        unique_line = self._create_order_line(unique_order, quantity=20.0)
        unique_delivery = self._create_picking(unique_order)
        self._create_done_move(unique_delivery, quantity=1.0, uom=self.dozen_uom)

        duplicate_order = self._create_order()
        duplicate_line_1 = self._create_order_line(duplicate_order)
        duplicate_line_2 = self._create_order_line(duplicate_order)
        duplicate_delivery = self._create_picking(duplicate_order)
        self._create_done_move(duplicate_delivery, quantity=5.0)

        lines = unique_line | duplicate_line_1 | duplicate_line_2
        lines._compute_progress_quantities()

        self.assertEqual(unique_line.qty_delivered, 12.0)
        self.assertFalse(duplicate_line_1.qty_delivered)
        self.assertFalse(duplicate_line_2.qty_delivered)

    def test_query_count_does_not_scale_per_line(self):
        order = self._create_order()
        lines = self.env["tha.consignment.order.line"]
        for index in range(10):
            product = self.env["product.product"].create({
                "name": "Consignment query product %s" % index,
                "type": "consu",
            })
            lines |= self._create_order_line(order, product=product)

        self.env.invalidate_all()
        start = self.env.cr.sql_log_count
        lines._compute_progress_quantities()
        batch_query_count = self.env.cr.sql_log_count - start

        self.env.invalidate_all()
        start = self.env.cr.sql_log_count
        lines[:1]._compute_progress_quantities()
        single_query_count = self.env.cr.sql_log_count - start

        self.assertLessEqual(batch_query_count, single_query_count + 4)

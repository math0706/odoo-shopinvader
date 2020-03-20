# -*- coding: utf-8 -*-
# Copyright 2019 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from openerp import fields
from openerp.addons.shopinvader.tests.common import CommonCase


class TestInvoiceService(CommonCase):
    """
    Tests for
    """

    def setUp(self, *args, **kwargs):
        super(TestInvoiceService, self).setUp(*args, **kwargs)
        self.invoice_obj = self.env["account.invoice"]
        self.journal_obj = self.env["account.journal"]
        self.register_payments_obj = self.env["account.register.payments"]
        self.sale = self.env.ref("shopinvader.sale_order_2")
        self.partner = self.env.ref("shopinvader.partner_1")
        self.product = self.env.ref("product.product_product_4")
        self.bank_journal_euro = self.journal_obj.create(
            {"name": "Bank", "type": "bank", "code": "BNK67"}
        )
        self.payment_method_manual_in = self.env.ref(
            "account.account_payment_method_manual_in"
        )
        self.precision = 2
        with self.work_on_services(partner=self.partner) as work:
            self.service = work.component(usage="invoice")
        with self.work_on_services(
            partner=self.backend.anonymous_partner_id
        ) as work:
            self.service_guest = work.component(usage="invoice")

    def _get_selection_label(self, invoice, field):
        """
        Get the translated label of the invoice selection field
        :param invoice: account.invoice recordset
        :param field: str
        :return: str
        """
        technical_type = invoice[field]
        type_dict = dict(
            invoice._fields.get(field)._description_selection(invoice.env)
        )
        return type_dict.get(technical_type, technical_type)

    def _check_data_content(self, data, invoices):
        """
        Check data based on given invoices
        :param data: list
        :param invoices: account.invoice recordset
        :return: bool
        """
        # To have them into correct order
        invoices = invoices.search(self.service._get_base_search_domain())
        self.assertEqual(len(data), len(invoices))
        for current_data, invoice in zip(data, invoices):
            state_label = self._get_selection_label(invoice, "state")
            type_label = self._get_selection_label(invoice, "type")
            self.assertEqual(current_data.get("invoice_id"), invoice.id)
            self.assertEqual(current_data.get("number"), invoice.number)
            self.assertEqual(
                current_data.get("date_invoice"), invoice.date_invoice
            )
            self.assertEqual(current_data.get("state"), state_label)
            self.assertEqual(current_data.get("type"), type_label)
            self.assertEqual(
                current_data.get("amount_total"), invoice.amount_total
            )
            self.assertEqual(
                current_data.get("amount_tax"), invoice.amount_tax
            )
            self.assertEqual(
                current_data.get("amount_untaxed"), invoice.amount_untaxed
            )
            self.assertEqual(current_data.get("amount_due"), invoice.residual)
        return True

    def _confirm_and_invoice_sale(self, sale, payment=True):
        """
        Confirm the given SO and create an invoice.
        Can also make the payment if payment parameter is True
        :param sale: sale.order recordset
        :param payment: bool
        :return: account.invoice
        """
        sale.action_confirm()
        for line in sale.order_line:
            line.write({"qty_delivered": line.product_uom_qty})
        invoice_id = sale.action_invoice_create()
        invoice = self.env["account.invoice"].browse(invoice_id)
        invoice.signal_workflow("invoice_open")
        invoice.action_move_create()
        if payment:
            self._make_payment(invoice)
        return invoice

    def _make_payment(self, invoice, journal=False, amount=False):
        """
        Make payment for given invoice
        :param invoice: account.invoice recordset
        :param amount: float
        :return: bool
        """
        ctx = {"active_model": invoice._name, "active_ids": invoice.ids}
        wizard_obj = self.register_payments_obj.with_context(**ctx)
        register_payments = wizard_obj.create(
            {
                "payment_date": fields.Date.today(),
                "journal_id": self.bank_journal_euro.id,
                "payment_method_id": self.payment_method_manual_in.id,
            }
        )
        values = {}
        if journal:
            values.update({"journal_id": journal.id})
        if amount:
            values.update({"amount": amount})
        if values:
            register_payments.write(values)
        register_payments.create_payment()

    def test_get_invoice_logged(self):
        """
        Test the get on a logged user.
        In the first part, the user should have any invoice.
        But to the second, he should have one.
        :return:
        """
        # Check first without invoice related to the partner
        result = self.service.dispatch("search")
        data = result.get("data", [])
        self.assertFalse(data)
        # Then create a invoice related to partner
        invoice = self._confirm_and_invoice_sale(self.sale, payment=False)
        self.assertEqual(invoice.partner_id, self.service.partner)
        result = self.service.dispatch("search")
        data = result.get("data", [])
        self._check_data_content(data, invoice)
        self._make_payment(invoice)
        result = self.service.dispatch("search")
        data = result.get("data", [])
        self._check_data_content(data, invoice)
        return

    def test_get_multi_invoice(self):
        """
        Test the get on a logged user.
        In the first part, the user should have any invoice.
        But to the second, he should have one.
        :return:
        """
        sale2 = self.sale.copy()
        sale3 = self.sale.copy()
        sale4 = self.sale.copy()
        invoice1 = self._confirm_and_invoice_sale(self.sale)
        invoice2 = self._confirm_and_invoice_sale(sale2)
        invoice3 = self._confirm_and_invoice_sale(sale3)
        invoice4 = self._confirm_and_invoice_sale(sale4)
        invoices = invoice1 | invoice2 | invoice3 | invoice4
        self.assertEqual(invoice1.partner_id, self.service.partner)
        self.assertEqual(invoice2.partner_id, self.service.partner)
        self.assertEqual(invoice3.partner_id, self.service.partner)
        self.assertEqual(invoice4.partner_id, self.service.partner)
        result = self.service.dispatch("search")
        data = result.get("data", [])
        self._check_data_content(data, invoices)
        return

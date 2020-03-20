# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


import logging

from openerp import api, fields, models

_logger = logging.getLogger(__name__)


class ShopinvaderCartStep(models.Model):
    _name = "shopinvader.cart.step"
    _description = "Shopinvader Cart Step"

    name = fields.Char(required=True)
    code = fields.Char(required=True)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    typology = fields.Selection(
        [("sale", "Sale"), ("cart", "Cart")], default="sale"
    )
    shopinvader_backend_id = fields.Many2one("shopinvader.backend", "Backend")
    current_step_id = fields.Many2one(
        "shopinvader.cart.step", "Current Cart Step", readonly=True
    )
    done_step_ids = fields.Many2many(
        comodel_name="shopinvader.cart.step",
        string="Done Cart Step",
        readonly=True,
    )
    # TODO move this in an extra OCA module
    shopinvader_state = fields.Selection(
        [
            ("cancel", "Cancel"),
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("shipped", "Shipped"),
        ],
        compute="_compute_shopinvader_state",
        store=True,
    )

    def _get_shopinvader_state(self):
        self.ensure_one()
        if self.state == "cancel":
            return "cancel"
        elif self.state == "done":
            return "shipped"
        elif self.state == "draft":
            return "pending"
        else:
            return "processing"

    @api.depends("state")
    def _compute_shopinvader_state(self):
        # simple way to have more human friendly name for
        # the sale order on the website
        for record in self:
            record.shopinvader_state = record._get_shopinvader_state()

    @api.model
    def _prepare_invoice(self, order, lines):
        res = super(SaleOrder, self)._prepare_invoice(order, lines)
        res["shopinvader_backend_id"] = self.shopinvader_backend_id.id
        return res

    @api.multi
    def action_confirm_cart(self):
        for record in self:
            if record.typology == "sale":
                # cart is already confirmed
                continue
            record.write({"typology": "sale"})
            if record.shopinvader_backend_id:
                record.shopinvader_backend_id._send_notification(
                    "cart_confirmation", record
                )
        return True

    @api.multi
    def action_button_confirm(self):
        res = super(SaleOrder, self).action_button_confirm()
        for record in self:
            if record.state != "draft" and record.shopinvader_backend_id:
                # If we confirm a cart directly we change the typology
                if record.typology != "sale":
                    record.typology = "sale"
                record.shopinvader_backend_id._send_notification(
                    "sale_confirmation", record
                )
        return res

    def reset_price_tax(self):
        for record in self:
            record.order_line.reset_price_tax()

    def _need_price_update(self, vals):
        for field in ["fiscal_position", "pricelist_id"]:
            if field in vals and self[field].id != vals[field]:
                return True
        return False

    def _play_cart_onchange(self, vals):
        result = {}
        # TODO in 10 use and improve onchange helper module
        if "partner_id" in vals:
            res = self.onchange_partner_id(vals["partner_id"]).get("value", {})
            for key in ["pricelist_id", "payment_term"]:
                if key in res:
                    result[key] = res[key]
        if "partner_shipping_id" in vals:
            res = self.onchange_delivery_id(
                self.company_id.id,
                vals.get("partner_id") or self.partner_id.id,
                vals["partner_shipping_id"],
                None,
            ).get("value", {})
            if "fiscal_position" in res:
                result["fiscal_position"] = res["fiscal_position"]
        return result

    @api.multi
    def write_with_onchange(self, vals):
        self.ensure_one()
        # Playing onchange on one2many is not really really clean
        # all value are returned even if their are not modify
        # Moreover "convert_to_onchange" in field.py add (5,) that
        # will drop the order_line
        # so it's better to drop the key order_line and run the onchange
        # on line manually
        reset_price = False
        #        new_vals = self.play_onchanges(vals, vals.keys())
        #        new_vals.pop("order_line", None)
        #        vals.update(new_vals)
        vals.update(self._play_cart_onchange(vals))
        reset_price = self._need_price_update(vals)
        self.write(vals)
        if reset_price:
            self.reset_price_tax()
        return True


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    shopinvader_variant_id = fields.Many2one(
        "shopinvader.variant",
        compute="_compute_shopinvader_variant",
        string="Shopinvader Variant",
    )

    def reset_price_tax(self):
        for line in self:
            res = line.product_id_change(
                line.order_id.pricelist_id.id,
                line.product_id.id,
                qty=line.product_uom_qty,
                uom=line.product_uom.id,
                qty_uos=line.product_uos_qty,
                uos=line.product_uos.id,
                name=line.name,
                partner_id=line.order_id.partner_id.id,
                lang=False,
                update_tax=True,
                date_order=line.order_id.date_order,
                packaging=False,
                fiscal_position=line.order_id.fiscal_position.id,
                flag=True,
            )["value"]
            line.write(
                {
                    "price_unit": res["price_unit"],
                    "discount": res.get("discount"),
                    "tax_id": [(6, 0, res.get("tax_id", []))],
                }
            )

    @api.depends("order_id.shopinvader_backend_id", "product_id")
    def _compute_shopinvader_variant(self):
        lang = self._context.get("lang")
        if not lang:
            _logger.warning(
                "No lang specified for getting the shopinvader variant "
                "take the first binding"
            )
        for record in self:
            bindings = record.product_id.shopinvader_bind_ids
            for binding in bindings:
                if (
                    binding.backend_id
                    != record.order_id.shopinvader_backend_id
                ):
                    continue
                if lang and binding.lang_id.code != lang:
                    continue
                record.shopinvader_variant_id = binding

    def _get_real_price_currency(
        self, product, rule_id, qty, uom, pricelist_id
    ):
        """Retrieve the price before applying the pricelist
            :param obj product: object of current product record
            :parem float qty: total quentity of product
            :param tuple price_and_rule: tuple(price, suitable_rule) coming from pricelist computation
            :param obj uom: unit of measure of current order line
            :param integer pricelist_id: pricelist id of sale order"""
        PricelistItem = self.env["product.pricelist.item"]
        field_name = "lst_price"
        currency_id = None
        product_currency = None
        if rule_id:
            pricelist_item = PricelistItem.browse(rule_id)
            if pricelist_item.price_version_id.pricelist_id.visible_discount:
                while (
                    pricelist_item.base == -1
                    and pricelist_item.base_pricelist_id
                    and pricelist_item.base_pricelist_id.visible_discount
                ):
                    price, rule_id = pricelist_item.base_pricelist_id.with_context(
                        uom=uom.id
                    ).price_rule_get(
                        product.id, qty or 1.0, self.order_id.partner_id
                    )
                    final_price, rule_id = res[pricelist.id]
                    pricelist_item = PricelistItem.browse(rule_id)

            if pricelist_item.base == -2:
                field_name = "standard_price"
            if pricelist_item.base == -1 and pricelist_item.base_pricelist_id:
                field_name = "price"
                product = product.with_context(
                    pricelist=pricelist_item.base_pricelist_id.id
                )
                product_currency = pricelist_item.base_pricelist_id.currency_id
            currency_id = (
                pricelist_item.price_version_id.pricelist_id.currency_id
            )

        product_currency = (
            product_currency
            or (product.company_id and product.company_id.currency_id)
            or self.env.user.company_id.currency_id
        )
        if not currency_id:
            currency_id = product_currency
            cur_factor = 1.0
        else:
            if currency_id.id == product_currency.id:
                cur_factor = 1.0
            else:
                cur_factor = currency_id._get_conversion_rate(
                    product_currency, currency_id
                )

        product_uom = self.env.context.get("uom") or product.uom_id.id
        if uom and uom.id != product_uom:
            # the unit price is in a different uom
            uom_factor = uom._compute_price(1.0, product.uom_id)
        else:
            uom_factor = 1.0

        return product[field_name] * uom_factor * cur_factor, currency_id.id

# -*- coding: utf-8 -*-
# Copyright 2017 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp.addons.shopinvader.services.helper import (
    secure_params,
    ShopinvaderService)
from openerp.addons.shopinvader.services.cart import shopinvader, CartService
from openerp.tools.translate import _
import stripe
import logging
_logger = logging.getLogger(__name__)


@shopinvader
class StripeTransactionService(ShopinvaderService):
    _model_name = 'gateway.transaction'

    def _generate_stripe_response(self, intent):
        if (
            intent.status == "requires_action"
            and intent.next_action.type == "use_stripe_sdk"
        ):
            # Tell the client to handle the action
            return {
                "requires_action": True,
                "payment_intent_client_secret": intent.client_secret,
            }
        elif intent.status == "succeeded":
            # The payment didn’t need any additional actions and completed!
            cart_service = self.service_for(CartService)
            # confirm the card
            data = cart_service.update({
                'next_step': self.backend_record.last_step_id.code})
            data["success"] = True
            return data
        elif intent.status == "canceled":
            return {"error": _("Payment canceled.")}
        else:
            _logger.error("Unexpected intent status: %s", intent)
            return {"error": _("Payment Error")}

    @secure_params
    def create(self, params):
        stripe_payment_intent_id = params['stripe_payment_intent_id']
        provider = self.env['payment.service.stripe']
        transaction = provider._get_transaction_from_return(params)
        intent = stripe.PaymentIntent.confirm(
            stripe_payment_intent_id,
            api_key=provider._api_key,
        )
        return self._generate_stripe_response(intent)

    def _validator_create(self):
        return {'stripe_payment_intent_id': {'type': 'string'}}

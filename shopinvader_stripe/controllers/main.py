# -*- coding: utf-8 -*-
# Copyright 2016 Akretion (http://www.akretion.com)
# Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from ..services.stripe_transaction import StripeTransactionService
from openerp.addons.shopinvader.controllers.main import (
    ShopinvaderController,
    route)
import logging
_logger = logging.getLogger(__name__)


class ShopinvaderStripeController(ShopinvaderController):

    # Check Transaction
    @route('/shopinvader/stripe/process_intent',
           methods=['POST'], auth="shopinvader")
    def process_intent(self, **params):
        return self.send_to_service(StripeTransactionService, params)

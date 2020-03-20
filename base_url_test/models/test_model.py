# -*- coding: utf-8 -*-
# Copyright 2019 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging

from openerp import api, fields, models

_logger = logging.getLogger(__name__)


class UrlBackendFake(models.Model):

    _name = "url.backend.fake"
    _description = "Url Backend"

    name = fields.Char(required=True)


class ResPartnerAddressableFake(models.Model):
    _name = "res.partner.addressable.fake"
    _inherit = "abstract.url"
    _inherits = {"res.partner": "record_id"}
    _description = "Fake partner addressable"

    backend_id = fields.Many2one(comodel_name="url.backend.fake")

    @api.multi
    @api.depends("lang_id", "record_id.name")
    def _compute_automatic_url_key(self):
        self._generic_compute_automatic_url_key()

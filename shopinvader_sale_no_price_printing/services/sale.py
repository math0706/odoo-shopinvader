from odoo.addons.component.core import Component
from odoo.addons.base_rest import restapi


class SaleService(Component):
    _inherit = "shopinvader.sale.service"
    _usage = "sales"

    @restapi.method(
        routes=[(["/<int:_id>/download"], "GET")],
        input_param=restapi.CerberusValidator("_get_download_schema"),
        output_param=restapi.BinaryData(required=True),
    )
    def download(self, _id, **params):
        # Add the input_param schema to the download route
        return super().download(_id, **params)

    def _get_download_schema(self):
        # Specify a true or false string for the no_price parameter
        # boolean is not working here since GET parameters are string
        return {
            "no_price": {
                "type": "string",
                "allowed": ["true", "false"],
                "required": False,
            }
        }

    def _get_report_action(self, target, params=None):
        """
        Get the action/dict to generate the report
        :param target: recordset
        :param params: dict
        :return: dict/action
        """
        # Choose the report according to the parameter
        report = (
            "sale_no_price_printing.action_report_saleorder_without_price"
            if params and params.get("no_price") == "true"
            else "sale.action_report_saleorder"
        )
        return self.env.ref(report).report_action(target, config=False)

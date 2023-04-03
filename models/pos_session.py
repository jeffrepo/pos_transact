# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_pos_payment_method(self):
        result = super()._loader_params_pos_payment_method()
        result['search_params']['fields'].append('no_mostrar_pos')
        result['search_params']['fields'].append('env_app_name')
        result['search_params']['fields'].append('tarjeta_tipo')
        return result

    def _loader_params_res_company(self):
        result = super()._loader_params_res_company()
        result['search_params']['fields'].append('moneda_ISO')
        result['search_params']['fields'].append('hash')
        result['search_params']['fields'].append('emp_cod')
        return result

    def _loader_params_pos_config_method(self):
        result = super()._loader_params_pos_config_method()
        result['search_params']['fields'].append('term_cod')
        return result

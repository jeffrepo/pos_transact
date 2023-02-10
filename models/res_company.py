# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
import logging

class ResCompany(models.Model):
    _inherit = 'res.company'

    emp_cod = fields.Char('Código de empresa')
    moneda_ISO = fields.Char('Moneda ISO')
    hash = fields.Char('HASH')

    @api.model
    def customer_fields(self, company=None):
        fields = {}
        company = self.env.company
        logging.warning('Función de fields_get')
        logging.warning(self)
        logging.warning(self.env)
        logging.warning(self.env.company)
        logging.warning(company.emp_cod)
        logging.warning(company.moneda_ISO)
        fields['emp_cod'] = company.emp_cod
        fields['moneda_iso'] = company.moneda_ISO
        fields['hash'] = company.hash
        return fields

# -*- coding: utf-8 -*-

from odoo import models
from odoo import _, api, fields
import logging

class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        logging.warning('Función para cargar campos')
        logging.warning('')
        fields = super().fields_get(allfields=allfields, attributes=attributes)
        logging.warning(fields)
        return fields

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from itertools import groupby
from re import search
from functools import partial

import pytz, logging

from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    tokenNro = fields.Char('Token Numero:')

    def _process_payment_lines(self, pos_order, order, pos_session, draft):
        logging.warning('')
        logging.warning('')
        logging.warning('Heredando una funcion :/ _process_payment_lines')
        logging.warning('')
        logging.warning('')
        logging.warning(pos_order)
        logging.warning('')
        for statement in pos_order['statement_ids']:
            logging.warning('statement_ids:')
            logging.warning(statement)
            logging.warning('')
            if statement[2]['nuevo_metodo_pago_id']:
                statement[2]['payment_method_id'] = statement[2]['nuevo_metodo_pago_id']

        logging.warning('')
        logging.warning('new pos_order')
        logging.warning(pos_order)

        result = super()._process_payment_lines(pos_order, order, pos_session, draft)

        return result

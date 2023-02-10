# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
import pprint
import random
import requests
import string
import base64
from werkzeug.exceptions import Forbidden
from lxml import etree
import xmltodict

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        logging.warning('Algo en python')
        logging.warning(self.use_payment_terminal)
        return super(PosPaymentMethod, self)._get_payment_terminal_selection() + [('transact', 'Transact')]

    # Adyen
    transact_api_key = fields.Char(string="Transact API key", help='Used when connecting to Adyen: https://docs.adyen.com/user-management/how-to-get-the-api-key/#description', copy=False)
    transact_terminal_identifier = fields.Char(help='[Terminal model]-[Serial number], for example: P400Plus-123456789', copy=False)
    transact_test_mode = fields.Boolean(help='Run transactions in the test environment.')

    transact_latest_response = fields.Char(copy=False, groups='base.group_erp_manager') # used to buffer the latest asynchronous notification from Transact.
    transact_latest_diagnosis = fields.Char(copy=False, groups='base.group_erp_manager') # used to determine if the terminal is still connected.

    @api.constrains('transact_terminal_identifier')
    def _check_transact_terminal_identifier(self):
        for payment_method in self:
            if not payment_method.transact_terminal_identifier:
                continue
            existing_payment_method = self.search([('id', '!=', payment_method.id),
                                                   ('transact_terminal_identifier', '=', payment_method.transact_terminal_identifier)],
                                                  limit=1)
            if existing_payment_method:
                raise ValidationError(_('Terminal %s is already used on payment method %s.')
                                      % (payment_method.transact_terminal_identifier, existing_payment_method.display_name))

    def _get_transact_endpoints(self):
        return {
            'terminal_request': 'https://terminal-api-%s.adyen.com/async',
        }

    def _is_write_forbidden(self, fields):
        whitelisted_fields = set(('transact_latest_response', 'transact_latest_diagnosis'))
        return super(PosPaymentMethod, self)._is_write_forbidden(fields - whitelisted_fields)

    def _transact_diagnosis_request_data(self, pos_config_name):

        service_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        return {
            "SaleToPOIRequest": {
                "MessageHeader": {
                    "ProtocolVersion": "3.0",
                    "MessageClass": "Service",
                    "MessageCategory": "Diagnosis",
                    "MessageType": "Request",
                    "ServiceID": service_id,
                    "SaleID": pos_config_name,
                    "POIID": self.transact_terminal_identifier,
                },
                "DiagnosisRequest": {
                    "HostDiagnosisFlag": False
                }
            }
        }

    def transact_values(self, dicc_venta, operation):
        self.ensure_one()
        TIMEOUT = 10

        _logger.info('request to transact\n%s', pprint.pformat(dicc_venta))
        environment = 'test' if self.transact_test_mode else 'live'
        endpoint = self._get_transact_endpoints()[operation] % environment

        data = {}
        attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
        SOAPN_NS = "{http://schemas.xmlsoap.org/soap/envelope/}"
        TEM = "{http://tempuri.org/}"
        TRAN = "{http://schemas.datacontract.org/2004/07/TransActV4ConcentradorWS.TransActV4Concentrador}"
        NSMAP = {
             'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
        }
        SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
        ns_map = {'soapenv': SOAP_NS, 'tem': "http://tempuri.org/", 'tran': "http://schemas.datacontract.org/2004/07/TransActV4ConcentradorWS.TransActV4Concentrador"}

        Envelope = etree.Element(etree.QName(SOAP_NS, 'Envelope'), nsmap=ns_map)
        TagHeader = etree.SubElement(Envelope,SOAPN_NS+"Header",{})
        TagBody = etree.SubElement(Envelope,SOAPN_NS+"Body",{})

        TagPostearTransaccion = etree.SubElement(TagBody,TEM+"PostearTransaccion",{})
        TagTransaccion = etree.SubElement(TagPostearTransaccion,TEM+"Transaccion",{})
        TagEmisorId = etree.SubElement(TagTransaccion,TRAN+"EmisorId",{})
        TagEmpCod = etree.SubElement(TagTransaccion,TRAN+"EmpCod",{})
        TagEmpHASH = etree.SubElement(TagTransaccion,TRAN+"EmpHASH",{})
        TagFacturaConsumidorFinal = etree.SubElement(TagTransaccion,TRAN+"FacturaConsumidorFinal",{})
        TagFacturaMonto = etree.SubElement(TagTransaccion,TRAN+"FacturaMonto",{})
        TagFacturaMontoGravado = etree.SubElement(TagTransaccion,TRAN+"FacturaMontoGravado",{})
        TagMontoIVA = etree.SubElement(TagTransaccion,TRAN+"TagMontoIVA",{})
        TagFacturaNro = etree.SubElement(TagTransaccion,TRAN+"FacturaNro",{})
        TagMonedaISO = etree.SubElement(TagTransaccion,TRAN+"MonedaISO",{})
        TagMonto = etree.SubElement(TagTransaccion,TRAN+"Monto",{})
        TagMontoCashBack = etree.SubElement(TagTransaccion,TRAN+"MontoCashBack",{})
        TagMontoPropina = etree.SubElement(TagTransaccion,TRAN+"MontoPropina",{})
        TagOperacion = etree.SubElement(TagTransaccion,TRAN+"Operacion",{})
        TagTarjetaId = etree.SubElement(TagTransaccion,TRAN+"TarjetaId",{})
        TagTermCod = etree.SubElement(TagTransaccion,TRAN+"TermCod",{})
        if len(dicc_venta)>1:
            if 'emisor_id' in dicc_venta:
                # TagEmisorId.text = 'LOL3'
                TagEmisorId.text = str(dicc_venta['emisor_id'])
            if 'emp_cod' in dicc_venta:
                TagEmpCod.text = str(dicc_venta['emp_cod'])
            if 'emp_hash' in dicc_venta:
                TagEmpHASH.text = str(dicc_venta['emp_hash'])
            if 'factura_consumidor_final' in dicc_venta:
                TagFacturaConsumidorFinal.text = str(dicc_venta['factura_consumidor_final'])
            if 'factura_monto' in dicc_venta:
                TagFacturaMonto.text = str(dicc_venta['factura_monto'])
            if 'factura_monto_gravado' in dicc_venta:
                TagFacturaMontoGravado.text = str(dicc_venta['factura_monto_gravado'])
            if 'monto_iva' in dicc_venta:
                TagMontoIVA.text = str(dicc_venta['monto_iva'])
            if 'factura_nro' in dicc_venta:
                TagFacturaNro.text = str(dicc_venta['factura_nro'])
            if 'moneda_iso' in dicc_venta:
                TagMonedaISO.text = str(dicc_venta['moneda_iso'])
            if 'monto' in dicc_venta:
                TagMonto.text = str(dicc_venta['monto'])
            if 'monto_cash_back' in dicc_venta:
                TagMontoCashBack.text = str(dicc_venta['monto_cash_back'])
            if 'monto_propina' in dicc_venta:
                TagMontoPropina.text = str(dicc_venta['monto_propina'])
            if 'operacion' in dicc_venta:
                TagOperacion.text = str(dicc_venta['operacion'])
            if 'tarjeta_id' in dicc_venta:
                TagTarjetaId.text = str(dicc_venta['tarjeta_id'])
            if 'term_cod' in dicc_venta:
                # TagTermCod.text = 'LO'
                TagTermCod.text = str(dicc_venta['term_cod'])

            xmls = etree.tostring(Envelope, encoding="UTF-8")
            xmls = xmls.decode("utf-8").replace("&amp;", "&").encode("utf-8")
            xmls_base64 = base64.b64encode(xmls)

            url = "https://wwwi.transact.com.uy/ConcentradorV402/TarjetasTransaccion_402.svc"

            headers = {"content-type": "text/xml; charset=utf-8", 'SOAPAction': "http://tempuri.org/ITarjetasTransaccion_402/PostearTransaccion"}
            response = requests.post(url, data = xmls, headers = headers, timeout = TIMEOUT)

            logging.warning('First xml')
            logging.warning(xmls)
            logging.warning('status code')
            logging.warning(response.status_code)
            logging.warning(response)
            if response.status_code == 500:
                logging.warning('Respuesta mala')
                return {
                    'error': {
                        'status_code': response.status_code,
                        'message': 'Algo mal'
                    }
                }

            if response:
                logging.warning('Primer RESPNSE')
                logging.warning(response)
                if response.status_code == 200:
                    if response.content:
                        new_xml = xmltodict.parse(response.content)
                        logging.warning('json.dumps(new_xml)')
                        logging.warning(json.dumps(new_xml))
                        logging.warning('')
                        new_json1 = json.dumps(new_xml)
                        new_json = json.loads(new_json1)
                        logging.warning('Que es new_json')
                        logging.warning(new_json)
                        if new_json:
                            if 's:Envelope' in new_json:
                                if new_json['s:Envelope']:
                                    if 's:Body' in new_json['s:Envelope']:
                                        if 'PostearTransaccionResponse' in new_json['s:Envelope']['s:Body']:
                                            if 'PostearTransaccionResult' in new_json['s:Envelope']['s:Body']['PostearTransaccionResponse']:
                                                if 'a:Resp_CodigoRespuesta' in new_json['s:Envelope']['s:Body']['PostearTransaccionResponse']['PostearTransaccionResult']:
                                                    if new_json['s:Envelope']['s:Body']['PostearTransaccionResponse']['PostearTransaccionResult']['a:Resp_CodigoRespuesta'] == '0':
                                                        logging.warning('Devolviendo TRUE')
                                                        new_json = str(new_json).replace("'", '"')
                                                        self.transact_latest_response = new_json
                                                        return True
                                                    else:
                                                        return {
                                                            'error': {
                                                                'status_code': new_json['s:Envelope']['s:Body']['PostearTransaccionResponse']['PostearTransaccionResult']['a:Resp_CodigoRespuesta'],
                                                                'message': new_json['s:Envelope']['s:Body']['PostearTransaccionResponse']['PostearTransaccionResult']['a:Resp_MensajeError']
                                                            }
                                                        }

                        else:
                            logging.warning('Verificar algo')
                else:
                    return {
                        'error': {
                            'status_code': response.status_code,
                            'message': 'Algo mal'
                        }
                    }

        logging.warning('data :D')
        logging.warning(data)
        return response.json()



    def get_latest_transact_status(self, pos_config_name):
        self.ensure_one()
        logging.warning('get_latest_transact_status')
        latest_response = self.sudo().transact_latest_response
        logging.warning('1. latest_response')
        logging.warning(latest_response)
        latest_response = json.loads(latest_response) if latest_response else False
        logging.warning('')

        logging.warning(latest_response)
        logging.warning('')
        return {
            'latest_response': latest_response,
        }

    def proxy_transact_request(self, data, operation=False):
        ''' Necessary because Adyen's endpoints don't have CORS enabled '''
        # if data['SaleToPOIRequest']['MessageHeader']['MessageCategory'] == 'Payment': # Clear only if it is a payment request
        #     self.sudo().transact_latest_response = ''  # avoid handling old responses multiple times

        if not operation:
            operation = 'terminal_request'

        return self.transact_values(data, operation)
        # return self._proxy_transact_request_direct(data, operation)

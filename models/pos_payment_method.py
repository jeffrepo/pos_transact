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

    # TransAct
    # transact_api_key = fields.Char(string="Transact API key", help='Used when connecting to Adyen: https://docs.adyen.com/user-management/how-to-get-the-api-key/#description', copy=False)
    transact_terminal_identifier = fields.Char(help='[Terminal model]-[Serial number], for example: P400Plus-123456789', copy=False)
    transact_test_mode = fields.Boolean(help='Run transactions in the test environment.')

    transact_latest_response = fields.Char(copy=False, groups='base.group_erp_manager') # used to buffer the latest asynchronous notification from Transact.
    transact_latest_diagnosis = fields.Char(copy=False, groups='base.group_erp_manager') # used to determine if the terminal is still connected.
    transact_token_nro = fields.Char('TOKEN',  store=True)
    no_mostrar_pos = fields.Boolean('No mostrar POS')
    tarjeta_tipo = fields.Selection(
    selection=[
    ('CRE','Crédito'),
    ('DEB','Débito'),
    ('NO_SETEAR', 'No setear')
    ], string="Tipo tarjeta")
    tarjeta_id = fields.Integer('Tarjeta ID')
    env_app_name = fields.Char(string="Emv App Name")

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
        response = ''
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
        TagConfiguracion = etree.SubElement(TagPostearTransaccion, TRAN+"Configuracion", {})
        TagTransaccion = etree.SubElement(TagPostearTransaccion,TEM+"Transaccion", {})
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

        #TagModoEmulacion = etree.SubElement(TagTransaccion,TRAN+"ModoEmulacion",{})

        TagModoEmulacion = etree.SubElement(TagConfiguracion, TRAN+"ModoEmulacion", {})
        TagModoEmulacion.text = 'false'

        logging.warning('dicc_venta')
        logging.warning(dicc_venta)
        url = ""
        if dicc_venta and len(dicc_venta)>1:
            if 'url_conector' in dicc_venta:
                url = str(dicc_venta['url_conector'])
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
            #if 'modo_emulacion' in dicc_venta:
             #   logging.warning('modo emulacion')
              #  logging.warning(dicc_venta['modo_emulacion'])
               # TagModoEmulacion.text = str(dicc_venta['modo_emulacion'])

            xmls = etree.tostring(Envelope, encoding="UTF-8")
            xmls = xmls.decode("utf-8").replace("&amp;", "&").encode("utf-8")
            xmls_base64 = base64.b64encode(xmls)

            #url = "https://wwwi.transact.com.uy/ConcentradorV402/TarjetasTransaccion_402.svc"
            #url = "https://wwwi.transact.com.uy/Concentrador/TarjetasTransaccion_401.svc?wsdl"
            #url = "https://wwwi.transact.com.uy/Concentrador/TarjetasTransaccion_400.svc?wsdl"
            #url = "https://wwwi.transact.com.uy/ConcentradorV402/TarjetasTransaccion_402.svc?wsdl"
            url = "https://concentrador01.transact.com.uy:444/TarjetasTransaccion_401.svc?wsdl"
            headers = {"content-type": "text/xml; charset=utf-8", 'SOAPAction': "http://tempuri.org/ITarjetasTransaccion_401/PostearTransaccion"}
            #headers = {"content-type": "text/xml; charset=utf-8", 'SOAPAction': "https://concentrador01.transact.com.uy:444/TarjetasTransaccion_401.svc?wsdl"}

            response = requests.post(url, data = xmls, headers = headers, timeout = TIMEOUT)

            logging.warning('First xml')
            logging.warning(xmls)
            logging.warning('status code')
            logging.warning(response.status_code)
            logging.warning(response)
            logging.warning(response.content)
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
                                                        tokenNro = str(new_json['s:Envelope']['s:Body']['PostearTransaccionResponse']['PostearTransaccionResult']['a:TokenNro'])
                                                        new_json = str(new_json).replace("'", '"')
                                                        return {'estado_transaccion':True, 'tokenNro':tokenNro}
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
        if response:
            logging.warning('response.json()')
            logging.warning(response)
            return response.json()
        else:
            return False

    def consult_transAct(self, tokenNro):
        self.ensure_one()
        TIMEOUT = 10
        logging.warning('')
        logging.warning('def consult_transAct')
        logging.warning('')
        _logger.info('request to transact\n%s', pprint.pformat(tokenNro))
        environment = 'test' if self.transact_test_mode else 'live'
        # endpoint = self._get_transact_endpoints()[operation] % environment

        data = {}
        attr_qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
        SOAPN_NS = "{http://schemas.xmlsoap.org/soap/envelope/}"
        TEM = "{http://tempuri.org/}"
        NSMAP = {
             'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
        }
        SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
        ns_map = {'soapenv': SOAP_NS, 'tem': "http://tempuri.org/"}

        Envelope = etree.Element(etree.QName(SOAP_NS, 'Envelope'), nsmap=ns_map)
        TagHeader = etree.SubElement(Envelope,SOAPN_NS+"Header",{})
        TagBody = etree.SubElement(Envelope,SOAPN_NS+"Body",{})

        TagConsultarTransaccion = etree.SubElement(TagBody,TEM+"ConsultarTransaccion",{})
        TagTokenNro = etree.SubElement(TagConsultarTransaccion, TEM+"TokenNro", {})

        logging.warning('token en consulT')
        logging.warning(tokenNro)

        if tokenNro:
            TagTokenNro.text = str(tokenNro)

        xmls = etree.tostring(Envelope, encoding="UTF-8")
        xmls = xmls.decode("utf-8").replace("&amp;", "&").encode("utf-8")
        xmls_base64 = base64.b64encode(xmls)

        #url = "https://wwwi.transact.com.uy/ConcentradorV402/TarjetasTransaccion_402.svc?wsdl"
        #url = str(self.env.company.url_conector)
        url = "https://concentrador01.transact.com.uy:444/TarjetasTransaccion_401.svc?wsdl"
        headers = {"content-type": "text/xml; charset=utf-8", 'SOAPAction': "http://tempuri.org/ITarjetasTransaccion_401/ConsultarTransaccion"}
        #headers = {"content-type": "text/xml; charset=utf-8", 'SOAPAction': "https://concentrador01.transact.com.uy:444/TarjetasTransaccion_401.svc?wsdl"}

        response = requests.post(url, data = xmls, headers = headers, timeout = TIMEOUT)

        logging.warning('First xml consult_transAct')
        logging.warning(xmls)
        logging.warning('status code')
        logging.warning(response.status_code)
        logging.warning(response)
        logging.warning(response.content)

        if response.status_code == 500:
            logging.warning('Respuesta mala')
            return {
                'error': {
                    'status_code': response.status_code,
                    'message': 'Algo mal'
                }
            }

        if response:
            logging.warning('Primer RESPNSE consult_transAct')
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
                    logging.warning('')
                    logging.warning('')
                    logging.warning('')
                    if new_json:
                        if 's:Envelope' in new_json:
                            if 's:Body' in new_json['s:Envelope']:
                                if 'ConsultarTransaccionResponse' in new_json['s:Envelope']['s:Body']:
                                    if 'ConsultarTransaccionResult' in new_json['s:Envelope']['s:Body']['ConsultarTransaccionResponse']:
                                        if 'a:Resp_CodigoRespuesta' in new_json['s:Envelope']['s:Body']['ConsultarTransaccionResponse']['ConsultarTransaccionResult']:
                                            if new_json['s:Envelope']['s:Body']['ConsultarTransaccionResponse']['ConsultarTransaccionResult']['a:Resp_CodigoRespuesta'] == '0':
                                                logging.warning('Se esta Obteniendo 0 en la respuesta')
                                                # self.latest_response = 'Esto es temporal'
                                                # return {
                                                # "@xmlns:a": "http://schemas.datacontract.org/2004/07/TransActV4ConcentradorWS.TransActV4Concentrador",
                                                # "@xmlns:i": "http://www.w3.org/2001/XMLSchema-instance",
                                                # "a:Aprobada": "true",
                                                # "a:CodRespAdq": "00",
                                                # "a:DatosTransaccion": {
                                                #     "a:Cuotas": "1",
                                                #     "a:DecretoLeyAplicado": "true",
                                                #     "a:DecretoLeyMonto": "243",
                                                #     "a:DecretoLeyNro": "19210",
                                                #     "a:EmisorId": "12",
                                                #     "a:Extendida": {
                                                #         "a:CuentaNro": "null",
                                                #         "a:DecretoLeyAdqId": "6",
                                                #         "a:DecretoLeyId": "1",
                                                #         "a:DecretoLeyNom": "CONSUMIDOR FINAL",
                                                #         "a:DecretoLeyVoucher": "Aplica dev. IVA-Ley 19210 | Sin nro. factura no aplica ley",
                                                #         "a:EmisorNombre": "ITAU",
                                                #         "a:EmpresaNombre": "EPIKUY",
                                                #         "a:EmpresaRUT": "111111110197",
                                                #         "a:EmvAppId": "A0000000031010",
                                                #         "a:EmvAppName": "VISA CREDITO",
                                                #         "a:FacturaMonto": "10000",
                                                #         "a:FacturaMontoGravado": "8100",
                                                #         "a:FacturaMontoGravadoTrn": "8100",
                                                #         "a:FacturaMontoIVA": "0",
                                                #         "a:FacturaMontoIVATrn": "0",
                                                #         "a:FacturaNro": "1234",
                                                #         "a:FirmarVoucher": "false",
                                                #         "a:MerchantID": "123456789",
                                                #         "a:PlanId": "1",
                                                #         "a:PlanNombre": "SIN PLAN",
                                                #         "a:PlanNroPlan": "0",
                                                #         "a:PlanNroTipoPlan": "1",
                                                #         "a:PlanVentaId": "0",
                                                #         "a:SucursalDireccion": "DIRECCION 1234",
                                                #         "a:SucursalNombre": "CASA CENTRAL",
                                                #         "a:TarjetaDocIdentidad": "null",
                                                #         "a:TarjetaMedio": "NFC",
                                                #         "a:TarjetaNombre": "VISA",
                                                #         "a:TarjetaTitular": "PAYWAVE//VISA",
                                                #         "a:TarjetaVencimiento": "*/*",
                                                #         "a:TerminalID": "VI197101",
                                                #         "a:TextoAdicional": "null",
                                                #         "a:TipoCuentaId": "0",
                                                #         "a:TipoCuentaNombre": "null",
                                                #         "a:TransaccionFechaHora": "2023-02-22T12:36:05"
                                                #     },
                                                #     "a:MonedaISO": "0858",
                                                #     "a:Monto": "10000",
                                                #     "a:MontoCashBack": "0",
                                                #     "a:MontoPropina": "0",
                                                #     "a:Operacion": "VTA",
                                                #     "a:TarjetaAlimentacion": "false",
                                                #     "a:TarjetaExtranjera": "false",
                                                #     "a:TarjetaIIN": "455110",
                                                #     "a:TarjetaNro": "******0043",
                                                #     "a:TarjetaPrestaciones": "false"
                                                # },
                                                # "a:EsOffline": "false",
                                                # "a:Lote": "2",
                                                # "a:MsgRespuesta": "APROBADA",
                                                # "a:NroAutorizacion": "E00002",
                                                # "a:Resp_CodigoRespuesta": "0",
                                                # "a:Resp_EstadoAvance": "ESTADOAVANCE_FINALIZADA_CORRECTAMENTE",
                                                # "a:Resp_MensajeError": "null",
                                                # "a:Resp_TokenSegundosReConsultar": "0",
                                                # "a:Resp_TransaccionFinalizada": "true",
                                                # "a:TarjetaId": "2",
                                                # "a:TarjetaTipo": "CRE",
                                                # "a:Ticket": "2",
                                                # "a:TokenNro": "D0CFAB0F-06EE-4757-8BD0-F34434D632ED",
                                                # "a:TransaccionId": "1462791",
                                                # "a:Voucher": {
                                                #     "@xmlns:b": "http://schemas.microsoft.com/2003/10/Serialization/Arrays",
                                                #     "b:string": [
                                                #         "--",
                                                #         "#CF#",
                                                #         "22//02//2023                           12:36",
                                                #         "#LOGO#",
                                                #         "/H                VENTA VISA                /N",
                                                #         "EPIKUY",
                                                #         "RUT: 111111110197",
                                                #         "DIRECCION 1234",
                                                #         "null",
                                                #         "#CF#",
                                                #         "#CF#",
                                                #         "CREDITO - ON LINE - CLESS",
                                                #         "Com.: 123456789            Term.: VI197101",
                                                #         "Ticket: 2                          Lote: 2",
                                                #         "Tar.: *****0043         Vto.: *//**",
                                                #         "Plan Venta: SIN PLAN(1)",
                                                #         "Plan//Cuotas: 0//1              Aut.: E00002",
                                                #         "No Fact.: 1234",
                                                #         "null",
                                                #         "Importe:                          $ 100,00",
                                                #         "Ley 19210:                         $ -2,43",
                                                #         "/HTOTAL:                             $ 97,57/N",
                                                #         "Aplica dev. IVA-Ley 19210",
                                                #         "Sin nro. factura no aplica ley",
                                                #         "null",
                                                #         "Imp. Factura:                     $ 100,00",
                                                #         "Imp. Gravado TRX:                  $ 81,00",
                                                #         "VISA CREDITO                A0000000031010",
                                                #         "null",
                                                #         "#CF#",
                                                #         "#CF#",
                                                #         "NO REQUIERE PIN NI OTROS DATOS",
                                                #         "PAYWAVE//VISA",
                                                #         "#CF#",
                                                #         "#CF#",
                                                #         "/I          * COPIA COMERCIO *          /N",
                                                #         "#CF#",
                                                #         "#BR#",
                                                #         "#CF#",
                                                #         "22//02//2023                           12:36",
                                                #         "#LOGO#",
                                                #         "/H                VENTA VISA                /N",
                                                #         "EPIKUY",
                                                #         "RUT: 111111110197",
                                                #         "DIRECCION 1234",
                                                #         "null",
                                                #         "#CF#",
                                                #         "#CF#",
                                                #         "CREDITO - ON LINE - CLESS",
                                                #         "Com.: 123456789            Term.: VI197101",
                                                #         "Ticket: 2                          Lote: 2",
                                                #         "Tar.: *****0043         Vto.: *//**",
                                                #         "Plan Venta: SIN PLAN(1)",
                                                #         "Plan//Cuotas: 0//1              Aut.: E00002",
                                                #         "No Fact.: 1234",
                                                #         "null",
                                                #         "Importe:                          $ 100,00",
                                                #         "Ley 19210:                         $ -2,43",
                                                #         "/HTOTAL:                             $ 97,57/N",
                                                #         "Aplica dev. IVA-Ley 19210",
                                                #         "Sin nro. factura no aplica ley",
                                                #         "null",
                                                #         "Imp. Factura:                     $ 100,00",
                                                #         "Imp. Gravado TRX:                  $ 81,00",
                                                #         "VISA CREDITO                A0000000031010",
                                                #         "null",
                                                #         "#CF#",
                                                #         "NO REQUIERE PIN NI OTROS DATOS",
                                                #         "null",
                                                #         "#CF#",
                                                #         "PAYWAVE//VISA",
                                                #         "#CF#",
                                                #         "#CF#",
                                                #         "/I          * COPIA CLIENTE *           /N",
                                                #         "#CF#",
                                                #         "null"
                                                #     ]
                                                # }
                                                # }



                                                return new_json['s:Envelope']['s:Body']['ConsultarTransaccionResponse']['ConsultarTransaccionResult']

                                            #     return {
                                            #     "@xmlns:a": "http://schemas.datacontract.org/2004/07/TransActV4ConcentradorWS.TransActV4Concentrador",
                                            #     "@xmlns:i": "http://www.w3.org/2001/XMLSchema-instance",
                                            #     "a:Aprobada": "true",
                                            #     "a:CodRespAdq": "00",
                                            #     "a:DatosTransaccion": {
                                            #     "a:Cuotas": "1",
                                            #     "a:DecretoLeyAplicado": "true",
                                            #     "a:DecretoLeyMonto": "0",
                                            #     "a:DecretoLeyNro": "19210",
                                            #     "a:EmisorId": "0",
                                            #     "a:Extendida": {
                                            #     "a:CuentaNro": "null",
                                            #     "a:DecretoLeyAdqId": "6",
                                            #     "a:DecretoLeyId": "1",
                                            #     "a:DecretoLeyNom": "CONSUMIDOR FINAL",
                                            #     "a:DecretoLeyVoucher": "Aplica dev. IVA-Ley 19210 | Sin nro. factura no aplica ley",
                                            #     "a:EmisorNombre": "DESCONOCIDO",
                                            #     "a:EmpresaNombre": "EPIKUY",
                                            #     "a:EmpresaRUT": "111111110197",
                                            #     "a:EmvAppId": "A0000000041010",
                                            #     "a:EmvAppName": "Mastercard",
                                            #     "a:FacturaMonto": "15000",
                                            #     "a:FacturaMontoGravado": "1800",
                                            #     "a:FacturaMontoGravadoTrn": "1200",
                                            #     "a:FacturaMontoIVA": "0",
                                            #     "a:FacturaMontoIVATrn": "0",
                                            #     "a:FacturaNro": "1234",
                                            #     "a:FirmarVoucher": "true",
                                            #     "a:MerchantID": "123456789",
                                            #     "a:PlanId": "1",
                                            #     "a:PlanNombre": "SIN PLAN",
                                            #     "a:PlanNroPlan": "0",
                                            #     "a:PlanNroTipoPlan": "1",
                                            #     "a:PlanVentaId": "0",
                                            #     "a:SucursalDireccion": "DIRECCION 1234",
                                            #     "a:SucursalNombre": "CASA CENTRAL",
                                            #     "a:TarjetaDocIdentidad": "null",
                                            #     "a:TarjetaMedio": "CHI",
                                            #     "a:TarjetaNombre": "MASTERCARD",
                                            #     "a:TarjetaTitular": "CRESPI//JUAN",
                                            #     "a:TarjetaVencimiento": "*/*",
                                            #     "a:TerminalID": "FI197101",
                                            #     "a:TextoAdicional": "null",
                                            #     "a:TipoCuentaId": "0",
                                            #     "a:TipoCuentaNombre": "null",
                                            #     "a:TransaccionFechaHora": "2023-03-08T15:17:39"
                                            #     },
                                            #     "a:MonedaISO": "0858",
                                            #     "a:Monto": "10000",
                                            #     "a:MontoCashBack": "0",
                                            #     "a:MontoPropina": "0",
                                            #     "a:Operacion": "VTA",
                                            #     "a:TarjetaAlimentacion": "false",
                                            #     "a:TarjetaExtranjera": "false",
                                            #     "a:TarjetaIIN": "522861",
                                            #     "a:TarjetaNro": "522861****2881",
                                            #     "a:TarjetaPrestaciones": "false"
                                            #     },
                                            #     "a:EsOffline": "false",
                                            #     "a:Lote": "2",
                                            #     "a:MsgRespuesta": "APROBADA",
                                            #     "a:NroAutorizacion": "E02002",
                                            #     "a:Resp_CodigoRespuesta": "0",
                                            #     "a:Resp_EstadoAvance": "ESTADOAVANCE_FINALIZADA_CORRECTAMENTE",
                                            #     "a:Resp_MensajeError": "null",
                                            #     "a:Resp_TokenSegundosReConsultar": "0",
                                            #     "a:Resp_TransaccionFinalizada": "true",
                                            #     "a:TarjetaId": "1",
                                            #     "a:TarjetaTipo": "CRE",
                                            #     "a:Ticket": "2",
                                            #     "a:TokenNro": "6580F8D7-4451-4B69-885F-B78C93C74A13",
                                            #     "a:TransaccionId": "1465104",
                                            #     "a:Voucher": {
                                            #     "@xmlns:b": "http://schemas.microsoft.com/2003/10/Serialization/Arrays",
                                            #     "b:string": [
                                            #     "--",
                                            #     "#CF#",
                                            #     "08//03//2023                           15:17",
                                            #     "#LOGO#",
                                            #     "/H             VENTA MASTERCARD             /N",
                                            #     "EPIKUY",
                                            #     "RUT: 111111110197",
                                            #     "DIRECCION 1234",
                                            #     "null",
                                            #     "#CF#",
                                            #     "#CF#",
                                            #     "CREDITO - ON LINE - CHIP",
                                            #     "Com.: 123456789            Term.: FI197101",
                                            #     "Ticket: 2                          Lote: 2",
                                            #     "Tar.: 522861***2881         Vto.: *//**",
                                            #     "Plan Venta: SIN PLAN(1)",
                                            #     "Plan//Cuotas: 0//1              Aut.: E02002",
                                            #     "No Fact.: 1234",
                                            #     "null",
                                            #     "/HTOTAL:                            $ 100,00/N",
                                            #     "Aplica dev. IVA-Ley 19210",
                                            #     "Sin nro. factura no aplica ley",
                                            #     "null",
                                            #     "Imp. Factura:                     $ 150,00",
                                            #     "Imp. Gravado TRX:                  $ 12,00",
                                            #     "Mastercard                  A0000000041010",
                                            #     "null",
                                            #     "#CF#",
                                            #     "#CF#",
                                            #     "Cédula: ..................................",
                                            #     "null",
                                            #     "Firma: ...................................",
                                            #     "CRESPI//JUAN",
                                            #     "#CF#",
                                            #     "#CF#",
                                            #     "/I          * COPIA COMERCIO *          /N",
                                            #     "#CF#",
                                            #     "#BR#",
                                            #     "#CF#",
                                            #     "08//03//2023                           15:17",
                                            #     "#LOGO#",
                                            #     "/H             VENTA MASTERCARD             /N",
                                            #     "EPIKUY",
                                            #     "RUT: 111111110197",
                                            #     "DIRECCION 1234",
                                            #     "null",
                                            #     "#CF#",
                                            #     "#CF#",
                                            #     "CREDITO - ON LINE - CHIP",
                                            #     "Com.: 123456789            Term.: FI197101",
                                            #     "Ticket: 2                          Lote: 2",
                                            #     "Tar.: 522861***2881         Vto.: *//**",
                                            #     "Plan Venta: SIN PLAN(1)",
                                            #     "Plan//Cuotas: 0//1              Aut.: E02002",
                                            #     "No Fact.: 1234",
                                            #     "null",
                                            #     "/HTOTAL:                            $ 100,00/N",
                                            #     "Aplica dev. IVA-Ley 19210",
                                            #     "Sin nro. factura no aplica ley",
                                            #     "null",
                                            #     "Imp. Factura:                     $ 150,00",
                                            #     "Imp. Gravado TRX:                  $ 12,00",
                                            #     "Mastercard                  A0000000041010",
                                            #     "null",
                                            #     "#CF#",
                                            #     "#CF#",
                                            #     "CRESPI//JUAN",
                                            #     "#CF#",
                                            #     "#CF#",
                                            #     "/I          * COPIA CLIENTE *           /N",
                                            #     "#CF#",
                                            #     "null"
                                            #     ]
                                            #     }
                                            # }



                                            else:
                                                logging.warning('')
                                                logging.warning('No se obtuvo una buena respuesta?')
                                                logging.warning('')
                                                return {
                                                    'error': {
                                                        'status_code': new_json['s:Envelope']['s:Body']['ConsultarTransaccionResponse']['ConsultarTransaccionResult']['a:Resp_CodigoRespuesta'],
                                                        'message': new_json['s:Envelope']['s:Body']['ConsultarTransaccionResponse']['ConsultarTransaccionResult']['a:Resp_MensajeError']
                                                    }
                                                }

        return True

    def get_latest_transact_status(self, pos_config_name, tokenNro):
        # self.ensure_one()
        # logging.warning('get_latest_transact_status')
        # latest_response = self.sudo().transact_latest_response
        # logging.warning('1. latest_response')
        # logging.warning(latest_response)
        # latest_response = json.loads(latest_response) if latest_response else False
        # logging.warning('')
        # logging.warning('2. latest_response')
        # logging.warning(latest_response)
        # logging.warning('')
        return self.consult_transAct(tokenNro)



        # return {
        #     'latest_response': latest_response,
        # }

    def proxy_transact_request(self, data, operation=False):
        ''' Necessary because Adyen's endpoints don't have CORS enabled '''
        # if data['SaleToPOIRequest']['MessageHeader']['MessageCategory'] == 'Payment': # Clear only if it is a payment request
        #     self.sudo().transact_latest_response = ''  # avoid handling old responses multiple times

        if not operation:
            operation = 'terminal_request'

        return self.transact_values(data, operation)
        # return self._proxy_transact_request_direct(data, operation)

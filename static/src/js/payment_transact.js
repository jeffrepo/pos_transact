odoo.define('pos_transact.payment', function (require) {
"use strict";

var core = require('web.core');
var rpc = require('web.rpc');
var PaymentInterface = require('point_of_sale.PaymentInterface');
const { Gui } = require('point_of_sale.Gui');
var models = require('point_of_sale.models');
// models.load_fields('res.company', 'emp_cod');
var _t = core._t;

var PaymentTransact = PaymentInterface.extend({

    send_payment_request: function (cid) {
      this._super.apply(this, arguments);
      // var line = this.pos.get_order().selected_paymentline;
      var order = this.pos.get_order();
      console.log('send_payment_request');
      console.log('');
      console.log('');

      var line = this.pending_transact_line();
        if (line){
            console.log(line.get_payment_status())
        }

      if (order.partner){
          if (order.pos.config.uy_anonymous_id && order.partner.id == order.pos.config.uy_anonymous_id[0]){
            this._reset_state();
            return this._transact_pay(cid);

          }else if(order.partner.city && order.partner.address && order.partner.state_id){
            this._reset_state();
            return this._transact_pay(cid);
          }else{

              if (line) {

                line.set_payment_status('cancel')
                this.was_cancelled = true;

                Gui.showPopup('ErrorPopup',{
                    'title': 'Missing Customer',
                    'body': 'You must have a client assigned',
                });
                return;

            }

          }

      }else{

        if (line) {

            line.set_payment_status('cancel')
            this.was_cancelled = true;

            Gui.showPopup('ErrorPopup',{
                'title': 'Missing Customer',
                'body': 'You must have a client assigned',
            });
            return;

        }



      }
    },

    send_payment_cancel: function (order, cid) {
        this._super.apply(this, arguments);
        return this._transact_cancel();
    },
    close: function () {
        this._super.apply(this, arguments);
    },

    set_most_recent_service_id(id) {
        this.most_recent_service_id = id;
    },

    pending_transact_line() {
      return this.pos.get_order().paymentlines.find(
        paymentLine => paymentLine.payment_method.use_payment_terminal === 'transact' && (!paymentLine.is_done()));
    },

    // private methods
    _reset_state: function () {
        this.was_cancelled = false;
        this.remaining_polls = 4;
        clearTimeout(this.polling);
    },

    _handle_odoo_connection_failure: function (data) {
        // handle timeout
        console.log('');
        console.log('_handle_odoo_connection_failure');
        console.log(data);
        console.log('');
        console.log('');
        var line = this.pending_transact_line();
        if (line) {
            line.set_payment_status('retry');
        }
        this._show_error(_t('Could not connect to the Odoo server, please check your internet connection and try again.'));

        return Promise.reject(data); // prevent subsequent onFullFilled's from being called
    },

    _call_transact: function (data, operation) {
        return rpc.query({
            model: 'pos.payment.method',
            method: 'proxy_transact_request',
            args: [[this.payment_method.id], data, operation],
        }, {
            // When a payment terminal is disconnected it takes Adyen
            // a while to return an error (~6s). So wait 10 seconds
            // before concluding Odoo is unreachable.
            timeout: 10000,
            shadow: true,
        }).catch(this._handle_odoo_connection_failure.bind(this));
    },

    _transact_get_sale_id: function () {
        var config = this.pos.config;
        return _.str.sprintf('%s (ID: %s)', config.display_name, config.id);
    },

    _transact_common_message_header: function () {
        var config = this.pos.config;
        this.most_recent_service_id = Math.floor(Math.random() * Math.pow(2, 64)).toString(); // random ID to identify request/response pairs
        this.most_recent_service_id = this.most_recent_service_id.substring(0, 10); // max length is 10

        return {
            'ProtocolVersion': '3.0',
            'MessageClass': 'Service',
            'MessageType': 'Request',
            'SaleID': this._transact_get_sale_id(config),
            'ServiceID': this.most_recent_service_id,
            'POIID': this.payment_method.transact_terminal_identifier
        };
    },

    _transact_pay_data: function () {
        var order = this.pos.get_order();
        var config = this.pos.config;
        var line = order.selected_paymentline;
        var self = this;
        var emp_cod = '', hash = '', moneda_iso = '', factura_nro = '', term_cod = '', url_conector = "";;

        console.log('_transact_pay_data');
        console.log('');

        if(order.get_tax_details().length != 1 && line.amount != order.get_total_with_tax().toFixed(2)){
          line.set_payment_status('cancel')
          this.was_cancelled = true;

          Gui.showPopup('ErrorPopup',{
              'title': 'Pago Parcial',
              'body': 'No se puede realizar porque hay Productos con distintos Impuestos',
          });


        }else {
          if(order.pos.company.url_conector){
            url_conector = order.pos.company.url_conector
          }
          if(order.pos.config.term_cod){
            term_cod = order.pos.config.term_cod;
          }

          if(order.pos.company.emp_cod){
            emp_cod = order.pos.company.emp_cod
          }
          if(order.pos.company.hash){
            hash = order.pos.company.hash;
          }
          if(order.pos.company.moneda_ISO){
            moneda_iso = order.pos.company.moneda_ISO;
          }
          if(order.uid){
            var order_uid = order.uid.replace('-','');
            order_uid = order_uid.replace('-','');
            factura_nro = order_uid;
          }

          var factura_monto_iva = 0, new_total_order = 0;
          var factura_monto_grabado = 0;

          if(order.get_tax_details().length>1){

            order.get_tax_details().forEach((impuesto) => {
                factura_monto_iva += impuesto.amount;
            })

            order.get_orderlines().forEach((x) => {

              for (let key in x.get_tax_details()) {
                if(x.get_tax_details()[key]>0){
                  new_total_order += x.get_price_with_tax();
                }
              }

            })
            factura_monto_grabado = new_total_order - factura_monto_iva;

          }else{
            if(order.get_tax_details()[0].tax.amount > 0){
              var calculo_iva = 1 + (order.get_tax_details()[0].tax.amount / 100);
              factura_monto_iva = order.get_tax_details()[0].amount;
              factura_monto_grabado = order.get_total_with_tax() - factura_monto_iva;
            }else {
              factura_monto_iva = 0;
              factura_monto_grabado = 0;
            }
          }

          var partner = "false";

          if(order.pos.config.uy_anonymous_id && order.partner.id == order.pos.config.uy_anonymous_id[0]){
              partner = "true";
          }


        //Monto grabado es 0 si es exento
          var data = {
              'emisor_id':0,
              'emp_cod':emp_cod,
              'emp_hash':hash,
              'factura_consumidor_final':partner,
              'factura_monto': order.get_total_with_tax() * 100,
              'factura_monto_gravado': factura_monto_grabado * 100,
              // 'factura_monto_gravado': 100 * 100,
              'factura_monto_iva': factura_monto_iva * 100,
              'factura_nro':factura_nro,
              'moneda_iso':moneda_iso,
              'monto': line.amount * 100,
              'monto_cash_back':0,
              'monto_propina':0,
              'operacion':'VTA',
              'tarjeta_id':0,
              'term_cod':term_cod,
              'url_conector': url_conector,
          };

          if (config.transact_ask_customer_for_tip) {
              data.SaleToPOIRequest.PaymentRequest.SaleData.SaleToAcquirerData = "tenderOption=AskGratuity";
          }

          return data;

        }


    },

    _transact_pay: function (cid) {
        var self = this;
        var order = this.pos.get_order();

        if (order.selected_paymentline.amount < 0) {
            this._show_error(_t('Cannot process transactions with negative amount.'));
            return Promise.resolve();
        }

        if (order === this.poll_error_order) {
            delete this.poll_error_order;
            return self._transact_handle_response({});
        }

        var data = this._transact_pay_data();
        var line = order.paymentlines.find(paymentLine => paymentLine.cid === cid);
        line.setTerminalServiceId(this.most_recent_service_id);
        return this._call_transact(data).then(function (data) {
            return self._transact_handle_response(data);
        });
    },

    _transact_cancel: function (ignore_error) {
      console.log('_transact_cancel');
      console.log('');
        var self = this;
        var config = this.pos.config;
        var previous_service_id = this.most_recent_service_id;
        var order = this.pos.get_order();
        var line = order.selected_paymentline;
        var emp_cod = '', hash = '', moneda_iso = '', factura_nro = '', term_cod = '';
        var header = _.extend(this._transact_common_message_header(), {
            'MessageCategory': 'Abort',
        });

        if(order.pos.config.term_cod){
          term_cod = order.pos.config.term_cod;
        }

        if(order.pos.company.emp_cod){
          emp_cod = order.pos.company.emp_cod
        }
        if(order.pos.company.hash){
          hash = order.pos.company.hash
        }
        if(order.pos.company.moneda_ISO){
          moneda_iso = order.pos.company.moneda_ISO
        }

        if(order.uid){
          var order_uid = order.uid.replace('-','');
          order_uid = order_uid.replace('-','');
          factura_nro = order_uid;
        }

        var factura_monto_iva = 0;
        var factura_monto_grabado = 0;

        if(order.get_tax_details().length>1){

          order.get_tax_details().forEach((impuesto) => {
              factura_monto_iva += impuesto.amount;
          })

          order.get_orderlines().forEach((x) => {

            for (let key in x.get_tax_details()) {

              if(x.get_tax_details()[key]>0){
                new_total_order += x.get_price_with_tax();
              }

            }

          })

          factura_monto_grabado = new_total_order - factura_monto_iva;

        }else{
          if(order.get_tax_details()[0].tax.amount > 0){
            var calculo_iva = 1 + (order.get_tax_details()[0].tax.amount / 100);
            factura_monto_iva = order.get_tax_details()[0].amount;
            factura_monto_grabado = order.get_total_with_tax() - factura_monto_iva;
          }else {
            factura_monto_iva = 0;
            factura_monto_grabado = 0;
          }
        }

        var partner = "false";

        if(order.pos.config.uy_anonymous_id && order.partner.id == order.pos.config.uy_anonymous_id[0]){
            partner = "true";
        }

        var data = {
          'emisor_id':0,
          'emp_cod':emp_cod,
          'emp_hash':hash,
          'factura_consumidor_final':partner,
          'factura_monto': order.get_total_with_tax() * 100,
          'factura_monto_gravado': factura_monto_grabado * 100,
          'factura_monto_iva': factura_monto_iva * 100,
          'factura_nro':factura_nro,
          'moneda_iso':moneda_iso,
          'monto': line.amount * 100,
          'monto_cash_back':0,
          'monto_propina':0,
          'operacion':'VTA',
          'tarjeta_id':0,
          'term_cod':term_cod,
        };

        return this._call_transact(data).then(function (data) {
            // Only valid response is a 200 OK HTTP response which is
            // represented by true.
            if (! ignore_error && data !== true) {
                self._show_error(_t('Cancelling the payment failed. Please cancel it manually on the payment terminal.'));
                self.was_cancelled = !!self.polling;
            }
        });
    },

    _convert_receipt_info: function (output_text) {
        return output_text.reduce(function (acc, entry) {
            var params = new URLSearchParams(entry.Text);

            if (params.get('name') && !params.get('value')) {
                return acc + _.str.sprintf('<br/>%s', params.get('name'));
            } else if (params.get('name') && params.get('value')) {
                return acc + _.str.sprintf('<br/>%s: %s', params.get('name'), params.get('value'));
            }

            return acc;
        }, '');
    },

    _poll_for_response: function (resolve, reject) {
        console.log('');
        console.log('_poll_for_response 1');
        console.log('');
        console.log('');
        var self = this;
        var order = self.pos.get_order();
        if (this.was_cancelled) {
            resolve(false);
            return Promise.resolve();
        }

        return rpc.query({
            model: 'pos.payment.method',
            method: 'get_latest_transact_status',
            args: [[this.payment_method.id], this._transact_get_sale_id(), order.get_TokenNro()],
        }, {
            timeout: 5000,
            shadow: true,
        }).catch(function (data) {
            if (self.remaining_polls != 0) {
                self.remaining_polls--;
            } else {
                reject();
                self.poll_error_order = self.pos.get_order();
                return self._handle_odoo_connection_failure(data);
            }
            // This is to make sure that if 'data' is not an instance of Error (i.e. timeout error),
            // this promise don't resolve -- that is, it doesn't go to the 'then' clause.
            return Promise.reject(data);
        }).then(function (status) {
            console.log('');
            console.log('status');
            console.log(status);
            var notification = false;
            if('latest_response' in status){
              notification = status.latest_response;
            }else{
              notification = status
            }

            var order = self.pos.get_order();
            var line = self.pending_transact_line() || resolve(false);
            console.log('');
            console.log('notification :D');
            console.log(notification);
            console.log('');
            console.log('');
            console.log('');
            var error = 'error' in notification;

            if (notification && error == false){

                if ('a:Resp_TokenSegundosReConsultar' in notification && 'a:Resp_TransaccionFinalizada' in notification && notification['a:Resp_TokenSegundosReConsultar'] == '0' && notification['a:Aprobada'] == 'true' ) {
                  var config = self.pos.config;
                  var metodos_pago = self.pos.payment_methods;
                  var id_pago = 0;
                  var monto_total = 0;
                  var nombre_pago = '';
                  metodos_pago.forEach((m_p) => {
                    if("a:DatosTransaccion" in notification && "a:Extendida" in notification["a:DatosTransaccion"] && "a:EmvAppName" in notification["a:DatosTransaccion"]["a:Extendida"] && "a:TarjetaTipo" in notification){
                       if(notification["a:TarjetaTipo"] == m_p.tarjeta_tipo && parseInt(notification["a:TarjetaId"]) == m_p.tarjeta_id){
                        id_pago = m_p.id
                        nombre_pago = m_p.name
                        monto_total = parseFloat(notification["a:DatosTransaccion"]["a:Monto"]);
                      }
                    }
                  });
                  var posicion = 0
                  if(id_pago != 0 ){
                    order.paymentlines.forEach((line) => {
                      if(line.payment_method.use_payment_terminal == "transact" && order.paymentlines[posicion].nuevo_metodo_pago_id == false){
                        order.paymentlines[posicion].set_nuevo_metodo_pago_id(id_pago);
                        order.paymentlines[posicion].set_nuevo_metodo_pago_nombre(nombre_pago);
                      }

                      posicion += 1;
                    });

                  }

                  resolve(true);
                }else if( 'a:Resp_TokenSegundosReConsultar' in notification && 'a:Resp_TransaccionFinalizada' in notification && notification['a:Resp_TokenSegundosReConsultar'] == '0' && notification['a:Aprobada'] == 'false' ){
                    resolve(false);

                    Gui.showPopup('ErrorPopup',{
                        'title': 'Estado transacción',
                        'body': notification['a:MsgRespuesta'],
                    });

                    line.set_payment_status('retry');
                    reject();
                }
            } else if ('error' in notification) {

              resolve(false);

              Gui.showPopup('ErrorPopup',{
                  'title': 'Estatus code:' + notification['error']['status_code'],
                  'body': notification['error']['message'],
              });

              line.set_payment_status('retry');
              reject();

            }else {
                line.set_payment_status('waitingCard')
            }
        });
    },

    _transact_handle_response: function (response) {
        console.log('Response --->');
        console.log(response);
        var order = this.pos.get_order();
        if(response && 'tokenNro' in response){
          order.set_TokenNro(response['tokenNro']);
        }

        var line = this.pending_transact_line();

        if (response.error && response.error.status_code != 200) {
            this._show_error(_t('Response code: '+response.error.status_code + ' '+ response.error.message));
            line.set_payment_status('force_done');
            return Promise.resolve();
        }

        response = response.SaleToPOIRequest;
        if (response && response.EventNotification && response.EventNotification.EventToNotify == 'Reject') {
            var msg = '';
            if (response.EventNotification) {
                var params = new URLSearchParams(response.EventNotification.EventDetails);
                msg = params.get('message');
            }

            this._show_error(_.str.sprintf(_t('An unexpected error occurred. Message from TRANSACT: %s'), msg));
            if (line) {
                line.set_payment_status('force_done');
            }

            return Promise.resolve();
        } else {
            line.set_payment_status('waitingCard');
            return this.start_get_status_polling()
        }
    },

    start_get_status_polling() {
        var self = this;
        var res = new Promise(function (resolve, reject) {
            // clear previous intervals just in case, otherwise
            // it'll run forever
            clearTimeout(self.polling);
            self._poll_for_response(resolve, reject);
            self.polling = setInterval(function () {
                self._poll_for_response(resolve, reject);
            }, 5500);
        });

        // make sure to stop polling when we're done
        res.finally(function () {
            self._reset_state();
        });

        return res;
    },

    _show_error: function (msg, title) {
        console.log('the title');
        console.log(msg);
        console.log(title);
        if (!title) {
            title =  _t('TRANSACT Error');
        }
        Gui.showPopup('ErrorPopup',{
            'title': title,
            'body': msg,
        });
    },

});

return PaymentTransact;
});

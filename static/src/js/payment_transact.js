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
      var line = this.pos.get_order().selected_paymentline;
      var order = this.pos.get_order();
      this._reset_state();
      return this._transact_pay(cid);
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

        // var any_fields = new Promise(function () {
        //     // clear previous intervals just in case, otherwise
        //     // it'll run forever
        //     clearTimeout(self.polling);
        //     self._call_fields();
        //     self.polling = setInterval(function () {
        //         self._call_fields();
        //     }, 5500);
        // });
        // console.log('');
        // console.log('');
        // console.log('------------');
        // console.log(any_fields);
        // console.log(any_fields.emp_cod);
        // console.log(order);
        // console.log('');
        // console.log('');
        // console.log('');
        //
        // var emp_cod = "";
        // var moneda_iso = "";
        // var hash = "";
        //
        // if(any_fields){
        //   emp_cod = any_fields['emp_cod']
        //   moneda_iso = any_fields['moneda_iso']
        //   hash = any_fields['hash']
        // }
        var data = {
            'emisor_id':0,
            'emp_cod':'NEWAGE',
            'emp_hash':'DF4D21265D1F2F1DDF4D21265D1F2F1D',
            'factura_consumidor_final':'true',
            'factura_monto':100,
            'factura_monto_gravado':100,
            'factura_monto_iva':100,
            'factura_nro':1234,
            'moneda_iso':'0858',
            'monto':100,
            'monto_cash_back':0,
            'monto_propina':0,
            'operacion':'VTA',
            'tarjeta_id':0,
            'term_cod':'T00001'
        };
        // console.log('data --');
        // console.log(data);
        // console.log(config);
        if (config.transact_ask_customer_for_tip) {
            data.SaleToPOIRequest.PaymentRequest.SaleData.SaleToAcquirerData = "tenderOption=AskGratuity";
        }

        return data;
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
        var self = this;
        var config = this.pos.config;
        var previous_service_id = this.most_recent_service_id;
        var header = _.extend(this._transact_common_message_header(), {
            'MessageCategory': 'Abort',
        });

        // console.log('Llamando a los campos');
        // var any_fields = this._call_fields();
        // console.log(any_fields);
        // console.log(any_fields['emp_cod']);
        // console.log('');
        // console.log('');
        //
        // var emp_cod = "";
        // var moneda_iso = "";
        // var hash = "";
        //
        // if(any_fields){
        //   emp_cod = any_fields['emp_cod']
        //   moneda_iso = any_fields['moneda_iso']
        //   hash = any_fields['hash']
        // }
        var data = {
            'emisor_id':0,
            'emp_cod':'NEWAGE',
            'emp_hash':'DF4D21265D1F2F1DDF4D21265D1F2F1D',
            'factura_consumidor_final':'true',
            'factura_monto':100,
            'factura_monto_gravado':100,
            'factura_monto_iva':100,
            'factura_nro':1234,
            'moneda_iso':'0858',
            'monto':100,
            'monto_cash_back':0,
            'monto_propina':0,
            'operacion':'VTA',
            'tarjeta_id':0,
            'term_cod':'T00001'
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
        var self = this;
        if (this.was_cancelled) {
            resolve(false);
            return Promise.resolve();
        }

        return rpc.query({
            model: 'pos.payment.method',
            method: 'get_latest_transact_status',
            args: [[this.payment_method.id], this._transact_get_sale_id()],
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
            var notification = status.latest_response;
            var order = self.pos.get_order();
            var line = self.pending_transact_line() || resolve(false);
            console.log('notification :D');
            console.log(notification);
            console.log(notification['s:Envelope']['s:Body']);
            if (notification) {
                console.log('good notification');
                // var response = notification.SaleToPOIResponse.PaymentResponse.Response;
                // var additional_response = new URLSearchParams(response.AdditionalResponse);

                if (notification['s:Envelope']['s:Body']['PostearTransaccionResponse']['PostearTransaccionResult']['a:Resp_CodigoRespuesta'] == '0') {
                    console.log('Sorry for party rock');
                    var config = self.pos.config;
                    // var payment_response = notification.SaleToPOIResponse.PaymentResponse;
                    // var payment_result = payment_response.PaymentResult;
                    //
                    // var cashier_receipt = payment_response.PaymentReceipt.find(function (receipt) {
                    //     return receipt.DocumentQualifier == 'CashierReceipt';
                    // });
                    //
                    // if (cashier_receipt) {
                    //     line.set_cashier_receipt(self._convert_receipt_info(cashier_receipt.OutputContent.OutputText));
                    // }
                    //
                    // var customer_receipt = payment_response.PaymentReceipt.find(function (receipt) {
                    //     return receipt.DocumentQualifier == 'CustomerReceipt';
                    // });
                    //
                    // if (customer_receipt) {
                    //     line.set_receipt_info(self._convert_receipt_info(customer_receipt.OutputContent.OutputText));
                    // }
                    //
                    // var tip_amount = payment_result.AmountsResp.TipAmount;
                    // if (config.transact_ask_customer_for_tip && tip_amount > 0) {
                    //     order.set_tip(tip_amount);
                    //     line.set_amount(payment_result.AmountsResp.AuthorizedAmount);
                    // }
                    //
                    // line.transaction_id = additional_response.get('pspReference');
                    // line.card_type = additional_response.get('cardType');
                    // line.cardholder_name = additional_response.get('cardHolderName') || '';
                    resolve(true);
                } else {
                    var message = additional_response.get('message');
                    self._show_error(_.str.sprintf(_t('Message from TRANSACT: %s'), message));

                    // this means the transaction was cancelled by pressing the cancel button on the device
                    if (message.startsWith('108 ')) {
                        resolve(false);
                    } else {
                        line.set_payment_status('retry');
                        reject();
                    }
                }
            } else {
                line.set_payment_status('waitingCard')
            }
        });
    },

    _transact_handle_response: function (response) {
        console.log('Response --->');
        console.log(response);
        var line = this.pending_transact_line();

        if (response.error && response.error.status_code != 200) {
            this._show_error(_t('Response code: '+response.error.status_code + ' '+ response.error.message));
            line.set_payment_status('force_done');
            return Promise.resolve();
        }

        response = response.SaleToPOIRequest;
        if (response && response.EventNotification && response.EventNotification.EventToNotify == 'Reject') {
            console.error('error from TRANSACT', response);

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

    _call_fields: function(){
      return rpc.query({
          model: 'res.company',
          method: 'customer_fields',
          args: [[]]
      },{
          timeout: 10000,
          shadow: true,
      }).catch(function(fields){
        console.log('Que tal fritos?');
        console.log(fields);
      });
    },
});

return PaymentTransact;
});

// odoo.define('pos_transact.payment', function(require) {
// "use strict";
//      var core = require('web.core');
//      var PaymentInterface = require('point_of_sale.PaymentInterface');
//      const { Gui } = require('point_of_sale.Gui');
//      const rpc = require('web.rpc');
//
//      var _t = core._t;
//
//      var PaymentTransact = PaymentInterface.extend({
//
//             send_payment_request: function(cid) {
//                 console.log('Hello Geordie');
//                 this._super.apply(this, arguments);
//                 var line = this.pos.get_order().selected_paymentline;
//                 var order = this.pos.get_order();
//                 var data = this._terminal_pay_data();
//                 var apikey = data.PaymentMethod.terminal_api_key
//                 var apipswd = data.PaymentMethod.terminal_api_pwd
//                 var terminalId = data.PaymentMethod.terminal_id
//                 this._reset_state();
//                // You can send your request from here to the terminal, and based on the response from your
//               // terminal you can set payment_status to success / retry / waiting.
//                 //line.set_payment_status('success');
//                 //return new Promise(function(resolve) {
//                  //   self._waitingResponse = self._waitingCancel;
//                  //});
//                 return this._transact_pay()
//              },
//
//             // private methods
//             _reset_state: function () {
//                 console.log('Hello Geordie 1');
//                 this.was_cancelled = false;
//                 this.last_diagnosis_service_id = false;
//                 this.remaining_polls = 4;
//                 clearTimeout(this.polling);
//             },
//
//             _call_transact: function (data, operation='sale') {
//                 console.log('Hello Geordie 2');
//                 return rpc.query({
//                     model: 'pos.payment.method',
//                     method: 'proxy_transact_request',
//                     args: [[this.payment_method.id], data, operation],
//                 }, {
//                     // When a payment terminal is disconnected it takes Adyen
//                     // a while to return an error (~6s). So wait 10 seconds
//                     // before concluding Odoo is unreachable.
//                     timeout: 10000,
//                     shadow: true,
//                 }).catch(this._handle_odoo_connection_failure.bind(this));
//             },
//             _transact_pay_data: function () {
//                 console.log('Hello Geordie 3');
//                 var order = this.pos.get_order();
//                 var config = this.pos.config;
//                 var line = order.selected_paymentline;
//                 console.log('Hello Geordie');
//                 var serial_number = false;
//                 if(config.serial_number){
//                     serial_number = config.serial_number;
//                 }
//                 var store_id = false
//                 if(config.store_id_transact){
//                     store_id = config.store_id_transact;
//                 }
//                 var config_id = false
//                 if(config.id){
//                     config_id = config.id;
//                 }
//
//                 var access_token = false;
//                 if(config.access_token){
//                     access_token = config.access_token;
//                 }
//
//                 var serial_number = false;
//                 if (config.serial_number){
//                     serial_number = config.serial_number;
//                 }
//                 var data = {
//                     'serialNumber': serial_number,
//                     'amount': line.amount,
//                     'storeId': store_id,
//                     'folioNumber': order.uid,
//                     'msi': "",
//                     "traceability": {
//                         'access_token': access_token,
//                         'type': "sale",
//                         'config_id': config_id,
//                         'serial_number': serial_number,
//                     }
//                 }
//
//                 return data;
//             },
//
//             _transact_pay: function () {
//                 console.log('Hello Geordie 4');
//                 var self = this;
//                 var order = this.pos.get_order();
//                 if (order.selected_paymentline.amount < 0) {
//                     this._show_error(_t('Cannot process transactions with negative amount.'));
//                     return Promise.resolve();
//                 }
//
//                 if (order === this.poll_error_order) {
//                     delete this.poll_error_order;
//                     return self._transact_handle_response({});
//                 }
//
//                 var data = this._transact_pay_data();
//                 return this._call_transact(data).then(function (data) {
//                     return self._transact_handle_response(data);
//                 });
//             },
//
//             _show_error: function (msg, title) {
//                 if (!title) {
//                     title =  _t('Transact Error');
//                 }
//                 Gui.showPopup('ErrorPopup',{
//                     'title': title,
//                     'body': msg,
//                 });
//             },
//
//
//             _transact_handle_response: function (response) {
//                 console.log('Hello Geordie 5');
//                 var line = this.pos.get_order().selected_paymentline;
//
//                 if (response.error && response.error.status_code != 200) {
//                     this._show_error(_t(response.error.message.toString()));
//                     line.set_payment_status('force_done');
//                     return Promise.resolve();
//                 }
//
//                 response = response.SaleToPOIRequest;
//                 if (response && response.EventNotification && response.EventNotification.EventToNotify == 'Reject') {
//                     console.error('error from Adyen', response);
//
//                     var msg = '';
//                     if (response.EventNotification) {
//                         var params = new URLSearchParams(response.EventNotification.EventDetails);
//                         msg = params.get('message');
//                     }
//
//                     this._show_error(_.str.sprintf(_t('An unexpected error occurred. Message from Adyen: %s'), msg));
//                     if (line) {
//                         line.set_payment_status('force_done');
//                     }
//
//                     return Promise.resolve();
//                 } else {
//                     line.set_payment_status('waitingCard');
//
//                     var self = this;
//                     var res = new Promise(function (resolve, reject) {
//                         // clear previous intervals just in case, otherwise
//                         // it'll run forever
//                         clearTimeout(self.polling);
//
//                         self.polling = setInterval(function () {
//                             self._poll_for_response(resolve, reject);
//                         }, 5500);
//                     });
//
//                     // make sure to stop polling when we're done
//                     res.finally(function () {
//                         self._reset_state();
//                     });
//
//                     return res;
//                 }
//             },
//
//            _terminal_pay_data: function() {
//                   console.log('Hello Geordie 6');
//                   var order = this.pos.get_order();
//                   var line = order.selected_paymentline;
//                   var data = {
//                         'Name': order.name,
//                         'OrderID': order.uid,
//                         'TimeStamp': moment().format(),
//                         'Currency': this.pos.currency.name,
//                         'RequestedAmount': line.amount,
//                         'PaymentMethod': this.payment_method
//                   };
//                  return data;
//              },
//
//          _handle_odoo_connection_failure: function (data) {
//              // handle timeout
//              console.log('Hello Geordie 9');
//              var line = this.pending_transact_line();
//              if (line) {
//                  line.set_payment_status('retry');
//              }
//             this._show_error(_t('Could not connect to the Odoo server, please check your internet connection and try again.'));
//
//             return Promise.reject(data); // prevent subsequent onFullFilled's from being called
//          },
//
//          pending_transact_line() {
//              console.log('Hello Geordie 11');
//              return this.pos.get_order().paymentlines.find(
//              paymentLine => paymentLine.payment_method.use_payment_terminal === 'transact' && (!paymentLine.is_done()));
//          },
//
//          clear_serial_id: function(id){
//            console.log('Hello Geordie 12');
//             return rpc.query({
//                model: 'pos.order',
//                method: 'delete_values',
//                args: [[],[id]],
//             }, {
//                timeout: 10000,
//                shadow: true,
//             }).then(function (ok){
//                 console.log('Un 1')
//             })
//          },
//
//          _poll_for_response: function (resolve, reject) {
//              var self = this;
//              var order = self.pos.get_order();
//              console.log('Hello Geordie 13');
//              if (this.was_cancelled) {
//                 resolve(false);
//                 return Promise.resolve();
//              }
//
//             return rpc.query({
//                 model: 'pos.payment.method',
//                 method: 'get_latest_transact_status',
//                 args: [[this.payment_method.id, ], this._transact_get_sale_id(), order.uid],
//             }, {
//                 timeout: 5000,
//                 shadow: true,
//             }).catch(function (data) {
//                 if (self.remaining_polls != 0) {
//                     self.remaining_polls--;
//                 } else {
//                     reject();
//                     self.poll_error_order = self.pos.get_order();
//                     return self._handle_odoo_connection_failure(data);
//                 }
//                 // This is to make sure that if 'data' is not an instance of Error (i.e. timeout error),
//                 // this promise don't resolve -- that is, it doesn't go to the 'then' clause.
//                 return Promise.reject(data);
//             }).then(function (status) {
//                 var notification = status.latest_response;
//                 var order = self.pos.get_order();
//                 var line = self.pending_transact_line();
//                 var additional_response = new URLSearchParams(notification.message);
// //                 si mi linea es retry que entre a un if creado para
//
//                 if (notification && notification.orderId ) {
// //                     var response = notification.SaleToPOIResponse.PaymentResponse.Response;
//                     var additional_response = new URLSearchParams(notification.message);
//
//                     if (notification.responseCode == '00' && notification.folioNumber == order.uid) {
//                         var config = self.pos.config;
// //                         Si el estado es retry meter el codigo de order.set_transact_orderId(notification); resolve(true);
//
//                         order.set_transact_orderId(notification);
//                         resolve(true);
//                     } else if(notification.responseCode != '00' && notification.folioNumber == order.uid){
// //                      Mostrar error y toda la cosas
//
//                         var message = additional_response.get('message');
//                         self._show_error(_.str.sprintf(_t('Message from Adyen: %s'), message));
//                         // this means the transaction was cancelled by pressing the cancel button on the device
//                         line.set_payment_status('retry');
//                         reject();
//                     }
//                     else {
//                         var message = additional_response.get('message');
//                         self._show_error(_.str.sprintf(_t('Message from Adyen: %s'), message));
//
//                         // this means the transaction was cancelled by pressing the cancel button on the device
//                         resolve(false);
//
//                     }
//                 } else if(notification && notification.responseCode != "00" ){
// //                     Mostrar error y toda la cosas
// //                     var message = additional_response.get('message');
//                     self._show_error(_.str.sprintf(_t(notification.message)));
//                     // this means the transaction was cancelled by pressing the cancel button on the device
// //                     Crear un RPC que que busque el pos.payment.method que lleve el numero de serial igualito al controller "serial_number", lo deje en blanco
//                     self.clear_serial_id(line.payment_method.id)
//                     resolve(false);
// //                     return Promise.resolve();
// //                     line.set_payment_status('retry');
//
// //                     reject();
//                 }
//
//                 else {
//                     line.set_payment_status('waitingCard')
//                 }
//             });
//         },
//
//         _transact_get_sale_id: function () {
//             var config = this.pos.config;
//             console.log('Hello Geordie 14');
//             return _.str.sprintf('%s (ID: %s)', config.display_name, config.id);
//         },
//
//
//      });
//     return PaymentTransact;
// });

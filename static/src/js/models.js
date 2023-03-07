odoo.define('pos_transact.models', function (require) {
const { Order, register_payment_method, Payment } = require('point_of_sale.models');
const PaymentTransact = require('pos_transact.payment');
const Registries = require('point_of_sale.Registries');

register_payment_method('transact', PaymentTransact);

const PosTransactPayment = (Payment) => class PosTransactPayment extends Payment {
    constructor(obj, options) {
      super(...arguments);
      this.nuevo_metodo_pago_id = this.nuevo_metodo_pago_id || false;
      this.nuevo_metodo_pago_nombre = this.nuevo_metodo_pago_nombre || '';
      // this.terminalServiceId = this.terminalServiceId || null;
    }

    init_from_JSON(json) {
      super.init_from_JSON(...arguments);
      this.nuevo_metodo_pago_id = json.nuevo_metodo_pago_id;
      this.nuevo_metodo_pago_nombre = json.nuevo_metodo_pago_nombre;
    }

    //@override
    export_as_JSON() {
      const json = super.export_as_JSON(...arguments);
      json.nuevo_metodo_pago_id = this.nuevo_metodo_pago_id;
      json.nuevo_metodo_pago_nombre = this.nuevo_metodo_pago_nombre;
      return json;
    }

    export_for_printing() {
      const result = super.export_for_printing(...arguments);
      result.nuevo_metodo_pago_id = this.nuevo_metodo_pago_id;
      result.nuevo_metodo_pago_nombre = this.nuevo_metodo_pago_nombre;
      return result;
    }

    set_nuevo_metodo_pago_id(nuevo_metodo_pago_id){
      this.nuevo_metodo_pago_id = nuevo_metodo_pago_id;
    }

    get_nuevo_metodo_pago_id(){
      return this.nuevo_metodo_pago_id;
    }

    set_nuevo_metodo_pago_nombre(nuevo_metodo_pago_nombre){
      this.nuevo_metodo_pago_nombre = nuevo_metodo_pago_nombre;
    }

    get_nuevo_metodo_pago_nombre(){
      return this.nuevo_metodo_pago_nombre;
    }
    // //@override
    // export_as_JSON() {
    //     const json = super.export_as_JSON(...arguments);
    //     json.terminal_service_id = this.terminalServiceId;
    //     return json;
    // }
    // //@override
    // init_from_JSON(json) {
    //     super.init_from_JSON(...arguments);
    //     this.terminalServiceId = json.terminal_service_id;
    // }
    setTerminalServiceId(id) {
        this.terminalServiceId = id;
    }
}
Registries.Model.extend(Payment, PosTransactPayment);

const PosTransactOrder = (Order) => class PosTransactOrder extends Order{
  constructor() {
      super(...arguments);
      this.tokenNro = this.tokenNro || "";
  }
  //@override
  export_as_JSON(){
      const json = super.export_as_JSON(...arguments);
      json.tokenNro = this.tokenNro;
      return json;
  }
  //@override
  init_from_JSON(json){
      super.init_from_JSON(...arguments);
      this.tokenNro = json.tokenNro;
  }
  set_TokenNro(tokenNro){
      this.tokenNro = tokenNro;
  }
  get_TokenNro(){
      return this.tokenNro;
  }
}
Registries.Model.extend(Order, PosTransactOrder);


});

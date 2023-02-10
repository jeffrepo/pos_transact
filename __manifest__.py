# -*- coding: utf-8 -*-

{
    'name': 'Pos transaction',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'sequence': 6,
    'summary': 'Pos transaction',
    'description': """
""",
    'depends': ['base','point_of_sale'],
    'data': [
    'views/pos_payment_method_views.xml',
    'views/res_company_views.xml'
    ],
    'assets':{
        'point_of_sale.assets': [
            # 'pos_transact/static/src/xml/Screens/PaymentScreen/PaymentScreen.xml',
            'pos_transact/static/src/js/payment_transact.js',
            'pos_transact/static/src/js/PaymentScreen.js',
            'pos_transact/static/src/js/models.js',
            # 'pos_transact/static/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
}

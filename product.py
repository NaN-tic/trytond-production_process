#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval, Get, If, Bool
from trytond.pool import Pool, PoolMeta

__all__ = ['ProductBom']


class ProductBom(metaclass=PoolMeta):
    __name__ = 'product.product-production.bom'

    process = fields.Many2One('production.process', 'Process',
        select=True, domain=[
            ('output_products', '=', If(Bool(Eval('product')),
                    Eval('product', 0),
                    Get(Eval('_parent_product', {}), 'id', 0))),
            ],
        depends=['product'])

    @classmethod
    def __setup__(cls):
        super(ProductBom, cls).__setup__()
        if not 'process' in cls.bom.depends:
            cls.bom.states.update({
                    'readonly': Bool(Eval('process', 0)),
                    })
            cls.bom.depends.add('process')
        if not 'process' in cls.route.depends:
            cls.route.states.update({
                    'readonly': Bool(Eval('process', 0)),
                    })
            cls.route.depends.add('process')

    @fields.depends('process', 'bom', 'route')
    def on_change_process(self):
        if self.process:
            self.bom = self.process.bom
            self.route = self.process.route

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Process = pool.get('production.process')
        for values in vlist:
            if values.get('process'):
                process = Process(values['process'])
                values['bom'] = process.bom.id
                values['route'] = process.route.id
        return super(ProductBom, cls).create(vlist)

from itertools import izip
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.modules.production.production import BOM_CHANGES
from trytond.transaction import Transaction


__all__ = ['Process', 'Step', 'BOMInput', 'BOMOutput', 'Operation', 'BOM',
    'Route', 'Production', 'StockMove']
__metaclass__ = PoolMeta


class Process(ModelSQL, ModelView):
    'Production Process'
    __name__ = 'production.process'
    name = fields.Char('Name', required=True)
    steps = fields.One2Many('production.process.step', 'process', 'Steps',
        context={
            'from_process': Eval('id'),
            },)
    bom = fields.Many2One('production.bom', 'BOM', required=True)
    route = fields.Many2One('production.route', 'Route', required=True)
    inputs = fields.Function(fields.One2Many('production.bom.input', None,
            'Inputs'), 'get_bom_field')
    outputs = fields.Function(fields.One2Many('production.bom.output', None,
            'Outputs'), 'get_bom_field')
    output_products = fields.Function(fields.Many2Many('production.bom.output',
            'bom', 'product', 'Outputs'), 'get_bom_field',
        searcher='search_bom_field')
    operations = fields.Function(fields.One2Many('production.route.operation',
            None, 'Operations'), 'get_operations')
    uom = fields.Many2One('product.uom', 'UOM', required=True)
    active = fields.Boolean('Active', select=True)

    @staticmethod
    def default_active():
        return True

    def get_bom_field(self, name):
        res = []
        if self.bom:
            res += [x.id for x in getattr(self.bom, name)]
        return res

    def get_operations(self, name):
        res = []
        if self.route:
            res += [x.id for x in self.route.operations]
        return res

    @classmethod
    def search_bom_field(cls, name, clause):
        return [tuple(('bom.' + name,)) + tuple(clause[1:])]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        BOM = pool.get('production.bom')
        Route = pool.get('production.route')
        boms_to_create = []
        routes_to_create = []
        with_boms = []
        without_boms = []
        for values in vlist:
            name = values.get('name')
            if not values.get('bom') and not values.get('route'):
                boms_to_create.append({
                        'name': name,
                        })
                routes_to_create.append({
                        'name': name,
                        'uom': values['uom'],
                        })
                without_boms.append(values)
            else:
                with_boms.append(values)
        if without_boms:
            boms = BOM.create(boms_to_create)
            routes = Route.create(routes_to_create)
            for values, bom, route in izip(without_boms, boms, routes):
                values['bom'] = bom.id
                values['route'] = route.id
        return super(Process, cls).create(with_boms + without_boms)

    @classmethod
    def delete(cls, steps):
        pool = Pool()
        BOM = pool.get('production.bom')
        Route = pool.get('production.route')
        boms = []
        routes = []
        for step in steps:
            boms.append(step.bom)
            routes.append(step.route)
        super(Process, cls).delete(steps)
        BOM.delete(boms)
        Route.delete(routes)

    def compute_factor(self, product, quantity, uom):
        '''
        Compute factor for an output product
        '''
        # TODO: Support that the same product is set as output of more
        # than one step
        for step in self.steps:
            factor = step.bom.compute_factor(product, quantity, uom)
            if factor is not None:
                return factor


class Step(ModelSQL, ModelView):
    'Production Process Step'
    __name__ = 'production.process.step'
    process = fields.Many2One('production.process', 'Process')
    name = fields.Char('Name', required=True)
    description = fields.Text('Description')
    sequence = fields.Integer('Sequence')
    inputs = fields.One2Many('production.bom.input', 'step', 'Inputs')
    outputs = fields.One2Many('production.bom.output', 'step', 'Outputs')
    operations = fields.One2Many('production.route.operation', 'step',
        'Operations',
        context={
            'from_step': Eval('id'),
            },)

    @classmethod
    def __setup__(cls):
        super(Step, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]


class BOMMixin:
    step = fields.Many2One('production.process.step', 'Step')

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Step = pool.get('production.process.step')
        for values in vlist:
            if not values.get('bom') and values.get('step'):
                values['bom'] = Step(values['step']).process.bom.id
        return super(BOMMixin, cls).create(vlist)


class BOMInput(BOMMixin):
    __name__ = 'production.bom.input'


class BOMOutput(BOMMixin):
    __name__ = 'production.bom.output'


class Operation:
    __name__ = 'production.route.operation'
    step = fields.Many2One('production.process.step', 'Step')

    @classmethod
    def __setup__(cls):
        super(Operation, cls).__setup__()
        if not cls.route.states:
            cls.route.states = {}
        new_invisible = Eval('context', {}).get('from_step', 0) != 0
        old_invisible = cls.route.states.get('invisible')
        if old_invisible:
            new_invisible = new_invisible | old_invisible
        cls.route.states.update({
                'invisible': new_invisible,
                })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Step = pool.get('production.process.step')
        for values in vlist:
            if not values.get('route') and values.get('step'):
                values['route'] = Step(values['step']).process.route.id
        return super(Operation, cls).create(vlist)

    @staticmethod
    def default_route():
        pool = Pool()
        Process = pool.get('production.process')
        Step = pool.get('production.process.step')

        process_id = Transaction().context.get('from_process')
        if process_id and process_id > 0:
            process = Process(process_id)
            return process.route.id

        step_id = Transaction().context.get('from_step')
        if step_id and step_id > 0:
            step = Step(step_id)
            if step.process:
                return step.process.route.id


class BOM:
    __name__ = 'production.bom'

    @classmethod
    def __setup__(cls):
        super(BOM, cls).__setup__()
        cls._error_messages.update({
                'cannot_delete_with_process': ('BOM "%(bom)s" cannot be '
                    'removed because it was created by process '
                    '"%(process)s".'),
                })

    @classmethod
    def delete(cls, boms):
        Process = Pool().get('production.process')
        processes = Process.search([('bom', 'in', [x.id for x in boms])],
            limit=1)
        if processes:
            process, = processes
            cls.raise_user_error('cannot_delete_with_process', {
                    'bom': processes[0].bom.rec_name,
                    'process': processes[0].rec_name,
                    })
        super(BOM, cls).delete(boms)


class Route:
    __name__ = 'production.route'

    @classmethod
    def __setup__(cls):
        super(Route, cls).__setup__()
        cls._error_messages.update({
                'cannot_delete_with_process': ('Route "%(route)s" cannot be '
                    'removed because it was created by process '
                    '"%(process)s".'),
                })

    @classmethod
    def delete(cls, routes):
        Process = Pool().get('production.process')
        processes = Process.search([('route', 'in', [x.id for x in routes])],
            limit=1)
        if processes:
            process, = processes
            cls.raise_user_error('cannot_delete_with_process', {
                    'route': process.route.rec_name,
                    'process': process.rec_name,
                    })
        super(Route, cls).delete(routes)


class Production:
    __name__ = 'production'

    process = fields.Many2One('production.process', 'Process',
        domain=[
            ('output_products', '=', Eval('product', 0)),
            ],
        states={
            'readonly': (~Eval('state').in_(['request', 'draft'])
                | ~Eval('warehouse', 0) | ~Eval('location', 0)),
            'invisible': ~Eval('product'),
            },
        depends=['product', 'state', 'warehouse', 'location'])

    @classmethod
    def __setup__(cls):
        super(Production, cls).__setup__()
        cls.bom.states.update({
                'readonly': Bool(Eval('process')),
                })
        cls.bom.depends.append('process')
        cls.quantity.states['required'] |= Bool(Eval('process'))
        cls.quantity.states['invisible'] &= ~Eval('process')
        cls.route.states.update({
                'readonly': Bool(Eval('process')),
                })
        cls.route.depends.append('process')

    @fields.depends(*(BOM_CHANGES + ['process', 'route', 'operations']))
    def on_change_process(self):
        res = {}
        if self.process:
            self.bom = self.process.bom
            res['bom'] = self.bom.id
            self.route = self.process.route
            res['route'] = self.route.id
            res.update(self.update_operations())
            res.update(self.explode_bom())
        return res

    @classmethod
    def compute_request(cls, product, warehouse, quantity, date, company):
        "Inherited from stock_supply_production"
        production = super(Production, cls).compute_request(product,
            warehouse, quantity, date, company)
        if product.boms:
            production.process = product.boms[0].process
        return production

    def _explode_move_values(self, from_location, to_location, company,
            bom_io, quantity):
        res = super(Production, self)._explode_move_values(from_location,
            to_location, company, bom_io, quantity)
        res['production_step'] = bom_io.step.id if bom_io.step else None
        return res


class StockMove:
    __name__ = 'stock.move'

    production_step = fields.Many2One('production.process.step', 'Process')

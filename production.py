
from trytond.model import ModelSQL, ModelView, DeactivableMixin, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError


__all__ = ['Process', 'Step', 'BOMInput', 'BOMOutput', 'Operation', 'BOM',
    'Route', 'Production', 'StockMove']


class Process(DeactivableMixin, ModelSQL, ModelView):
    'Production Process'
    __name__ = 'production.process'
    name = fields.Char('Name', required=True)
    steps = fields.One2Many('production.process.step', 'process', 'Steps',
        context={
            'from_route': Eval('route'),
        },
        states={
            'readonly': ~Eval('route'),
        }, depends=['route'])
    bom = fields.Many2One('production.bom', 'BOM', required=True)
    route = fields.Many2One('production.route', 'Route', required=True,
        states={
            'readonly': Bool(Eval('steps', [0])),
            },
        depends=['steps'])
    inputs = fields.Function(fields.One2Many('production.bom.input', None,
            'Inputs'), 'get_bom_field', setter='_set_bom_field')
    outputs = fields.Function(fields.One2Many('production.bom.output', None,
            'Outputs'), 'get_bom_field', setter='_set_bom_field')
    output_products = fields.Function(fields.Many2Many('production.bom.output',
            'bom', 'product', 'Outputs'), 'get_bom_field',
        searcher='search_bom_field')
    operations = fields.Function(fields.One2Many('production.route.operation',
            None, 'Operations'), 'get_operations')
    uom = fields.Many2One('product.uom', 'UOM', required=True)

    def get_bom_field(self, name):
        res = []
        if self.bom:
            res += [x.id for x in getattr(self.bom, name)]
        return res

    @classmethod
    def _set_bom_field(cls, processes, name, value):
        # Prevent NotImplementedError for One2Many
        pass

    def get_operations(self, name):
        res = []
        if self.route:
            res += [x.id for x in self.route.operations]
        return res

    @classmethod
    def search_bom_field(cls, name, clause):
        return [tuple(('bom.' + name,)) + tuple(clause[1:])]

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

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        BOM = pool.get('production.bom')
        Route = pool.get('production.route')

        vlist = [x.copy() for x in vlist]
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
            for values, bom, route in zip(without_boms, boms, routes):
                values['bom'] = bom.id
                values['route'] = route.id
        return super(Process, cls).create(with_boms + without_boms)

    @classmethod
    def copy(cls, processes, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['bom'] = None
        default['route'] = None

        res = []
        for process in processes:
            local_default = default.copy()
            local_default['name'] = '%s (*)' % process.name
            res += super(Process, cls).copy([process], default=local_default)
        return res

    @classmethod
    def write(cls, *args):
        pool = Pool()
        BOM = pool.get('production.bom')
        Route = pool.get('production.route')

        bom_args = []
        route_args = []
        actions = iter(args)
        for processes, values in zip(actions, actions):
            if values.get('name'):
                new_values = {
                    'name': values['name']
                    }

                if values.get('bom'):
                    bom_args.extend(([BOM(values['bom'])], new_values))
                else:
                    for process in processes:
                        bom_args.extend(([process.bom], new_values))

                if values.get('route'):
                    route_args.extend(([Route(values['route'])], new_values))
                else:
                    for process in processes:
                        route_args.extend(([process.route], new_values))

        super(Process, cls).write(*args)
        if bom_args:
            BOM.write(*bom_args)
        if route_args:
            Route.write(*route_args)

    @classmethod
    def delete(cls, processes):
        pool = Pool()
        BOM = pool.get('production.bom')
        Route = pool.get('production.route')
        boms = []
        routes = []
        for process in processes:
            boms.append(process.bom)
            routes.append(process.route)
        super(Process, cls).delete(processes)
        BOM.delete(boms)
        Route.delete(routes)


class Step(ModelSQL, ModelView):
    'Production Process Step'
    __name__ = 'production.process.step'
    process = fields.Many2One('production.process', 'Process')
    name = fields.Char('Name', required=True)
    description = fields.Text('Description')
    sequence = fields.Integer('Sequence')
    inputs = fields.One2Many('production.bom.input', 'step', 'Inputs', order=[
            ('step_sequence', 'ASC'),
            ])
    outputs = fields.One2Many('production.bom.output', 'step', 'Outputs',
        order=[
            ('step_sequence', 'ASC'),
            ])
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

    @classmethod
    def copy(cls, steps, default=None):
        pool = Pool()
        BOMInput = pool.get('production.bom.input')
        BOMOutput = pool.get('production.bom.output')
        Operation = pool.get('production.route.operation')

        if default is None:
            default = {}
        else:
            default = default.copy()
        default['inputs'] = None
        default['outputs'] = None
        default['operations'] = None

        res = []
        for step in steps:
            new_step, = super(Step, cls).copy([step], default=default)
            BOMInput.copy(step.inputs, {
                    'step': new_step.id,
                    'bom': new_step.process.bom.id,
                    })
            BOMOutput.copy(step.outputs, {
                    'step': new_step.id,
                    'bom': new_step.process.bom.id,
                    })
            Operation.copy(step.operations, {
                    'step': new_step.id,
                    'route': new_step.process.route.id,
                    })
            res.append(new_step)
        return res


class BOMMixin(metaclass=PoolMeta):
    step = fields.Many2One('production.process.step', 'Step')
    step_sequence = fields.Integer('Step Sequence')

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Step = pool.get('production.process.step')
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('bom') and values.get('step'):
                values['bom'] = Step(values['step']).process.bom.id
        return super(BOMMixin, cls).create(vlist)


class BOMInput(BOMMixin):
    __name__ = 'production.bom.input'


class BOMOutput(BOMMixin):
    __name__ = 'production.bom.output'


class Operation(metaclass=PoolMeta):
    __name__ = 'production.route.operation'
    step = fields.Many2One('production.process.step', 'Step')

    @classmethod
    def __setup__(cls):
        super(Operation, cls).__setup__()

        if not cls.route.states:
            cls.route.states = {}
        new_readonly = Eval('context', {}).get('from_route', 0) != 0
        readonly = cls.route.states.get('readonly')
        if readonly:
            new_readonly = new_readonly | readonly
        cls.route.states.update({
                'readonly': new_readonly,
                })

    @staticmethod
    def default_route():
        return Transaction().context.get('from_route')

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Step = pool.get('production.process.step')
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('route') and values.get('step'):
                values['route'] = Step(values['step']).process.route.id
        return super(Operation, cls).create(vlist)


class BOM(metaclass=PoolMeta):
    __name__ = 'production.bom'

    @classmethod
    def delete(cls, boms):
        Process = Pool().get('production.process')
        processes = Process.search([('bom', 'in', [x.id for x in boms])],
            limit=1)
        if processes:
            raise UserError(gettext(
                'production_process.cannot_delete_with_process',
                    bom=processes[0].bom.rec_name,
                    process=processes[0].rec_name))
        super(BOM, cls).delete(boms)


class Route(metaclass=PoolMeta):
    __name__ = 'production.route'

    @classmethod
    def delete(cls, routes):
        Process = Pool().get('production.process')
        processes = Process.search([('route', 'in', [x.id for x in routes])],
            limit=1)
        if processes:
            process, = processes
            raise UserError(gettext(
                'production_process.cannot_delete_with_process_route',
                    route=process.route.rec_name,
                    process=process.rec_name))
        super(Route, cls).delete(routes)


class Production(metaclass=PoolMeta):
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
        bom_readonly = cls.bom.states['readonly']
        cls.bom.states.update({
                'readonly': bom_readonly | Bool(Eval('process')),
                })
        cls.bom.depends.add('process')
        cls.quantity.states['required'] |= Bool(Eval('process'))
        cls.quantity.states['invisible'] &= ~Eval('process')
        cls.route.states.update({
                'readonly': Bool(Eval('process')),
                })
        cls.route.depends.add('process')

    @fields.depends('process', methods=['on_change_route', 'explode_bom'])
    def on_change_process(self):
        if self.process:
            self.bom = self.process.bom
            self.route = self.process.route
            self.on_change_route()
            self.explode_bom()

    @classmethod
    def compute_request(cls, product, warehouse, quantity, date, company,
            order_point=None):
        "Inherited from stock_supply_production"
        production = super(Production, cls).compute_request(product,
            warehouse, quantity, date, company, order_point)
        if product.boms:
            production.process = product.boms[0].process
        return production

    def _explode_move_values(self, type, bom_io, quantity):
        move = super(Production, self)._explode_move_values(type, bom_io, quantity)
        move.production_step = bom_io.step.id if bom_io.step else None
        return move


class StockMove(metaclass=PoolMeta):
    __name__ = 'stock.move'

    production_step = fields.Many2One('production.process.step', 'Process')

===================
Production Scenario
===================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install production Module::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([('name', '=', 'production_process')])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point=',')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Configuration production location::

    >>> Location = Model.get('stock.location')
    >>> warehouse, = Location.find([('code', '=', 'WH')])
    >>> production_location, = Location.find([('code', '=', 'PROD')])
    >>> warehouse.production_location = production_location
    >>> warehouse.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal(30)
    >>> template.cost_price = Decimal(20)
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create Components::

    >>> component1 = Product()
    >>> template1 = ProductTemplate()
    >>> template1.name = 'component 1'
    >>> template1.default_uom = unit
    >>> template1.type = 'goods'
    >>> template1.list_price = Decimal(5)
    >>> template1.cost_price = Decimal(1)
    >>> template1.save()
    >>> component1.template = template1
    >>> component1.save()

    >>> meter, = ProductUom.find([('name', '=', 'Meter')])
    >>> centimeter, = ProductUom.find([('name', '=', 'centimeter')])
    >>> component2 = Product()
    >>> template2 = ProductTemplate()
    >>> template2.name = 'component 2'
    >>> template2.default_uom = meter
    >>> template2.type = 'goods'
    >>> template2.list_price = Decimal(7)
    >>> template2.cost_price = Decimal(5)
    >>> template2.save()
    >>> component2.template = template2
    >>> component2.save()

Create work centers and operation types::

    >>> Route = Model.get('production.route')
    >>> OperationType = Model.get('production.operation.type')
    >>> RouteOperation = Model.get('production.route.operation')
    >>> assembly = OperationType(name='Assembly')
    >>> assembly.save()
    >>> cleaning = OperationType(name='Cleaning')
    >>> cleaning.save()
    >>> hour, = ProductUom.find([('name', '=', 'Hour')])
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> WorkCenter = Model.get('production.work_center')
    >>> WorkCenterCategory = Model.get('production.work_center.category')
    >>> category = WorkCenterCategory()
    >>> category.name = 'Default Category'
    >>> category.uom = hour
    >>> category.cost_price = Decimal('25.0')
    >>> category.save()
    >>> workcenter1 = WorkCenter()
    >>> workcenter1.name = 'Assembler Machine'
    >>> workcenter1.type = 'machine'
    >>> workcenter1.category = category
    >>> workcenter1.uom == hour
    True
    >>> workcenter1.cost_price
    Decimal('25.0')
    >>> workcenter1.save()
    >>> workcenter2 = WorkCenter()
    >>> workcenter2.name = 'Cleaner Machine'
    >>> workcenter2.type = 'machine'
    >>> workcenter2.category = category
    >>> workcenter2.cost_price = Decimal('50.0')
    >>> workcenter2.save()

Create a process definition::

    >>> Process = Model.get('production.process')
    >>> Step = Model.get('production.process.step')
    >>> BOM = Model.get('production.bom')
    >>> BOMInput = Model.get('production.bom.input')
    >>> BOMOutput = Model.get('production.bom.output')
    >>> process = Process()
    >>> process.name = 'Assembly components'
    >>> process.uom =  unit
    >>> step1 = Step()
    >>> process.steps.append(step1)
    >>> step1.name = 'First step'
    >>> input1 = BOMInput()
    >>> step1.inputs.append(input1)
    >>> input1.product = component1
    >>> input1.quantity = 5
    >>> input2 = BOMInput()
    >>> step2 = Step()
    >>> process.steps.append(step2)
    >>> step2.inputs.append(input2)
    >>> step2.name = 'Second step'
    >>> input2.product = component2
    >>> input2.quantity = 150
    >>> input2.uom = centimeter
    >>> route_operation = RouteOperation()
    >>> step2.operations.append(route_operation)
    >>> route_operation.sequence = 1
    >>> route_operation.operation_type = assembly
    >>> route_operation.work_center_category = category
    >>> route_operation.work_center = workcenter1
    >>> route_operation.time = 1
    >>> route_operation.quantity = 3
    >>> route_operation.quantity_uom = unit
    >>> step3 = Step()
    >>> process.steps.append(step3)
    >>> step3.name = 'Third step'
    >>> output = BOMOutput()
    >>> step3.outputs.append(output)
    >>> output.product = product
    >>> output.quantity = 1
    >>> route_operation = RouteOperation()
    >>> step3.operations.append(route_operation)
    >>> route_operation.sequence = 2
    >>> route_operation.operation_type = cleaning
    >>> route_operation.calculation = 'fixed'
    >>> route_operation.work_center_category = category
    >>> route_operation.work_center = workcenter2
    >>> route_operation.time = 1
    >>> process.save()
    >>> process.reload()
    >>> len(process.operations) == 2
    True
    >>> len(process.inputs) == 2
    True
    >>> len(process.outputs) == 1
    True
    >>> len(process.operations) == 2
    True
    >>> len(process.route.operations) == 2
    True
    >>> bom = process.bom
    >>> len(bom.inputs) == 2
    True
    >>> len(bom.outputs) == 1
    True
    >>> ProductBom = Model.get('product.product-production.bom')
    >>> product.processes.append(ProductBom(process=process))
    >>> product.save()
    >>> len(product.boms) == 1
    True
    >>> product.boms[0].bom == bom
    True

Create an Inventory::

    >>> Inventory = Model.get('stock.inventory')
    >>> InventoryLine = Model.get('stock.inventory.line')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory_line1 = InventoryLine()
    >>> inventory.lines.append(inventory_line1)
    >>> inventory_line1.product = component1
    >>> inventory_line1.quantity = 10
    >>> inventory_line2 = InventoryLine()
    >>> inventory.lines.append(inventory_line2)
    >>> inventory_line2.product = component2
    >>> inventory_line2.quantity = 5
    >>> inventory.save()
    >>> Inventory.confirm([inventory.id], config.context)
    >>> inventory.state
    u'done'

Make a production::

    >>> Production = Model.get('production')
    >>> Operation = Model.get('production.operation')
    >>> production = Production()
    >>> production.product = product
    >>> production.process = process
    >>> production.bom == process.bom
    True
    >>> production.route == process.route
    True
    >>> len(production.operations) == 2
    True
    >>> production.quantity = 2
    >>> sorted([i.quantity for i in production.inputs]) == [10, 300]
    True
    >>> output, = production.outputs
    >>> output.quantity == 2
    True
    >>> production.cost == Decimal('25')
    True
    >>> production.save()
    >>> Production.wait([production.id], config.context)
    >>> Production.assign_try([production.id], config.context)
    True
    >>> Production.run([production.id], config.context)
    >>> operations = [o.id for o in production.operations]
    >>> Operation.run(operations, config.context)
    >>> Operation.done(operations, config.context)
    >>> Production.done([production.id], config.context)
    >>> production.reload()
    >>> output, = production.outputs
    >>> output.state
    u'done'
    >>> config._context['locations'] = [storage.id]
    >>> product.reload()
    >>> product.quantity == 2
    True

Bom and routes can not be deleted because they are linked to process::

    >>> process.route.delete()
    Traceback (most recent call last):
        ...
    UserError: ('UserError', (u'Route "Assembly components" cannot be removed because it was created by process "Assembly components".', ''))
    >>> process.bom.delete()
    Traceback (most recent call last):
        ...
    UserError: ('UserError', (u'BOM "Assembly components" cannot be removed because it was created by process "Assembly components".', ''))

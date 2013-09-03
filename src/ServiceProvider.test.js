fixture("ServiceProvider", function() {
    this.setUp(function() {
        this.sp = new IMVU.ServiceProvider;
    });

    test("instantiates objects", function() {
        function Foo(){}
        assert['instanceof'](this.sp.create(Foo), Foo);
    });

    test("satisfies dependencies", function() {
        var timer = {};
        this.sp.register('timer', timer);

        function Foo(options) {
            this.timer = options.timer;
        }
        Foo.dependencies = ['timer'];
        var instance = this.sp.create(Foo);
        assert.equal(timer, instance.timer);
    });

    test("dependencies can be specified on prototypes too", function() {
        var service = {};
        this.sp.register('service', service);

        function Foo(options) {
            this.service = options.service;
        }
        Foo.prototype.dependencies = ['service'];
        var instance = this.sp.create(Foo);
        assert.equal(service, instance.service);
    });

    test("throws error if dependency is not satisfied", function() {
        function Foo() {
        }
        Foo.dependencies = ['timer'];
        var e = assert.throws(ReferenceError, function() {
            this.sp.create(Foo);
        }.bind(this));
        assert.equal('Unsatisfied dependencies "timer" when constructing Foo', e.message);
    });

    test('passing extra arguments', function() {
        var service = {};
        this.sp.register('service', service);
        function Foo(options) {
            this.extra = options.extra;
            this.service = options.service;
        }
        Foo.dependencies = ['service'];
        var instance = this.sp.create(Foo, {extra: 10});
        assert.equal(service, instance.service);
        assert.equal(10, instance.extra);
    });

    test('extra arguments override services', function() {
        var service1 = {};
        this.sp.register('service', service1);
        var service2 = {};
        function Foo(options) {
            this.service = options.service;
        }
        Foo.dependencies = ['service'];
        var instance = this.sp.create(Foo, {service: service2});
        assert.equal(service2, instance.service);
    });

    test('extra arguments is the last parameter', function() {
        var service1 = {};
        this.sp.register('service', service1);
        var service2 = {};
        function Foo(thing, options) {
            this.thing = thing;
            this.service = options.service;
        }
        Foo.dependencies = ['service'];
        var instance = this.sp.create(Foo, 'thing', {service: service2});
        assert.equal('thing', instance.thing);
        assert.equal(service2, instance.service);
    });

    test('passes itself into options', function() {
        function Foo(options) {
            this.serviceProvider = options.serviceProvider;
        }
        var instance = this.sp.create(Foo);
        assert.equal(this.sp, instance.serviceProvider);
    });

    test("unnecessary services aren't given", function() {
        var service = {};
        this.sp.register('service', service);

        function Foo(options) {
            this.service = options.service;
        }

        var instance = this.sp.create(Foo);
        assert.equal(undefined, instance.service);
    });

    test('trying to create a new undefined thing throws a helpful error', function(){
        var e = assert.throws(ReferenceError, function() {
            this.sp.create(undefined);
        }.bind(this));
        assert.equal('Passed bad class type "undefined" to ServiceProvider.new()', e.message);
    });

    test('trying to create a new int throws a helpful error', function(){
        var e = assert.throws(ReferenceError, function() {
            this.sp.create(10);
        }.bind(this));
        assert.equal('Passed bad class type "10" to ServiceProvider.new()', e.message);
    });

    test('attempting to get unknown services raises ReferenceError', function() {
        var e = assert.throws(ReferenceError, function() {
            this.sp.get('service');
        }.bind(this));
        assert.equal('No service registered for "service"', e.message);
    });

    test('looking up registered services', function() {
        var service = {};
        this.sp.register('service', service);
        assert.equal(service, this.sp.get('service'));
    });
});

/*global IMVU*/
(function() {
    "use strict";

    function sequence(list, action, continuation) {
        function next(index) {
            if (index < list.length) {
                action(list[index], next.bind(null, index + 1));
            } else {
                continuation();
            }
        }
        next(0);
    }

    // { beforeTest: function,
    //   afterTest: function }
    var superFixtures = [];

    function registerSuperFixture(superFixture) {
        superFixtures.push(superFixture);
    }

    // { fixtureStack: linked list of fixture objects
    //   name: string,
    //   body: function(onComplete) }
    var allTests = [];

    function asyncTest(name, func) {
        allTests.push({
            name: name,
            body: func,
        });
    }
    function test(name, fn) {
        function sync(onComplete) {
            /*jshint validthis:true*/
            fn.call(this);
            onComplete();
        }
        if (arguments.length !== 2) {
            throw new TypeError("test requires 1 or 2 arguments");
        }
        allTests.push({
            name: name,
            body: sync,
            fixtureStack: fixtureStack.top(),
        });
    }

    function runTest(test, continuation) {
        try {
            var afterTests = [];

            for (var i = 0; i < superFixtures.length; ++i) {
                var superFixture = superFixtures[i];

                var superScope = {};
                superFixture.beforeTest.call(superScope);
                afterTests.push(superFixture.afterTest.bind(superScope));
            }

            var testScope;
            if (test.fixtureStack) {
                testScope = Object.create(test.fixtureStack.fixtureObject.scope);
            } else {
                testScope = {}; // TODO: Object.create from the fixture scope?
            }

            var fixture = test.fixtureStack;
            while (undefined !== fixture) {
                var fixtureObject = fixture.fixtureObject;
                while (undefined !== fixtureObject) {
                    fixtureObject.setUp.call(testScope);
                    afterTests.push(fixtureObject.tearDown.bind(testScope));
                    fixtureObject = fixtureObject.parent;
                }
                fixture = fixture.next;
            }

            test.body.call(testScope, function () {
                while (afterTests.length) {
                    afterTests.pop()();
                }
                continuation(false, null);
            });
        } catch (e) {
            continuation(true, e.stack);
        }
    }

    function run_all(reporter, continuation) {
        sequence(allTests, function (test, next) {
            reporter({
                type: 'test-start',
                name: test.name
            });

            runTest(test, function (failed, stack) {
                if (failed) {
                    reporter({
                        type: 'test-complete',
                        name: test.name,
                        verdict: 'FAIL',
                        stack: stack
                    });
                    continuation(true); // short-circuit
                } else {
                    reporter({
                        type: 'test-complete',
                        name: test.name,
                        verdict: 'PASS'
                    });
                    next();
                }
            });
        }, function () {
            allTests = [];
            continuation(false);
        });
    }

    function nul(continuation) {
        continuation();
    }

    function registerFixture(fixtureName, obj, wrap) {
        obj = Object.create(obj);
        _.extend(obj, obj.baseFixture);

        var setUp = obj.setUp ? obj.setUp : nul;
        var tearDown = obj.tearDown ? obj.tearDown : nul;

        for (var testName in obj) {
            if (testName.substr(0, 4) !== 'test') {
                continue;
            } else {
                var self = Object.create(obj);

                asyncTest(fixtureName + '.' + testName, wrap(obj, setUp, obj[testName], tearDown));
            }
        }

        return obj;
    }

    var fixtureStack = {
        push: function(fo) {
            this._top = {
                fixtureObject: fo,
                next: this._top
            };
        },
        pop: function() {
            this._top = this._top.next;
        },
        top: function() {
            return this._top;
        },
        _top: undefined,
    };

    function FixtureObject(parent) {
        this.parent = parent;

        if (this.parent === undefined) {
            this.scope = {
                setUp: function(setUp) {
                    this.setUp = setUp;
                }.bind(this),
                tearDown: function(tearDown) {
                    this.tearDown = tearDown;
                }.bind(this),
            };
        } else {
            this.scope = this.parent.scope;
        }
    }
    FixtureObject.prototype.setUp = function defaultSetUp() {
    };
    FixtureObject.prototype.tearDown = function defaultTearDown() {
    };

    FixtureObject.prototype.extend = function(fixtureName, definition) {
        if (!(definition instanceof Function)) {
            throw new TypeError("fixture's 2nd argument must be a function");
        }

        var fixtureObject = new FixtureObject(this);

        fixtureStack.push(fixtureObject);
        try {
            definition.call(fixtureObject.scope);
        }
        finally {
            fixtureStack.pop();
        }

        return fixtureObject;
    };

    fixture = FixtureObject.prototype.extend.bind(undefined);

    function fixture(fixtureName, definition) {
        if (!(definition instanceof Function)) {
            throw new TypeError("fixture's 2nd argument must be a function");
        }

        var scope = {
            setUp: function(setUp) {
                fixtureObject.setUp = setUp;
            },
            tearDown: function(tearDown) {
                fixtureObject.tearDown = tearDown;
            },
        };
        var fixtureObject = new FixtureObject(undefined, scope);

        fixtureStack.push(fixtureObject);
        try {
            definition.call(fixtureObject.scope);
        }
        finally {
            fixtureStack.pop();
        }

        return fixtureObject;
    }

    function asyncFixture(fixtureName, obj) {
        return registerFixture(fixtureName, obj, function (fixture, setUp, body, tearDown) {
            return function (continuation) {
                setUp.call(fixture, function () {
                    body.call(fixture, function () {
                        tearDown.call(fixture, continuation);
                    });
                });
            };
        });
    }

    var AssertionError = Error;

    function fail(exception, info) {
        exception.info = info;
        throw exception;
    }

    var assert = {
        fail: function(info) {
            info = info || "assert.fail()";
            fail(new AssertionError(info));
        },

        'true': function(value) {
            if (!value) {
                fail(new AssertionError("expected truthy, actual " + IMVU.repr(value)),
                     {Value: value});
            }
        },

        'false': function(value) {
            if (value) {
                fail(new AssertionError("expected falsy, actual " + IMVU.repr(value)),
                     {Value: value});
            }
        },

        equal: function(expected, actual) {
            if (expected !== actual) {
                fail(new AssertionError('expected: ' + IMVU.repr(expected) + ', actual: ' + IMVU.repr(actual)),
                     {Expected: expected, Actual: actual});
            }
        },

        deepEqual: function(expected, actual) {
            if (!_.isEqual(expected, actual)) {
                fail(new AssertionError('expected: ' + IMVU.repr(expected) + ', actual: ' + IMVU.repr(actual)),
                     {Expected: expected, Actual: actual});
            }
        },

        nearEqual: function( expected, actual, tolerance ) {
            if( tolerance === undefined ) {
                tolerance = 0.0;
            }
            if( expected instanceof Array && actual instanceof Array ) {
                assert.equal(expected.length, actual.length);
                for( var i=0; i<expected.length; ++i ) {
                    assert.nearEqual(expected[i], actual[i], tolerance);
                }
                return;
            }
            if( Math.abs(expected - actual) > tolerance ) {
                fail( new AssertionError('expected: ' + IMVU.repr(expected) + ', actual: ' + IMVU.repr(actual) +
                                         ', tolerance: ' + IMVU.repr(tolerance) + ', diff: ' + IMVU.repr(actual-expected) ),
                      { Expected:expected, Actual:actual, Tolerance:tolerance } );
            }
        },

        notEqual: function(expected, actual) {
            if (expected instanceof Array && actual instanceof Array) {
                assert.notEqual(expected.length, actual.length);
                for (var i = 0; i < expected.length; ++i) {
                    assert.notEqual(expected[i], actual[i]);
                }
                return;
            }
            if (expected === actual) {
                fail(new AssertionError('not expected: ' + IMVU.repr(expected) + ', actual: ' + IMVU.repr(actual)),
                     {Expected: expected, Actual: actual});
            }
        },

        inArray: function(expected, array) {
            var found = false;
            _.each(array, function(element){
                if (_.isEqual(expected, element)){
                    found = true;
                }
            });
            if (!found){
                fail(new AssertionError('expected: ' + IMVU.repr(expected) + ' not found in array: ' + IMVU.repr(array)),
                     {Expected: expected, 'Array': array});
            }
        },

        'throws': function(exception, fn) {
            try {
                fn();
            } catch (e) {
                if (e instanceof exception) {
                    return e;
                }
                fail(new AssertionError('expected to throw: "' + IMVU.repr(exception) + '", actually threw: "' + IMVU.repr(e) + '"'),
                     {Expected: exception, Actual: e});
            }
            throw new AssertionError('did not throw');
        },

        instanceof: function(actual, type) {
            if(!(actual instanceof type)) {
                fail(new AssertionError(IMVU.repr(actual) + 'not instance of' + IMVU.repr(type)),
                    {Type: type, Actual: actual});
            }
        },

        // TODO: lift into separate file?
        dom: {
            hasClass: function(className, selector) {
                assert.true($(selector).hasClass(className));
            },

            notHasClass: function(className, selector) {
                assert.false($(selector).hasClass(className));
            },

            text: function(expected, selector) {
                assert.equal(expected, $(selector).text());
            },

            value: function(expected, selector) {
                assert.equal(expected, $(selector).val());
            },

            count: function(elementCount, selector) {
                assert.equal(elementCount, $(selector).length);
            },

            visible: function(selector) {
                assert.true($(selector).is(':visible'));
            },

            notVisible: function(selector) {
                assert.false($(selector).is(':visible'));
            },

            focused: function(selector) {
                var expected = $(selector)[0];
                var actual = document.activeElement;
                if (expected !== actual) {
                    throw new AssertionError(actual.outerHTML + ' has focus. expected: ' + expected.outerHTML);
                }
            },
        },
    };

    var g = 'undefined' === typeof window ? global : window;

    // synonyms
    assert.equals = assert.equal;
    assert.notEquals = assert.notEqual;
    assert['null'] = assert.equal.bind(null, null);
    assert.notNull = assert.notEqual.bind(null, null);

    g.registerSuperFixture = registerSuperFixture;
    g.test = test;
    g.run_all = run_all;
    g.fixture = fixture;
    g.repr = IMVU.repr;
    g.AssertionError = AssertionError;
    g.assert = assert;
    g.test = test;
    g.asyncTest = asyncTest;
    g.asyncFixture = asyncFixture;

    g.setTimeout = function() {
        throw new AssertionError("Don't call setTimeout in tests.  Use fakes.");
    };
    g.setInterval = function() {
        throw new AssertionError("Don't call setInterval in tests.  Use fakes.");
    };
    if (typeof process !== 'undefined') {
        process.nextTick = function() {
            throw new AssertionError("Don't call process.nextTick in tests.  Use fakes.");
        };
    }
})();

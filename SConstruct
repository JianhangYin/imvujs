import os
import multiprocessing

SetOption('num_jobs', multiprocessing.cpu_count())
print "running with -j", GetOption('num_jobs')

BASE_SOURCES = [
    'ext/underscore-1.4.2.js',
    'ext/backbone-0.9.2.js',
    'ext/easyXDM-2.4.15.118.js',
    'src/polyfill.js',
    'third-party/es5-shim/es5-shim.js',
    'src/es6-collections.js',
    'src/repr.js',
    'src/new.js',
    'src/error.js',
    'src/subclass.js',
    'src/function.js',
    'src/BaseClass.js',
    'src/ServiceProvider.js',
    'src/Random.js',
    'src/module-common.js',
    'src/rest.js',
]

WEB_SOURCES = [
    'ext/jquery-1.8.2.js'
] + BASE_SOURCES + [
    'src/module.js',
    'src/Timer.js',
]

NODE_SOURCES = BASE_SOURCES + [
    'src/node-kraken.js',
]

env = Environment(
    ENV=os.environ,
    toolpath=['tools'],
    tools=['closure', 'uglify', 'gzip', 'kraken_combine'])

BASE_CLOSURE_FLAGS = [
    '--language_in', 'ECMASCRIPT5',
    '--jscomp_error', 'ambiguousFunctionDecl',
    '--jscomp_error', 'checkDebuggerStatement',
    '--jscomp_error', 'checkRegExp',
    '--jscomp_off', 'checkTypes',
    '--jscomp_error', 'checkVars',
    '--jscomp_error', 'deprecated',
    '--jscomp_off', 'duplicate',
    '--jscomp_error', 'es5Strict',
    '--jscomp_off', 'missingProperties',
    '--jscomp_error', 'undefinedNames',
    '--jscomp_off', 'undefinedVars',
    '--jscomp_off', 'uselessCode',
    '--jscomp_error', 'globalThis',
]

targets = []

targets += env.ClosureCompiler(
    'out/imvu.js',
    ['ext/esprima.js'] + WEB_SOURCES,
    CLOSURE_FLAGS=BASE_CLOSURE_FLAGS+[
        '--formatting', 'PRETTY_PRINT',
        '--compilation_level', 'WHITESPACE_ONLY'])

targets += env.ClosureCompiler(
    'out/imvu.min.js',
    WEB_SOURCES,
    CLOSURE_FLAGS=BASE_CLOSURE_FLAGS + ["--define='KRAKEN_DEBUG=false'"])

targets += env.ClosureCompiler(
    'out/imvu.node.js',
    NODE_SOURCES,
    CLOSURE_FLAGS=BASE_CLOSURE_FLAGS+['--formatting', 'PRETTY_PRINT', '--compilation_level', 'WHITESPACE_ONLY'])

#targets += env.UglifyMinify(
#    'out/imvu.min2.js',
#    WEB_SOURCES)

env.Gzip('out/imvu.min.js.gz', 'out/imvu.min.js')

targets += env.CombinedModule('out/imvu.fakes.js', 'fakes/Package.js')

if 'target' in ARGUMENTS:
    env.Install(ARGUMENTS['target'], targets)
    env.Alias('install', ARGUMENTS['target'])

env.Default('out')

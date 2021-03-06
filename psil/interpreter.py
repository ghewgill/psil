"""PSIL: Python S-expresssion Intermediate Language

>>> eval(read("1"))
1
>>> eval(read("'(1 2 3)"))
[1, 2, 3]
>>> eval(read("(make-list (map (lambda (x) (* x x)) '(1 2 3)))"))
[1, 4, 9]
>>> eval(read("(apply + '(1 2))"))
3

"""

import ast
import functools
import operator
import os
import re
import sys

from . import deparse
from .symbol import Symbol
from .reader import tokenise, parse, read
from .compiler import psilc

Compile = False

Symbols = {}

class UndefinedSymbolError(Exception):
    def __init__(self, s):
        Exception.__init__(self, s)

class NotCallableError(Exception):
    pass

class SetNotSymbolError(Exception):
    pass

class TailCall(Exception):
    def __init__(self, fn, args):
        self.fn = fn
        self.args = args
    def apply(self):
        if isinstance(self.fn, Function):
            return self.fn.apply(self.args, tail=True)
        else:
            return self.fn(*self.args)
    def __str__(self):
        return str(self.fn) + ":" + str(self.args)

class Scope(object):
    NotFound = object()
    def __init__(self, parent = None):
        self.parent = parent
        self.symbols = {}
        self.globals = None
    def setglobals(self, globals):
        self.globals = globals
    def define(self, name, value):
        if name in self.symbols:
            print("*** warning: redefining", name, file=sys.stderr)
        self.symbols[name] = value
        return value
    def set(self, name, value):
        s = self
        while s is not None:
            if name in s.symbols:
                s.symbols[name] = value
                return
            s = s.parent
        raise UndefinedSymbolError(name)
    def lookup(self, name):
        s = self
        while s is not None:
            r = s.symbols.get(name, self.NotFound)
            if r is not self.NotFound:
                return (True, r)
            if s.globals is not None:
                r = s.globals.get(name, self.NotFound)
                if r is not self.NotFound:
                    return (True, r)
            s = s.parent
        return (False, None)
    def eval(self, s, tail=False):
        try:
            if isinstance(s, list) and len(s) > 0:
                f = s[0]
                if isinstance(f, Symbol):
                    if f is Symbol.define:
                        if isinstance(s[1], Symbol):
                            return self.define(s[1].name, self.eval(s[2]))
                        else:
                            return self.define(s[1][0].name, Function(s[1][0].name, s[1][1:], s[2:], self))
                    if f is Symbol.defmacro:
                        return self.define(s[1].name, Macro(s[1].name, s[2], s[3:], self))
                    if f is Symbol.if_:
                        if self.eval(s[1]):
                            return self.eval(s[2], tail)
                        elif len(s) >= 4:
                            return self.eval(s[3], tail)
                        else:
                            return None
                    if f is Symbol.lambda_:
                        return Function("lambda", s[1], s[2:], self)
                    if f is Symbol.quasiquote:
                        def qq(t, depth=1):
                            if isinstance(t, list):
                                if len(t) > 0 and isinstance(t[0], Symbol):
                                    if t[0] is Symbol.quasiquote:
                                        return [t[0], qq(t[1], depth + 1)]
                                    if t[0] is Symbol.unquote:
                                        if depth == 1:
                                            return self.eval(t[1])
                                        else:
                                            return [t[0], qq(t[1], depth - 1)]
                                r = []
                                for x in t:
                                    if isinstance(x, list) and len(x) > 0 and isinstance(x[0], Symbol) and x[0] is Symbol.unquote_splicing:
                                        if depth == 1:
                                            r.extend(self.eval(x[1]))
                                        else:
                                            r.append([x[0], qq(x[1], depth - 1)])
                                    else:
                                        r.append(qq(x, depth))
                                return r
                            else:
                                return t
                        return qq(s[1])
                    if f is Symbol.quote:
                        return s[1]
                    if f is Symbol.set:
                        if not isinstance(s[1], Symbol):
                            raise SetNotSymbolError(s[1])
                        val = self.eval(s[2])
                        self.set(s[1].name, val)
                        return val
                    if f.name.startswith("."):
                        return getattr(self.eval(s[1]), f.name[1:])(*[self.eval(x) for x in s[2:]])
                fn = self.eval(f)
                if isinstance(fn, Macro):
                    assert False, "unexpected macro call: " + str(fn)
                    return self.eval(fn(*s[1:]), tail)
                elif tail:
                    raise TailCall(fn, [self.eval(x) for x in s[1:]])
                elif isinstance(fn, Function):
                    return fn.apply([self.eval(x) for x in s[1:]], tail=tail)
                elif hasattr(fn, "__call__"):
                    return fn(*[self.eval(x) for x in s[1:]])
                else:
                    raise NotCallableError(fn)
            elif isinstance(s, Symbol):
                if s.name[0].startswith(":"):
                    return s
                else:
                    found, r = self.lookup(s.name)
                    if not found:
                        # doctest seems to make __builtins__ a dict instead of a module
                        if isinstance(__builtins__, dict) and s.name in __builtins__:
                            r = __builtins__[s.name]
                        elif s.name in dir(__builtins__):
                            r = getattr(__builtins__, s.name)
                        else:
                            raise UndefinedSymbolError(s.name)
                    return r
            else:
                return s
        except TailCall as t:
            if tail:
                raise
            a = t
            while True:
                try:
                    return a.apply()
                except TailCall as t:
                    a = t
                    a.__traceback__ = None
        except Exception as x:
            print("*", external(s))
            raise

class Function(object):
    def __init__(self, name, params, body, scope):
        self.name = name
        self.params = []
        self.fixed = 0
        self.rest = None
        if isinstance(params, Symbol):
            self.rest = params
            params = []
        elif len(params) >= 2 and params[-2].name == ".":
            self.rest = params[-1]
            params = params[:-2]
        for p in params:
            if isinstance(p, list) and len(p) > 0 and isinstance(p[0], Symbol) and p[0].name == "o":
                self.params.append(p[1])
            else:
                self.params.append(p)
                self.fixed += 1
        self.body = body
        self.scope = scope
    def __str__(self):
        return "<Function %s>" % self.name
    def __call__(self, *args):
        return self.apply(args, tail=False)
    def apply(self, args, tail=True):
        scope = Scope(self.scope)
        if self.params is not None:
            if isinstance(self.params, list):
                assert len(args) >= self.fixed
                if self.rest is not None:
                    if len(args) > len(self.params):
                        scope.define(self.rest.name, list(args[len(self.params):]))
                    else:
                        scope.define(self.rest.name, [])
                else:
                    assert len(args) <= len(self.params)
                for p, a in zip(self.params, list(args) + [None] * (len(self.params) - len(args))):
                    scope.define(p.name, a)
            else:
                scope.define(self.params.name, list(args))
        r = None
        if self.body:
            for b in self.body[:-1]:
                scope.eval(b)
            r = scope.eval(self.body[-1], tail)
        return r

class Macro(Function):
    def __str__(self):
        return "<Macro %s>" % self.name

def eval(s):
    """
    >>> eval(read("1"))
    1
    >>> eval(read("(+ 1 2 3)"))
    6
    >>> eval(read("((lambda (x) (* x x)) 3)"))
    9
    >>> eval(read("(define (test fn x y) ((if fn * +) x y))"))
    <psil.interpreter.Function object at 0x...>
    >>> eval(read("(test True 2 3)"))
    6
    >>> eval(read("(test False 2 3)"))
    5
    """
    return Globals.eval(s)

def macroexpand(p, once = False):
    while isinstance(p, list) and len(p) > 0 and isinstance(p[0], Symbol):
        found, f = Globals.lookup(p[0].name)
        if found and isinstance(f, Macro):
            p = f(*p[1:])
        else:
            break
        if once:
            break
    return p

def macroexpand_r(p, depth=0, quoted=False):
    """
    >>> macroexpand_r(read("(foo bar)"))
    [<foo>, <bar>]
    >>> macroexpand_r(read("(and)"))
    True
    >>> macroexpand_r(read("(and a b)"))
    [<if>, <a>, [<if>, <b>, True, <False>], <False>]
    >>> macroexpand_r(read("(lambda (and) a)"))
    [<lambda>, [<and>], <a>]
    """
    if isinstance(p, list):
        if len(p) > 0 and isinstance(p[0], Symbol):
            if p[0] is Symbol.lambda_:
                return p[:2] + [x for x in [macroexpand_r(x, depth, quoted) for x in p[2:]] if x is not None]
            if p[0] is Symbol.quote:
                return [p[0], macroexpand_r(p[1], depth, True)]
            if p[0] is Symbol.quasiquote:
                return [p[0], macroexpand_r(p[1], depth+1, quoted)]
            if p[0] is Symbol.unquote or p[0] is Symbol.unquote_splicing:
                if depth <= 0:
                    raise "invalid unquote depth"
                return [p[0], macroexpand_r(p[1], depth-1, False)]
            if depth == 0 and not quoted:
                p = macroexpand(p)
                if not isinstance(p, list):
                    return p
        if not quoted:
            return [x for x in [macroexpand_r(x, depth, quoted) for x in p] if x is not None]
        else:
            return p
    else:
        return p

Globals = Scope()

Globals.symbols["macroexpand-1"] = lambda x: macroexpand(x, True)
Globals.symbols["macroexpand"] = macroexpand
Globals.symbols["macroexpand_r"] = macroexpand_r

Globals.symbols["+"]         = lambda *args: sum(args)
Globals.symbols["-"]         = lambda *args: -args[0] if len(args) == 1 else functools.reduce(operator.sub, args)
Globals.symbols["*"]         = lambda *args: functools.reduce(operator.mul, args, 1)
Globals.symbols["**"]        = operator.pow
Globals.symbols["/"]         = lambda *args: 1.0/args[0] if len(args) == 1 else functools.reduce(operator.truediv, args)
Globals.symbols["//"]        = lambda *args: functools.reduce(operator.floordiv, args)
Globals.symbols["%"]         = lambda x, y: x % tuple(y) if isinstance(y, list) else x % y
Globals.symbols["<<"]        = operator.lshift
Globals.symbols[">>"]        = operator.rshift
Globals.symbols["&"]         = lambda *args: functools.reduce(operator.and_, args, -1)
Globals.symbols["|"]         = lambda *args: functools.reduce(operator.or_, args, 0)
Globals.symbols["^"]         = operator.xor
Globals.symbols["~"]         = operator.invert
def _all(p, a):
    for i in range(len(a)-1):
        if not p(a[i], a[i+1]):
            return False
    return True
def _any(p, a):
    for i in range(len(a)-1):
        if p(a[i], a[i+1]):
            return True
    return False
Globals.symbols["<"]         = lambda *args: _all(operator.lt, args)
Globals.symbols[">"]         = lambda *args: _all(operator.gt, args)
Globals.symbols["<="]        = lambda *args: _all(operator.le, args)
Globals.symbols[">="]        = lambda *args: _all(operator.ge, args)
Globals.symbols["=="]        = lambda *args: _all(operator.eq, args)
Globals.symbols["!="]        = operator.ne
Globals.symbols["is"]        = lambda *args: _all(operator.is_, args)
Globals.symbols["is-not"]    = operator.is_not
Globals.symbols["in"]        = lambda x, y: x in y
Globals.symbols["not-in"]    = lambda x, y: x not in y
Globals.symbols["not"]       = operator.not_

def _del(x, y):
    del x[y]
Globals.symbols["del"]       = _del
# TODO: raise
Globals.symbols["include"] = lambda x: include(x)

Globals.symbols["list"]     = lambda *args: list(args)
Globals.symbols["make-list"]= lambda args: list(args)
Globals.symbols["list?"]    = lambda x: isinstance(x, list)
Globals.symbols["cons"]     = lambda x, y: [x] + y if isinstance(y, list) else [x]
def _set_car(x, y): x[0] = y
Globals.symbols["set-car!"] = _set_car
Globals.symbols["car"]    = lambda x: x[0]
Globals.symbols["cdr"]    = lambda x: x[1:]
Globals.symbols["caar"]   = lambda x: x[0][0]
Globals.symbols["cadr"]   = lambda x: x[1]
Globals.symbols["cdar"]   = lambda x: x[0][1:]
Globals.symbols["cddr"]   = lambda x: x[2:]
Globals.symbols["caaar"]  = lambda x: x[0][0][0]
Globals.symbols["caadr"]  = lambda x: x[1][0]
Globals.symbols["caddr"]  = lambda x: x[2]
Globals.symbols["cadddr"] = lambda x: x[3]
#Globals.symbols["cadar"]  = lambda x: x[0][1][0] # TODO
#Globals.symbols["caddr"]  = lambda x: x[0][0][0]
#Globals.symbols["cdaar"]  = lambda x: x[0][0][0]
#Globals.symbols["cdadr"]  = lambda x: x[0][0][0]
#Globals.symbols["cddar"]  = lambda x: x[0][0][0]
#Globals.symbols["cdddr"]  = lambda x: x[0][0][0]
Globals.symbols["caaaar"] = lambda x: x[0][0][0][0]
#...
Globals.symbols["null?"]  = lambda x: isinstance(x, list) and len(x) == 0
Globals.symbols["append"] = lambda *args: functools.reduce(operator.concat, map(list, args), [])
Globals.symbols["reverse"] = lambda x: list(reversed(x))
Globals.symbols["list-tail"] = lambda x, y: x[y:]
Globals.symbols["list-ref"] = lambda x, y: x[y]

Globals.symbols["symbol?"] = lambda x: isinstance(x, Symbol)
Globals.symbols["symbol->string"] = lambda x: x.name
Globals.symbols["string->symbol"] = lambda x: Symbol.new(x)

Globals.symbols["apply"] = lambda *args: args[0](*args[1])
Globals.symbols["concat"] = lambda *args: "".join(str(x) for x in args)
Globals.symbols["format"] = lambda x, *y: x % y
Globals.symbols["index"] = lambda x, y: x[y]
Globals.symbols["slice"] = lambda x, y, z: x[y:z]
def _set(x, y, z):
    x[y] = z
Globals.symbols["dict-set"] = _set

Globals.symbols["gensym"] = Symbol.gensym

#Globals.symbols["rt"] = __import__("psil", fromlist=["rt"], level=0)
Globals.symbols["_import"] = lambda x, g: __import__("psil", fromlist=["rt"], level=0).rt._import(x, g)

def call_with_current_continuation(f):
    import stackless
    channel = stackless.channel()
    stackless.tasklet(f)(channel.send)
    return channel.receive()
Globals.symbols["call-with-current-continuation"] = call_with_current_continuation

def external(x):
    """
    >>> print(external(123))
    123
    >>> print(external("abc"))
    "abc"
    >>> print(external([123, "abc"]))
    (123 "abc")
    >>> print(external(r'a\"b'))
    "a\\\"b"

    #>>> print([ord(x) for x in external(r'a\"b')])
    #[34, 97, 92, 92, 92, 34, 98, 34]
    """
    if isinstance(x, list):
        if len(x) > 0:
            if x[0] is Symbol.quote:
                return "'" + external(x[1])
            if x[0] is Symbol.quasiquote:
                return "`" + external(x[1])
            if x[0] is Symbol.unquote:
                return "," + external(x[1])
            if x[0] is Symbol.unquote_splicing:
                return ",@" + external(x[1])
        return "(" + " ".join(external(i) for i in x) + ")"
    if isinstance(x, Symbol):
        return x.name
    if isinstance(x, str):
        # todo: escape escapes
        return '"' + re.sub('"', r'\"', x) + '"'
    return str(x)

def psil(s, compiled = True, glob = None):
    tokens = tokenise(s)
    r = None
    compiled &= Compile
    g = dict(globals())
    for k, v in Globals.symbols.items():
        g[k] = v
    while True:
        p = parse(tokens)
        #print(external(p))
        if p is None:
            break
        p = macroexpand_r(p)
        if p is None:
            continue
        #print(external(p))
        if compiled and (not isinstance(p, list) or not isinstance(p[0], Symbol) or p[0] is not Symbol.defmacro):
            tree = psilc(p)

            tree = ast.Module([tree])
            ast.fix_missing_locations(tree)

            #print(ast.dump(tree))

            src = deparse.SourceGenerator()
            deparse.gen_source(tree, src)
            #print("source:", str(src))

            r = exec(compile(tree, "<psil>", "exec"), g)
        else:
            try:
                Globals.setglobals(glob)
                r = Globals.eval(p, tail=True)
            except TailCall as t:
                a = t
                while True:
                    try:
                        r = a.apply()
                        break
                    except TailCall as t:
                        a = t
                        a.__traceback__ = None
    return r

def rep(s):
    r = psil(s)
    if r is not None:
        print(external(r))

def include(fn):
    f = open(fn)
    text = f.read()
    f.close()
    m = re.match(r"#!.*?$", text, re.MULTILINE)
    if m is not None:
        text = text[m.end(0):]
    psil(text)

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stdmacros.psil")) as f:
    psil(f.read(), compiled=False)

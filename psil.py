"""PSIL: Python S-expresssion Intermediate Language

>>> eval(read("1"))
1
>>> eval(read("'(1 2 3)"))
[1, 2, 3]
>>> eval(read("(map (lambda (x) (* x x)) '(1 2 3))"))
[1, 4, 9]
>>> eval(read("(apply + '(1 2))"))
3

"""

import compiler
import operator
import os
import re
import sys

Compile = False

# adapted from http://code.activestate.com/recipes/475109/
PY_STRING_LITERAL_RE = (r'''
  """(?:                 # Triple-quoted can contain...
      [^"\\]             | # a non-quote non-backslash
      \\.                | # a backslashed character
      "{1,2}(?!")          # one or two quotes
    )*""" |
  "(?:                   # Non-triple quoted can contain...
     [^"\\]              | # a non-quote non-backslash
     \\.                   # a backslashed character
   )*"(?!")
''')

RE_NUMBER = re.compile(r"[-+]?\d+(\.\d+)?(e[-+]?\d+)?", re.IGNORECASE)
RE_SYMBOL = re.compile(r"[^ \t\n\)]+", re.IGNORECASE)
RE_STRING = re.compile(PY_STRING_LITERAL_RE, re.VERBOSE)

peval = eval

Symbols = {}

class SyntaxError(Exception):
    def __init__(self, s):
        Exception.__init__(self, s)

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
            return apply(self.fn, self.args)
    def __str__(self):
        return str(self.fn) + ":" + str(self.args)

class Token(object):
    LPAREN = object()
    RPAREN = object()
    QUOTE  = object()
    QQUOTE = object()
    COMMA  = object()
    SPLICE = object()
    SYMBOL = object()
    NUMBER = object()
    STRING = object()

def tokenise(s):
    """
    >>> [x[1] for x in tokenise("1")]
    [1]
    >>> [x[1] for x in tokenise("()")]
    ['(', ')']
    >>> [x[1] for x in tokenise("a")]
    ['a']
    >>> [x[1] for x in tokenise("'a")]
    ["'", 'a']
    >>> [x[1] for x in tokenise('''"test"''')]
    ['test']
    >>> [x[1] for x in tokenise('''(a 1 "test" 'c)''')]
    ['(', 'a', 1, 'test', "'", 'c', ')']
    >>> [x[1] for x in tokenise("123 34.5 56e7")]
    [123, 34.5, 560000000.0]
    >>> [x[1] for x in tokenise("(a ,@b c)")]
    ['(', 'a', ',@', 'b', 'c', ')']
    """
    i = 0
    while True:
        while i < len(s) and s[i].isspace():
            i += 1
        if i >= len(s):
            break
        if   s[i] == "(":
            yield (Token.LPAREN, s[i])
            i += 1
        elif s[i] == ")":
            yield (Token.RPAREN, s[i])
            i += 1
        elif s[i] == "'":
            yield (Token.QUOTE, s[i])
            i += 1
        elif s[i] == "`":
            yield (Token.QQUOTE, s[i])
            i += 1
        elif s[i] == ",":
            if s[i+1] == "@":
                yield (Token.SPLICE, s[i:i+2])
                i += 2
            else:
                yield (Token.COMMA, s[i])
                i += 1
        elif s[i] == '"':
            m = RE_STRING.match(s[i:])
            if m:
                yield (Token.STRING, peval(m.group(0)))
                i += m.end(0)
            else:
                raise SyntaxError(s[i:])
        elif s[i] == ";":
            i = s.index("\n", i+1)
        else:
            m = RE_NUMBER.match(s[i:])
            if m:
                if m.group(1) or m.group(2):
                    x = float(m.group(0))
                    yield (Token.NUMBER, x)
                else:
                    yield (Token.NUMBER, int(m.group(0)))
                i += m.end(0)
            else:
                m = RE_SYMBOL.match(s[i:])
                if m:
                    yield (Token.SYMBOL, m.group(0))
                    i += m.end(0)
                else:
                    raise SyntaxError(s[i:])

class Symbol(object):
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return "<%s>" % self.name
    names = {}
    gensym_counter = 0
    @staticmethod
    def new(name):
        if name in Symbol.names:
            return Symbol.names[name]
        s = Symbol(name)
        Symbol.names[name] = s
        return s
    @staticmethod
    def gensym():
        Symbol.gensym_counter += 1
        return Symbol.new("_g_%d" % Symbol.gensym_counter)

Symbol.quote            = Symbol.new("quote")
Symbol.quasiquote       = Symbol.new("quasiquote")
Symbol.unquote          = Symbol.new("unquote")
Symbol.unquote_splicing = Symbol.new("unquote-splicing")

Symbol.define           = Symbol.new("define")
Symbol.defmacro         = Symbol.new("defmacro")
Symbol.if_              = Symbol.new("if")
Symbol.lambda_          = Symbol.new("lambda")
Symbol.set              = Symbol.new("set!")

def parse(tokens, next = None):
    """
    >>> parse(tokenise("(a b c)"))
    [<a>, <b>, <c>]
    >>> parse(tokenise("'()"))
    [<quote>, []]
    >>> parse(tokenise("("))
    Traceback (most recent call last):
        ...
    SyntaxError: unclosed parenthesis
    >>> parse(tokenise("())"))
    """
    if next is None:
        try:
            next = tokens.next()
        except StopIteration:
            return None
    t, v = next
    if t == Token.LPAREN:
        a = []
        while True:
            try:
                next = tokens.next()
            except StopIteration:
                raise SyntaxError("unclosed parenthesis")
            if next[0] == Token.RPAREN:
                break
            a.append(parse(tokens, next))
        return a
    elif t == Token.STRING:
        return v
    elif t == Token.NUMBER:
        return v
    elif t == Token.QUOTE:
        return [Symbol.quote, parse(tokens)]
    elif t == Token.QQUOTE:
        return [Symbol.quasiquote, parse(tokens)]
    elif t == Token.COMMA:
        return [Symbol.unquote, parse(tokens)]
    elif t == Token.SPLICE:
        return [Symbol.unquote_splicing, parse(tokens)]
    elif t == Token.SYMBOL:
        return Symbol.new(v)
    else:
        raise SyntaxError(next)

def read(s):
    r"""
    >>> read("1")
    1
    >>> read("()")
    []
    >>> read("a")
    <a>
    >>> read('''"test"''')
    'test'
    >>> read(r'''"test\""''')
    'test"'
    >>> read(r'''"test\"s"''')
    'test"s'
    >>> read(r'''("test\"")''')
    ['test"']
    >>> read(r'''"test\n"''')
    'test\n'
    >>> read('''("test")''')
    ['test']
    >>> read('''(a 1 "test")''')
    [<a>, 1, 'test']
    >>> read("(a (b c) d)")
    [<a>, [<b>, <c>], <d>]
    >>> read("(+ 1 2)")
    [<+>, 1, 2]
    """
    return parse(tokenise(s))

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
            print >>sys.stderr, "*** warning: redefining", name
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
    def eval(self, s, tail = False):
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
                        return apply(getattr(self.eval(s[1]), f.name[1:]), [self.eval(x) for x in s[2:]])
                fn = self.eval(f)
                if isinstance(fn, Macro):
                    assert False, "unexpected macro call: " + str(fn)
                    return self.eval(apply(fn, s[1:]), tail)
                elif tail:
                    raise TailCall(fn, [self.eval(x) for x in s[1:]])
                elif isinstance(fn, Function):
                    return fn.apply([self.eval(x) for x in s[1:]], tail=True)
                elif callable(fn):
                    return apply(fn, [self.eval(x) for x in s[1:]])
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
        except TailCall, t:
            if tail:
                raise
            a = t
            while True:
                try:
                    return a.apply()
                except TailCall, t:
                    a = t
        except Exception, x:
            print "*", external(s)
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
    <__main__.Function object at 0x...>
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
            p = apply(f, p[1:])
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
                return p[:2] + [macroexpand_r(x, depth, quoted) for x in p[2:]]
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
Globals.symbols["-"]         = lambda *args: -args[0] if len(args) == 1 else reduce(operator.sub, args)
Globals.symbols["*"]         = lambda *args: reduce(operator.mul, args, 1)
Globals.symbols["**"]        = operator.pow
Globals.symbols["/"]         = lambda *args: 1.0/args[0] if len(args) == 1 else reduce(operator.div, args)
Globals.symbols["//"]        = lambda *args: reduce(operator.floordiv, args)
Globals.symbols["%"]         = lambda x, y: x % tuple(y) if isinstance(y, list) else x % y
Globals.symbols["<<"]        = operator.lshift
Globals.symbols[">>"]        = operator.rshift
Globals.symbols["&"]         = lambda *args: reduce(operator.and_, args, -1)
Globals.symbols["|"]         = lambda *args: reduce(operator.or_, args, 0)
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
def _print(*a):
    print "".join(str(x) for x in a)
Globals.symbols["print"]     = _print
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
Globals.symbols["append"] = lambda *args: reduce(operator.add, args)
Globals.symbols["reverse"] = lambda x: list(reversed(x))
Globals.symbols["list-tail"] = lambda x, y: x[y:]
Globals.symbols["list-ref"] = lambda x, y: x[y]

Globals.symbols["symbol?"] = lambda x: isinstance(x, Symbol)
Globals.symbols["symbol->string"] = lambda x: x.name
Globals.symbols["string->symbol"] = lambda x: Symbol.new(x)

Globals.symbols["concat"] = lambda *args: "".join(str(x) for x in args)
Globals.symbols["format"] = lambda x, *y: x % y
Globals.symbols["index"] = lambda x, y: x[y]
Globals.symbols["slice"] = lambda x, y, z: x[y:z]
def _set(x, y, z):
    x[y] = z
Globals.symbols["dict-set"] = _set

Globals.symbols["gensym"] = Symbol.gensym

def call_with_current_continuation(f):
    import stackless
    channel = stackless.channel()
    stackless.tasklet(f)(channel.send)
    return channel.receive()
Globals.symbols["call-with-current-continuation"] = call_with_current_continuation

Macros = """
(defmacro begin forms
    `((lambda ()
        ,@forms)))
(defmacro when whenargs
    `(if ,(car whenargs)
        (begin ,@(cdr whenargs))))
(defmacro let letargs
    `((lambda (,@(map car (car letargs)))
        ,@(cdr letargs)) ,@(map cadr (car letargs))))
(defmacro let* letargs ; this is probably broken
    (if (car letargs)
        `((lambda (,(caaar letargs))
            (let* ,(cdar letargs) ,@(cdr letargs))) ,(cadr (caar letargs)))
        `(begin ,@(cdr letargs))))
(defmacro and andargs
    (if andargs
        `(if ,(car andargs)
             (and ,@(cdr andargs))
             False)
        True))
(defmacro or orargs
    (if orargs
        `(if ,(car orargs)
             ,(car orargs)
             (or ,@(cdr orargs)))
        False))
(defmacro cond condargs
    (if condargs
        (if (is (caar condargs) 'else)
            `(begin ,@(cdar condargs))
            `(if ,(caar condargs)
                ,@(cdar condargs)
                (cond ,@(cdr condargs))))))
(defmacro for-each args
    `(map ,@args))
(defmacro import args
    `(define ,(car args)
      (__import__ ,(symbol->string (car args)))))
(defmacro comment args)
"""

class SourceGenerator(object):
    def __init__(self):
        self.source = ""
        self.depth = 0
    def line(self, s):
        self.source += "    "*self.depth + s + "\n"
    def indent(self):
        self.depth += 1
    def dedent(self):
        self.depth -= 1
    def __str__(self):
        return self.source

def pydent(s):
    if s == "try": s = "try_"
    s = s.replace("-", "_")
    s = s.replace("?", "_")
    s = s.replace(">", "_")
    return s

def compile_add(p):
    if len(p) == 2:
        return build_ast(p[1])
    elif len(p) == 3:
        return compiler.ast.Add((build_ast(p[1]), build_ast(p[2])))
    else:
        return compiler.ast.Add((compile_add(p[:-1]), build_ast(p[-1])))

def compile_define(p):
    if isinstance(p[1], list):
        stmt = [build_ast(x) for x in p[2:]]
        if not is_statement(stmt[-1]):
            stmt[-1] = compiler.ast.Return(stmt[-1])
        return compiler.ast.Function(None, pydent(p[1][0].name), [x.name for x in p[1][1:]], [], 0, None, compiler.ast.Stmt(stmt))
    else:
        return compiler.ast.Assign([compiler.ast.AssName(pydent(p[1].name), None)], build_ast(p[2]))

def compile_divide(p):
    if len(p) == 2:
        return compiler.ast.Div((compiler.ast.Const(1), build_ast(p[1])))
    elif len(p) == 3:
        return compiler.ast.Div((build_ast(p[1]), build_ast(p[2])))
    else:
        return compiler.ast.Div((compile_divide(p[:-1]), build_ast(p[-1])))

def compile_equals(p):
    if len(p) == 3:
        return compiler.ast.Compare(build_ast(p[1]), [(p[0].name, build_ast(p[2]))])
    else:
        return compiler.ast.CallFunc(compiler.ast.Name("=="), [build_ast(x) for x in p[1:]])

def compile_lambda(p):
    if len(p) > 3:
        return compiler.ast.Lambda([pydent(x.name) for x in p[1]], [], 0, [build_ast(x) for x in p[2:]])
    else:
        return compiler.ast.Lambda([pydent(x.name) for x in p[1]], [], 0, build_ast(p[2]))

def compile_multiply(p):
    if len(p) == 2:
        return build_ast(p[1])
    elif len(p) == 3:
        return compiler.ast.Mul((build_ast(p[1]), build_ast(p[2])))
    else:
        return compiler.ast.Mul((compile_multiply(p[:-1]), build_ast(p[-1])))

def compile_quote(p):
    def q(p):
        if isinstance(p, list):
            return compiler.ast.List([q(x) for x in p])
        elif isinstance(p, Symbol):
            return compiler.ast.CallFunc(compiler.ast.Name("sym"), [compiler.ast.Const(p.name)])
        else:
            return compiler.ast.Const(p)
    return q(p[1])

def compile_subtract(p):
    if len(p) == 2:
        return compiler.ast.UnarySub(build_ast(p[1]))
    elif len(p) == 3:
        return compiler.ast.Sub((build_ast(p[1]), build_ast(p[2])))
    else:
        return compiler.ast.Sub((compile_subtract(p[:-1]), build_ast(p[-1])))

CompileFuncs = {
    Symbol.new("+"): compile_add,
    Symbol.new("-"): compile_subtract,
    Symbol.new("*"): compile_multiply,
    Symbol.new("/"): compile_divide,
    Symbol.new("%"): lambda p: compiler.ast.Mod((build_ast(p[1]), build_ast(p[2]))),
    Symbol.new("&"): lambda p: compiler.ast.Bitand([build_ast(p[1]), build_ast(p[2])]),
    Symbol.new("**"): lambda p: compiler.ast.Power((build_ast(p[1]), build_ast(p[2]))),
    Symbol.new(">>"): lambda p: compiler.ast.RightShift((build_ast(p[1]), build_ast(p[2]))),
    Symbol.new("<<"): lambda p: compiler.ast.LeftShift((build_ast(p[1]), build_ast(p[2]))),
    Symbol.new("^"): lambda p: compiler.ast.Bitxor([build_ast(p[1]), build_ast(p[2])]),
    Symbol.new("<"): lambda p: compiler.ast.Compare(build_ast(p[1]), [(p[0].name, build_ast(p[2]))]),
    Symbol.new(">"): lambda p: compiler.ast.Compare(build_ast(p[1]), [(p[0].name, build_ast(p[2]))]),
    Symbol.new("<="): lambda p: compiler.ast.Compare(build_ast(p[1]), [(p[0].name, build_ast(p[2]))]),
    Symbol.new(">="): lambda p: compiler.ast.Compare(build_ast(p[1]), [(p[0].name, build_ast(p[2]))]),
    Symbol.new("=="): compile_equals,
    Symbol.new("!="): lambda p: compiler.ast.Compare(build_ast(p[1]), [(p[0].name, build_ast(p[2]))]),
    Symbol.new("is"): lambda p: compiler.ast.Compare(build_ast(p[1]), [(p[0].name, build_ast(p[2]))]),
    Symbol.new("is-not"): lambda p: compiler.ast.Compare(build_ast(p[1]), [("is not", build_ast(p[2]))]),
    Symbol.new("define"): compile_define,
    Symbol.new("dict-set"): lambda p: compiler.ast.Assign([compiler.ast.Subscript(build_ast(p[1]), 0, build_ast(p[2]))], build_ast(p[3])),
    Symbol.new("caadr"): lambda p: compiler.ast.Subscript(compiler.ast.Subscript(build_ast(p[1]), 0, compiler.ast.Const(1)), 0, compiler.ast.Const(0)),
    Symbol.new("caar"): lambda p: compiler.ast.Subscript(compiler.ast.Subscript(build_ast(p[1]), 0, compiler.ast.Const(0)), 0, compiler.ast.Const(0)),
    Symbol.new("cadddr"): lambda p: compiler.ast.Subscript(build_ast(p[1]), 0, compiler.ast.Const(3)),
    Symbol.new("caddr"): lambda p: compiler.ast.Subscript(build_ast(p[1]), 0, compiler.ast.Const(2)),
    Symbol.new("cadr"): lambda p: compiler.ast.Subscript(build_ast(p[1]), 0, compiler.ast.Const(1)),
    Symbol.new("car"): lambda p: compiler.ast.Subscript(build_ast(p[1]), 0, compiler.ast.Const(0)),
    Symbol.new("cdar"): lambda p: compiler.ast.Slice(compiler.ast.Subscript(build_ast(p[1]), 0, compiler.ast.Const(0)), 0, compiler.ast.Const(1), None),
    Symbol.new("cddr"): lambda p: compiler.ast.Slice(build_ast(p[1]), 0, compiler.ast.Const(2), None),
    Symbol.new("cdr"): lambda p: compiler.ast.Slice(build_ast(p[1]), 0, compiler.ast.Const(1), None),
    Symbol.new("cons"): lambda p: compiler.ast.Add((compiler.ast.List([build_ast(p[1])]), build_ast(p[2]))),
    Symbol.new("if"): lambda p: compiler.ast.If([(build_ast(p[1]), build_ast(p[2]))], build_ast(p[3]) if len(p) >= 4 else None),
    Symbol.new("in"): lambda p: compiler.ast.Compare(build_ast(p[1]), [("in", build_ast(p[2]))]),
    Symbol.new("index"): lambda p: compiler.ast.Subscript(build_ast(p[1]), 0, build_ast(p[2])),
    Symbol.new("lambda"): compile_lambda,
    Symbol.new("list"): lambda p: compiler.ast.List([build_ast(x) for x in p[1:]]),
    Symbol.new("not"): lambda p: compiler.ast.Not(build_ast(p[1])),
    Symbol.new("not-in"): lambda p: compiler.ast.Compare(build_ast(p[1]), [("not in", build_ast(p[2]))]),
    Symbol.new("print"): lambda p: compiler.ast.CallFunc(compiler.ast.Name("__print__"), [build_ast(p[1])]),
    Symbol.new("quote"): compile_quote,
    Symbol.new("set!"): lambda p: compiler.ast.Assign([compiler.ast.AssName(p[1].name, None)], build_ast(p[2])),
    Symbol.new("slice"): lambda p: compiler.ast.Slice(build_ast(p[1]), 0, build_ast(p[2]), build_ast(p[3])),
    Symbol.new("string->symbol"): lambda p: compiler.ast.CallFunc(compiler.ast.Name("intern"), [build_ast(p[1])]),
}

def build_ast(p, tail = False):
    """
    >>> build_ast(parse(tokenise("(+ 2 3)")))
    Add((Const(2), Const(3)))
    """
    if isinstance(p, list):
        if isinstance(p[0], Symbol):
            f = CompileFuncs.get(p[0])
            if f:
                return f(p)
            elif p[0].name.startswith("."):
                return compiler.ast.CallFunc(compiler.ast.Getattr(build_ast(p[1]), p[0].name[1:]), [build_ast(x) for x in p[2:]])
            else:
                return compiler.ast.CallFunc(compiler.ast.Name(pydent(p[0].name)), [build_ast(x) for x in p[1:]])
        else:
            return compiler.ast.CallFunc(build_ast(p[0]), [build_ast(x) for x in p[1:]])
    elif isinstance(p, Symbol):
        return compiler.ast.Name(pydent(p.name))
    else:
        return compiler.ast.Const(p)

InlineFuncs = {
    "+": "(lambda *x: sum(x))",
    "*": "(lambda *x: reduce(operator.mul, x, 1))",
    "==": "(lambda *x: all(map(lambda i: x[i] == x[i+1], range(len(x)-1))))",
    "and": "(lambda *x: reduce(operator.and_, x))",
    "append": "(lambda *x: reduce(operator.add, x))",
    "cadr": "(lambda x: x[1])",
    "car": "(lambda x: x[0])",
    "concat": "(lambda *x: ''.join([str(y) for y in x]))",
    "make_list": "list",
    "not": "(lambda x: not x)",
    "reverse": "(lambda x: list(reversed(x)))",
}

def expr(node):
    #print "node:", node
    if isinstance(node, compiler.ast.Add):
        return "(%s + %s)" % (expr(node.left), expr(node.right))
    elif isinstance(node, compiler.ast.AssName):
        return node.name
    elif isinstance(node, compiler.ast.Bitand):
        return "(" + " & ".join([expr(x) for x in node.nodes]) + ")"
    elif isinstance(node, compiler.ast.Bitxor):
        return "(" + " ^ ".join([expr(x) for x in node.nodes]) + ")"
    elif isinstance(node, compiler.ast.CallFunc):
        if isinstance(node.node, compiler.ast.Lambda):
            return "(" + expr(node.node) + ")(" + ", ".join([expr(x) for x in node.args]) + ")"
        else:
            return expr(node.node) + "(" + ", ".join([expr(x) for x in node.args]) + ")"
    elif isinstance(node, compiler.ast.Compare):
        return "(" + expr(node.expr) + "".join([" " + x[0] + " " + expr(x[1]) + ")" for x in node.ops])
    elif isinstance(node, compiler.ast.Const):
        return repr(node.value)
    elif isinstance(node, compiler.ast.Div):
        return "(%s / %s)" % (expr(node.left), expr(node.right))
    elif isinstance(node, compiler.ast.Getattr):
        return expr(node.expr) + "." + node.attrname
    elif isinstance(node, compiler.ast.If):
        return "(" + expr(node.tests[0][1]) + " if " + expr(node.tests[0][0]) + " else " + (expr(node.else_) if node.else_ else "None") + ")"
    elif isinstance(node, compiler.ast.Lambda):
        if hasattr(node, "name"):
            return node.name
        else:
            return "lambda " + ", ".join(node.argnames) + ": " + expr(node.code)
    elif isinstance(node, compiler.ast.LeftShift):
        return "(%s << %s)" % (expr(node.left), expr(node.right))
    elif isinstance(node, compiler.ast.List):
        return "[" + ", ".join([expr(x) for x in node.nodes]) + "]"
    elif isinstance(node, compiler.ast.Mod):
        return "(%s %% %s)" % (expr(node.left), expr(node.right))
    elif isinstance(node, compiler.ast.Mul):
        return "(%s * %s)" % (expr(node.left), expr(node.right))
    elif isinstance(node, compiler.ast.Name):
        f = InlineFuncs.get(node.name)
        if f:
            return f
        else:
            return node.name
    elif isinstance(node, compiler.ast.Not):
        return "not %s" % expr(node.expr)
    elif isinstance(node, compiler.ast.Power):
        return "(%s ** %s)" % (expr(node.left), expr(node.right))
    elif isinstance(node, compiler.ast.RightShift):
        return "(%s >> %s)" % (expr(node.left), expr(node.right))
    elif isinstance(node, compiler.ast.Slice):
        return expr(node.expr) + "[" + (expr(node.lower) if node.lower else "") + ":" + (expr(node.upper) if node.upper else "") + "]"
    elif isinstance(node, compiler.ast.Sub):
        return "(%s - %s)" % (expr(node.left), expr(node.right))
    elif isinstance(node, compiler.ast.Subscript):
        return "%s[%s]" % (expr(node.expr), expr(node.subs))
    elif isinstance(node, compiler.ast.UnarySub):
        return "-(%s)" % expr(node.expr)
    else:
        print >>sys.stderr, "expr:", node
        sys.exit(1)

def is_statement(p):
    return isinstance(p, compiler.ast.Assign)

LambdaCounter = 0

def gen_source(node, source):
    class LiftLambda(object):
        def visitLambda(self, p):
            global LambdaCounter
            if isinstance(p.code, list):
                LambdaCounter += 1
                p.name = "_lambda_" + str(LambdaCounter)
                gen_source(compiler.ast.Function(None, p.name, p.argnames, p.defaults, p.flags, None, compiler.ast.Stmt(p.code[:-1] + [p.code[-1] if is_statement(p.code[-1]) else compiler.ast.Return(p.code[-1])])), source)
            elif is_statement(p.code):
                LambdaCounter += 1
                p.name = "_lambda_" + str(LambdaCounter)
                gen_source(compiler.ast.Function(None, p.name, p.argnames, p.defaults, p.flags, None, compiler.ast.Stmt([p.code])), source)
            else:
                compiler.walk(p.code, self)
        def visitStmt(self, p):
            pass
    compiler.walk(node, LiftLambda())
    if isinstance(node, compiler.ast.Assign):
        source.line("".join([expr(x)+" = " for x in node.nodes]) + expr(node.expr))
    elif isinstance(node, compiler.ast.Function):
        source.line("def " + node.name + "(" + ", ".join(node.argnames) + "):")
        source.indent()
        gen_source(node.code, source)
        source.dedent()
    elif isinstance(node, compiler.ast.If):
        source.line("if " + expr(node.tests[0][0]) + ":")
        source.indent()
        gen_source(node.tests[0][1], source)
        source.dedent()
        if node.else_:
            source.line("else:")
            source.indent()
            gen_source(node.else_, source)
            source.dedent()
    elif isinstance(node, compiler.ast.Print):
        #print "nodes:", node.nodes
        #self.source.line("print " + ",".join([expr(x) for x in node.nodes]))
        source.line("print " + expr(node.nodes))
    elif isinstance(node, compiler.ast.Return):
        source.line("return " + expr(node.value))
    elif isinstance(node, compiler.ast.Stmt):
        for x in node.nodes:
            gen_source(x, source)
    else:
        source.line(expr(node))

def psilc(p):
    ast = build_ast(p)
    #print "ast:", ast
    source = SourceGenerator()
    gen_source(ast, source)
    #print "source:\n", str(source)
    return str(source)

def external(x):
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
        return '"' + re.sub('"', r'\"', x) + '"'
    return str(x)

def psil(s, compiled = True, glob = None):
    t = tokenise(s)
    r = None
    compiled &= Compile
    source = """import operator
def __print__(a): print a
"""
    while True:
        p = parse(t)
        if p is None:
            break
        p = macroexpand_r(p)
        if p is None:
            continue
        if compiled and (not isinstance(p, list) or not isinstance(p[0], Symbol) or p[0] is not Symbol.defmacro):
            source += psilc(p)
        else:
            try:
                Globals.setglobals(glob)
                r = Globals.eval(p)
            except TailCall, x:
                r = x.apply()
    if compiled:
        exec compiler.compile(source, "psil", "exec") in globals()
    return r

def rep(s):
    r = psil(s)
    if r is not None:
        print external(r)

def include(fn):
    f = open(fn)
    text = f.read()
    f.close()
    m = re.match(r"#!.*?$", text, re.MULTILINE)
    if m is not None:
        text = text[m.end(0):]
    psil(text)

psil(Macros, compiled = False)

if __name__ == "__main__":
    Interactive = True
    a = 1
    while a < len(sys.argv) and sys.argv[a].startswith("-"):
        if sys.argv[a] == "-c":
            Compile = True
        elif sys.argv[a] == "-e":
            a += 1
            psil(sys.argv[a])
            Interactive = False
        elif sys.argv[a] == "--test":
            import doctest
            a += 1
            if a < len(sys.argv):
                doctest.testfile(sys.argv[a])
            else:
                doctest.testmod(optionflags=doctest.ELLIPSIS)
                doctest.testfile("psil.test", optionflags=doctest.ELLIPSIS)
                doctest.testfile("integ.test", optionflags=doctest.ELLIPSIS)
            sys.exit(0)
        a += 1
    if a < len(sys.argv):
        # TODO: command line args to script
        include(sys.argv[a])
    elif Interactive:
        Globals.symbols["quit"] = lambda: sys.exit(0)
        try:
            import readline
        except ImportError:
            pass
        import traceback
        print "PSIL interactive mode"
        print "Use (quit) to exit"
        while True:
            try:
                s = raw_input("> ")
            except EOFError:
                print
                break
            try:
                rep(s)
            except SystemExit:
                raise
            except:
                traceback.print_exc()

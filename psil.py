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

import math
import re

RE_NUMBER = re.compile(r"[-+]?\d+(\.\d+)?(e[-+]?\d+)?", re.IGNORECASE)
RE_SYMBOL = re.compile(r"[^ \t\n\)]+", re.IGNORECASE)

peval = eval

Symbols = {}

class SyntaxError(Exception):
    def __init__(self, s):
        Exception.__init__(self, s)

class UndefinedSymbolError(Exception):
    def __init__(self, s):
        Exception.__init__(self, s)

class SetNotSymbolError(Exception):
    pass

class Token(object):
    LPAREN = object()
    RPAREN = object()
    QUOTE  = object()
    QQUOTE = object()
    COMMA  = object()
    SYMBOL = object()
    BOOLEAN = object()
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
    """
    i = 0
    while True:
        while i < len(s) and s[i] in " \t\n":
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
            yield (Token.COMMA, s[i])
            i += 1
        elif s[i] == '"':
            j = s.index('"', i+1)
            yield (Token.STRING, peval(s[i:j+1]))
            i = j + 1
        elif s[i] == ";":
            i = s.index("\n", i+1)
        elif s[i] == "#":
            yield (Token.BOOLEAN, s[i+1])
            i += 2
        else:
            m = RE_NUMBER.match(s[i:])
            if m:
                if m.group(1) or m.group(2):
                    x = float(m.group(0))
                    if x == math.floor(x):
                        x = int(x)
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
    @staticmethod
    def new(name):
        if name in Symbol.names:
            return Symbol.names[name]
        s = Symbol(name)
        Symbol.names[name] = s
        return s

def parse(tokens, next = None):
    if next is None:
        try:
            next = tokens.next()
        except StopIteration:
            return None
    t, v = next
    if t == Token.LPAREN:
        a = []
        while True:
            next = tokens.next()
            if next[0] == Token.RPAREN:
                break
            a.append(parse(tokens, next))
        if len(a) == 0:
            return None
        return a
    elif t == Token.STRING:
        return v
    elif t == Token.BOOLEAN:
        return Special.T if v == "t" else Special.F
    elif t == Token.NUMBER:
        return v
    elif t == Token.QUOTE:
        return [Symbol.new("quote"), parse(tokens)]
    elif t == Token.QQUOTE:
        return [Symbol.new("quasiquote"), parse(tokens)]
    elif t == Token.COMMA:
        return [Symbol.new("unquote"), parse(tokens)]
    elif t == Token.SYMBOL:
        return Symbol.new(v)
    else:
        raise SyntaxError(next)

def read(s):
    """
    >>> read("1")
    1
    >>> read("()")
    >>> read("a")
    <a>
    >>> read('''"test"''')
    'test'
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
    def __init__(self, parent = None):
        self.parent = parent
        self.symbols = {}
    def define(self, name, value):
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
            if name in s.symbols:
                return s.symbols[name]
            s = s.parent
        return None
    def eval(self, s):
        if isinstance(s, list) and len(s) > 0:
            if isinstance(s[0], Symbol):
                if s[0].name == "define":
                    if isinstance(s[1], Symbol):
                        return self.define(s[1].name, self.eval(s[2]))
                    else:
                        return self.define(s[1][0].name, Function(s[1][1:], s[2:], self))
                if s[0].name == "defmacro":
                    return self.define(s[1].name, Macro(s[2], s[3], self))
                if s[0].name == "if":
                    if self.eval(s[1]) != Special.F:
                        return self.eval(s[2])
                    else:
                        return self.eval(s[3])
                if s[0].name == "lambda":
                    return Function(s[1], s[2:], self)
                if s[0].name == "quasiquote":
                    def qq(t, depth=1):
                        if isinstance(t, list):
                            if len(t) > 0 and isinstance(t[0], Symbol):
                                if t[0].name == "quasiquote":
                                    return [t[0], qq(t[1], depth + 1)]
                                if t[0].name == "unquote":
                                    if depth == 1:
                                        return self.eval(t[1])
                                    else:
                                        return [t[0], qq(t[1], depth - 1)]
                            return [qq(x, depth) for x in t]
                        else:
                            return t
                    return qq(s[1])
                if s[0].name == "quote":
                    return s[1]
                if s[0].name == "set!":
                    if not isinstance(s[1], Symbol):
                        raise SetNotSymbolError(s[1])
                    val = self.eval(s[2])
                    self.set(s[1].name, val)
                    return val
                if s[0].name.startswith("."):
                    return getattr(self.eval(s[1]), s[0].name[1:])
                m = self.eval(s[0])
                if isinstance(m, Macro):
                    return self.eval(m.expand(*s[1:]))
            f = self.eval(s[0])
            args = [self.eval(x) for x in s[1:]]
            return f(*args)
        elif isinstance(s, Symbol):
            r = self.lookup(s.name)
            if r is None:
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

class Macro(object):
    def __init__(self, params, body, scope):
        self.params = params
        self.body = body
        self.scope = scope
    def expand(self, *args):
        scope = Scope(self.scope)
        for p, a in zip(self.params, args):
            scope.define(p.name, a)
        return scope.eval(self.body)

class Function(object):
    def __init__(self, params, body, scope):
        self.params = params
        self.body = body
        self.scope = scope
    def __call__(self, *args):
        scope = Scope(self.scope)
        if self.params is not None:
            if isinstance(self.params, list):
                for p, a in zip(self.params, args):
                    scope.define(p.name, a)
            else:
                scope.define(self.params.name, list(args))
        r = None
        for b in self.body:
            r = scope.eval(b)
        return r

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
    >>> eval(read("(test #t 2 3)"))
    6
    >>> eval(read("(test #f 2 3)"))
    5
    """
    return Globals.eval(s)

class Special(object):
    def __init__(self, v):
        self.val = v
    def __repr__(self):
        return self.val

Special.T = Special("#t")
Special.F = Special("#f")

Globals = Scope()

Globals.symbols["first"]  = lambda x: x[0]
Globals.symbols["rest"]   = lambda x: x[1:]
Globals.symbols["eqv?"]   = lambda x, y: Special.T if x is y else Special.F
Globals.symbols["eq?"]    = lambda x, y: Special.T if x is y else Special.F
Globals.symbols["equal?"] = lambda x, y: Special.T if x == y else Special.F
Globals.symbols["apply"]  = lambda x, args: x(*args)

Globals.symbols["number?"]   = lambda x: Special.T
Globals.symbols["complex?"]  = lambda x: Special.T if isinstance(x, complex) or isinstance(x, float) or isinstance(x, int) else Special.F
Globals.symbols["real?"]     = lambda x: Special.T if isinstance(x, float) or isinstance(x, int) else Special.F
Globals.symbols["rational?"] = lambda x: Special.F # todo
Globals.symbols["integer?"]  = lambda x: Special.T if isinstance(x, int) else Special.F
Globals.symbols["exact?"]    = lambda x: Special.T if isinstance(x, int) else Special.F
Globals.symbols["inexact?"]  = lambda x: Special.T if not isinstance(x, int) else Special.F
Globals.symbols["="]         = lambda *args: Special.T if reduce(lambda x, y: x and y, [args[i] == args[i+1] for i in range(len(args)-1)], True) else Special.F
Globals.symbols["<"]         = lambda *args: Special.T if reduce(lambda x, y: x and y, [args[i] < args[i+1] for i in range(len(args)-1)], True) else Special.F
Globals.symbols[">"]         = lambda *args: Special.T if reduce(lambda x, y: x and y, [args[i] > args[i+1] for i in range(len(args)-1)], True) else Special.F
Globals.symbols["<="]        = lambda *args: Special.T if reduce(lambda x, y: x and y, [args[i] <= args[i+1] for i in range(len(args)-1)], True) else Special.F
Globals.symbols[">="]        = lambda *args: Special.T if reduce(lambda x, y: x and y, [args[i] >= args[i+1] for i in range(len(args)-1)], True) else Special.F
Globals.symbols["zero?"]     = lambda x: Special.T if x == 0 else Special.F
Globals.symbols["positive?"] = lambda x: Special.T if x > 0 else Special.F
Globals.symbols["negative?"] = lambda x: Special.T if x < 0 else Special.F
Globals.symbols["odd?"]      = lambda x: Special.T if x & 1 else Special.F
Globals.symbols["even?"]     = lambda x: Special.T if not (x & 1) else Special.F
Globals.symbols["max"]       = lambda *args: max(args)
Globals.symbols["min"]       = lambda *args: min(args)
Globals.symbols["+"]         = lambda *args: sum(args)
Globals.symbols["*"]         = lambda *args: reduce(lambda x, y: x * y, args, 1)
Globals.symbols["-"]         = lambda *args: -args[0] if len(args) == 1 else reduce(lambda x, y: x - y, args)
Globals.symbols["/"]         = lambda *args: 1.0/args[0] if len(args) == 1 else reduce(lambda x, y: 1.0*x / y, args)
Globals.symbols["abs"]       = lambda x: abs(x)
Globals.symbols["quotient"]  = lambda x, y: x // y
Globals.symbols["modulo"]    = lambda x, y: x % y
Globals.symbols["remainder"] = lambda x, y: x % y
Globals.symbols["gcd"]       = lambda x, y: x if y == 0 else Globals.symbols["gcd"](y, x % abs(y))
Globals.symbols["lcm"]       = lambda x, y: x * y # TODO
Globals.symbols["numerator"] = lambda x: x # TODO
Globals.symbols["denominator"] = lambda x: x # TODO
Globals.symbols["floor"]     = lambda x: int(math.floor(x)) if not isinstance(x, int) else x
Globals.symbols["ceiling"]   = lambda x: int(math.ceil(x)) if not isinstance(x, int) else x
Globals.symbols["truncate"]  = lambda x: int(math.ceil(x)) if x < 0 else int(math.floor(x))
Globals.symbols["round"]     = lambda x: int(math.floor(x + 0.5)) if not isinstance(x, int) else x
Globals.symbols["exp"]       = math.exp
Globals.symbols["log"]       = math.log
Globals.symbols["sin"]       = math.sin
Globals.symbols["cos"]       = math.cos
Globals.symbols["tan"]       = math.tan
Globals.symbols["asin"]      = math.asin
Globals.symbols["acos"]      = math.acos
Globals.symbols["atan"]      = lambda *args: math.atan(args[0]) if len(args) == 1 else math.atan2(args[0], args[1])
Globals.symbols["sqrt"]      = math.sqrt
Globals.symbols["expt"]      = math.pow
Globals.symbols["make-rectangular"] = lambda x, y: 0 # TODO
Globals.symbols["make-polar"] = lambda x, y: 0 # TODO
Globals.symbols["real-part"]  = lambda z: 0 # TODO
Globals.symbols["imag-part"]  = lambda z: 0 # TODO
Globals.symbols["magnitude"]  = lambda z: 0 # TODO
Globals.symbols["angle"]      = lambda z: 0 # TODO
Globals.symbols["exact->inexact"] = lambda x: x # TODO
Globals.symbols["inexact->exact"] = lambda x: x # TODO
Globals.symbols["number->string"] = lambda x, b = 10: str(x) if b == 10 else hex(x)[2:] # TODO
Globals.symbols["string->number"] = lambda x, b = 10: int(x, b) # TODO

Globals.symbols["not"]      = lambda x: Special.T if x is Special.F else Special.F
Globals.symbols["boolean?"] = lambda x: Special.T if x is Special.F or x is Special.T else Special.F

Globals.symbols["list"]     = lambda *args: list(args)
Globals.symbols["list?"]    = lambda x: Special.T if isinstance(x, list) or x is None else Special.F
Globals.symbols["set-cdr!"] = lambda x: None # TODO
Globals.symbols["pair?"]    = lambda x: Special.F # TODO
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
#Globals.symbols["cadar"]  = lambda x: x[0][1][0] # TODO
#Globals.symbols["caddr"]  = lambda x: x[0][0][0]
#Globals.symbols["cdaar"]  = lambda x: x[0][0][0]
#Globals.symbols["cdadr"]  = lambda x: x[0][0][0]
#Globals.symbols["cddar"]  = lambda x: x[0][0][0]
#Globals.symbols["cdddr"]  = lambda x: x[0][0][0]
Globals.symbols["caaaar"] = lambda x: x[0][0][0][0]
#...
Globals.symbols["null?"]  = lambda x: Special.T if x is None else Special.F
Globals.symbols["length"] = lambda x: len(x) if x is not None else 0
Globals.symbols["append"] = lambda *args: reduce(lambda x, y: x + y, args)
Globals.symbols["reverse"] = lambda x: list(reversed(x))
Globals.symbols["list-tail"] = lambda x, y: x[y:]
Globals.symbols["list-ref"] = lambda x, y: x[y]
def _mem(obj, lst, p):
    for i, e in enumerate(lst):
        if p(e, obj) is not Special.F:
            return lst[i:]
    return Special.F
Globals.symbols["memq"]   = lambda x, y: _mem(x, y, Globals.symbols["eq?"])
Globals.symbols["memv"]   = lambda x, y: _mem(x, y, Globals.symbols["eqv?"])
Globals.symbols["member"] = lambda x, y: _mem(x, y, Globals.symbols["equal?"])
def _ass(obj, lst, p):
    for x in lst:
        if p(x[0], obj) is not Special.F:
            return x
    return Special.F
Globals.symbols["assq"]   = lambda x, y: _ass(x, y, Globals.symbols["eq?"])
Globals.symbols["assv"]   = lambda x, y: _ass(x, y, Globals.symbols["eqv?"])
Globals.symbols["assoc"]  = lambda x, y: _ass(x, y, Globals.symbols["equal?"])

Globals.symbols["symbol?"] = lambda x: Special.T if isinstance(x, Symbol) else Special.F
Globals.symbols["symbol->string"] = lambda x: x.name
Globals.symbols["string->symbol"] = lambda x: Symbol.new(x)

Globals.symbols["string=?"] = lambda x, y: Special.T if x == y else Special.F

Globals.symbols["import"] = lambda x: Globals.define(x.name, __import__(x.name))

def _print(x):
    print x
Globals.symbols["display"] = _print

def external(x):
    if x is None:
        return ""
    if isinstance(x, list):
        return "(" + " ".join(external(i) for i in x) + ")"
    if isinstance(x, Symbol):
        return x.name
    if isinstance(x, str):
        return '"' + re.sub('"', r'\"', x) + '"'
    return str(x)

def psil(s):
    t = tokenise(s)
    r = None
    while True:
        p = parse(t)
        if p is None:
            break
        r = eval(p)
    return r

def rep(s):
    r = psil(s)
    if r is not None:
        print external(r)

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        Globals.symbols["quit"] = lambda: sys.exit(0)
        import traceback
        print "PSIL interactive mode"
        print "Use (quit) to exit"
        while True:
            sys.stdout.write("> ")
            sys.stdout.flush()
            s = sys.stdin.readline()
            try:
                rep(s)
            except SystemExit:
                raise
            except:
                traceback.print_exc()
    elif sys.argv[1] == "--test":
        import doctest
        doctest.testmod(optionflags=doctest.ELLIPSIS)
        doctest.testfile("psil.test", optionflags=doctest.ELLIPSIS)
        doctest.testfile("integ.test", optionflags=doctest.ELLIPSIS)
        doctest.testfile("r5rs.test", optionflags=doctest.ELLIPSIS)
    else:
        f = open(sys.argv[1])
        text = f.read()
        f.close()
        m = re.match(r"#!.*?$", text, re.MULTILINE)
        if m is not None:
            text = text[m.end(0):]
        psil(text)

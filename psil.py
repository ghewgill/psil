"""PSIL: Python S-expresssion Intermediate Language

#>>> read("1")
#1
#>>> eval(read("1"))
#1

"""

import re

RE_NUMBER = re.compile(r"[-+]?\d+(\.\d+)?(e[-+]?\d+)?", re.IGNORECASE)
RE_SYMBOL = re.compile(r"[^ \t\n\)]+", re.IGNORECASE)

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
        elif s[i] == '"':
            j = s.index('"', i+1)
            yield (Token.STRING, s[i+1:j])
            i = j + 1
        else:
            m = RE_NUMBER.match(s[i:])
            if m:
                if m.group(1) or m.group(2):
                    yield (Token.NUMBER, float(m.group(0)))
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

def read(s):
    """
    >>> read("1")
    1
    >>> read("()")
    NIL
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

    def parse(tokens, next = None):
        if next is None:
            next = tokens.next()
        t, v = next
        if t == Token.LPAREN:
            a = []
            while True:
                next = tokens.next()
                if next[0] == Token.RPAREN:
                    break
                a.append(parse(tokens, next))
            if len(a) == 0:
                return Special("NIL")
            return a
        elif t == Token.STRING:
            return v
        elif t == Token.NUMBER:
            return v
        elif t == Token.QUOTE:
            return [Symbol("quote"), parse(tokens)]
        elif t == Token.SYMBOL:
            return Symbol(v)
        else:
            raise SyntaxError(next)

    return parse(tokenise(s))

class Scope(object):
    def __init__(self, parent = None):
        self.parent = parent
        self.symbols = {}
    def add(self, name, value):
        self.symbols[name] = value
    def set(self, name, value):
        s = self
        while s is not None:
            if name in s.symbols:
                s.symbols[name] = value
                return
            s = s.parent
        Globals.symbols[name] = value
    def lookup(self, name):
        s = self
        while s is not None:
            if name in s.symbols:
                return s.symbols[name]
            s = s.parent
        raise UndefinedSymbolError(name)

class Function(object):
    def __init__(self, params, body, scope):
        self.params = params
        self.body = body
        self.scope = scope
    def __call__(self, *args):
        scope = Scope(self.scope)
        for p, a in zip(self.params, args):
            scope.add(p.name, a)
        r = None
        for b in self.body:
            r = eval(b, scope)
        return r

def eval(s, scope = None):
    """
    >>> eval(read("1"))
    1
    >>> eval(read("(+ 1 2 3)"))
    6
    """
    if scope is None:
        scope = Globals
    if isinstance(s, list):
        if isinstance(s[0], Symbol) and s[0].name == "defun":
            scope.add(s[1].name, Function(s[2], s[3:], scope))
            return s[1]
        elif isinstance(s[0], Symbol) and s[0].name == "quote":
            return s[1]
        elif isinstance(s[0], Symbol) and s[0].name == "set":
            sym = eval(s[1], scope)
            if not isinstance(sym, Symbol):
                raise SetNotSymbolError(sym)
            val = eval(s[2], scope)
            scope.set(sym.name, val)
            return val
        elif isinstance(s[0], Symbol) and s[0].name == "setq":
            return eval([Symbol("set"), [Symbol("quote"), s[1]], s[2]], scope)
        else:
            f = eval(s[0], scope)
            args = [eval(x, scope) for x in s[1:]]
            return f(*args)
    elif isinstance(s, Symbol):
        return scope.lookup(s.name)
    else:
        return s

class Special(object):
    def __init__(self, v):
        self.val = v
    def __repr__(self):
        return self.val

Globals = Scope()

Globals.symbols["+"]      = lambda *args: sum(args)
Globals.symbols["-"]      = lambda x, y: x - y
Globals.symbols["*"]      = lambda *args: reduce(lambda x, y: x * y, args)
Globals.symbols["/"]      = lambda x, y: x / y
Globals.symbols["t"]      = Special("T")
Globals.symbols["nil"]    = Special("NIL")
Globals.symbols["cons"]   = lambda x, y: [x] + y if isinstance(y, list) else [x]
Globals.symbols["list"]   = lambda *args: list(args)
Globals.symbols["append"] = lambda *args: reduce(lambda x, y: x + y, args)
Globals.symbols["first"]  = lambda x: x[0]
Globals.symbols["rest"]   = lambda x: x[1:]
Globals.symbols["car"]    = Globals.symbols["first"]
Globals.symbols["cdr"]    = Globals.symbols["rest"]
Globals.symbols["length"] = lambda x: len(x)
Globals.symbols["atom"]   = lambda x: Globals.symbols["t"] if not isinstance(x, list) else Globals.symbols["nil"]
Globals.symbols["listp"]  = lambda x: Globals.symbols["t"] if isinstance(x, list) else Globals.symbols["nil"]

if __name__ == "__main__":
    import doctest
    doctest.testmod()
    doctest.testfile("psil.test")

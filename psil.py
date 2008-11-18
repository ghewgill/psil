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
    QQUOTE = object()
    COMMA  = object()
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
        elif s[i] == "`":
            yield (Token.QQUOTE, s[i])
            i += 1
        elif s[i] == ",":
            yield (Token.COMMA, s[i])
            i += 1
        elif s[i] == '"':
            j = s.index('"', i+1)
            yield (Token.STRING, __builtins__.eval(s[i:j+1]))
            i = j + 1
        elif s[i] == ";":
            i = s.index("\n", i+1)
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
        return a
    elif t == Token.STRING:
        return v
    elif t == Token.NUMBER:
        return v
    elif t == Token.QUOTE:
        return [Symbol("quote"), parse(tokens)]
    elif t == Token.QQUOTE:
        return [Symbol("quasiquote"), parse(tokens)]
    elif t == Token.COMMA:
        return [Symbol("unquote"), parse(tokens)]
    elif t == Token.SYMBOL:
        return Symbol(v)
    else:
        raise SyntaxError(next)

def read(s):
    """
    >>> read("1")
    1
    >>> read("()")
    []
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

class Function(object):
    def __init__(self, params, body, scope):
        self.params = params
        self.body = body
        self.scope = scope
    def __call__(self, *args):
        scope = Scope(self.scope)
        for p, a in zip(self.params, args):
            scope.define(p.name, a)
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
    >>> eval(read("((lambda (x) (* x x)) 3)"))
    9
    >>> eval(read("(define (test fn x y) ((if fn * +) x y))"))
    <test>
    >>> eval(read("(test #t 2 3)"))
    6
    >>> eval(read("(test #f 2 3)"))
    5
    """
    if scope is None:
        scope = Globals
    if isinstance(s, list) and len(s) > 0:
        if isinstance(s[0], Symbol):
            if s[0].name == "define":
                if isinstance(s[1], Symbol):
                    scope.define(s[1].name, eval(s[2]))
                    return s[1]
                else:
                    scope.define(s[1][0].name, Function(s[1][1:], s[2:], scope))
                    return s[1][0]
            if s[0].name == "if":
                if eval(s[1], scope) != Special.F:
                    return eval(s[2], scope)
                else:
                    return eval(s[3], scope)
            if s[0].name == "lambda":
                return Function(s[1], s[2:], scope)
            if s[0].name == "quasiquote":
                def qq(t):
                    if isinstance(t, list):
                        return [eval(x[1], scope) if isinstance(x, list) and isinstance(x[0], Symbol) and x[0].name == "unquote" else qq(x) for x in t]
                    else:
                        return t
                return qq(s[1])
            if s[0].name == "quote":
                return s[1]
            if s[0].name == "set!":
                if not isinstance(s[1], Symbol):
                    raise SetNotSymbolError(s[1])
                val = eval(s[2], scope)
                scope.set(s[1].name, val)
                return val
            if s[0].name.startswith("."):
                return getattr(eval(s[1], scope), s[0].name[1:])
        f = eval(s[0], scope)
        args = [eval(x, scope) for x in s[1:]]
        return f(*args)
    elif isinstance(s, Symbol):
        r = scope.lookup(s.name)
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

class Special(object):
    def __init__(self, v):
        self.val = v
    def __repr__(self):
        return self.val

Special.T = Special("T")
Special.F = Special("F")

Globals = Scope()

Globals.symbols["+"]      = lambda *args: sum(args)
Globals.symbols["-"]      = lambda x, y: x - y
Globals.symbols["*"]      = lambda *args: reduce(lambda x, y: x * y, args)
Globals.symbols["/"]      = lambda x, y: x / y
Globals.symbols["="]      = lambda x, y: Special.T if x == y else Special.F
Globals.symbols[">"]      = lambda x, y: Special.T if x > y else Special.F
Globals.symbols["<"]      = lambda x, y: Special.T if x < y else Special.F
Globals.symbols["#t"]     = Special.T
Globals.symbols["#f"]     = Special.F
Globals.symbols["cons"]   = lambda x, y: [x] + y if isinstance(y, list) else [x]
Globals.symbols["list"]   = lambda *args: list(args)
Globals.symbols["append"] = lambda *args: reduce(lambda x, y: x + y, args)
Globals.symbols["first"]  = lambda x: x[0]
Globals.symbols["rest"]   = lambda x: x[1:]
Globals.symbols["car"]    = Globals.symbols["first"]
Globals.symbols["cdr"]    = Globals.symbols["rest"]
Globals.symbols["length"] = lambda x: len(x)
Globals.symbols["list?"]  = lambda x: Special.T if isinstance(x, list) else Special.F
Globals.symbols["apply"]  = lambda x, args: x(*args)

def _import(x):
    exec "import "+x.name
    mod = locals()[x.name]
    Globals.define(x.name, mod)
    return mod
Globals.symbols["import"] = _import

def _print(x):
    print x
Globals.symbols["display"] = _print

def psil(s):
    t = tokenise(s)
    while True:
        p = parse(t)
        if p is None:
            break
        r = eval(p)
    return r

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        import traceback
        while True:
            sys.stdout.write("> ")
            sys.stdout.flush()
            s = sys.stdin.readline()
            try:
                print psil(s)
            except:
                traceback.print_exc()
    elif sys.argv[1] == "--test":
        import doctest
        doctest.testmod()
        doctest.testfile("psil.test")
        #doctest.testfile("integ.test")
    else:
        f = open(sys.argv[1])
        text = f.read()
        f.close()
        m = re.match(r"#!.*?$", text, re.MULTILINE)
        if m is not None:
            text = text[m.end(0):]
        psil(text)

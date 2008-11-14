"""PSIL: Python S-expresssion Intermediate Language

#>>> read("1")
#1
#>>> eval(read("1"))
#1

"""

import re

RE_NUMBER = re.compile(r"[-+]?\d+(\.\d+)?(e[-+]?\d+)?", re.IGNORECASE)
RE_SYMBOL = re.compile(r"[^ \)]+", re.IGNORECASE)

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
        while i < len(s) and s[i] == " ":
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
    def lookup(self):
        if self.name not in Symbols:
            raise UndefinedSymbolError(self.name)
        return Symbols[self.name]

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

def eval(s):
    """
    >>> eval(read("1"))
    1
    >>> eval(read("(+ 1 2 3)"))
    6
    """
    if isinstance(s, list):
        if isinstance(s[0], Symbol) and s[0].name == "quote":
            return s[1]
        elif isinstance(s[0], Symbol) and s[0].name == "set":
            sym = eval(s[1])
            if not isinstance(sym, Symbol):
                raise SetNotSymbolError(sym)
            val = eval(s[2])
            Symbols[sym.name] = val
            return val
        elif isinstance(s[0], Symbol) and s[0].name == "setq":
            return eval([Symbol("set"), [Symbol("quote"), s[1]], s[2]])
        else:
            f = eval(s[0])
            args = [eval(x) for x in s[1:]]
            return f(*args)
    elif isinstance(s, Symbol):
        return s.lookup()
    else:
        return s

class Special(object):
    def __init__(self, v):
        self.val = v
    def __repr__(self):
        return self.val

Symbols["+"] = lambda *args: sum(args)
Symbols["-"] = lambda x, y: x - y
Symbols["*"] = lambda *args: reduce(lambda x, y: x * y, args)
Symbols["/"] = lambda x, y: x / y
Symbols["t"] = Special("T")
Symbols["nil"] = Special("NIL")
Symbols["cons"] = lambda x, y: [x] + y if isinstance(y, list) else [x]
Symbols["list"] = lambda *args: list(args)
Symbols["append"] = lambda *args: reduce(lambda x, y: x + y, args)
Symbols["first"] = lambda x: x[0]
Symbols["rest"] = lambda x: x[1:]
Symbols["length"] = lambda x: len(x)
Symbols["atom"] = lambda x: Symbols["t"] if not isinstance(x, list) else Symbols["nil"]
Symbols["listp"] = lambda x: Symbols["t"] if isinstance(x, list) else Symbols["nil"]

if __name__ == "__main__":
    import doctest
    doctest.testmod()
    doctest.testfile("psil.test")

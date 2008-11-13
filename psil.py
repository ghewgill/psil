"""PSIL: Python S-expresssion Intermediate Language

#>>> read("1")
#1
#>>> eval(read("1"))
#1

"""

import re

RE_NUMBER = re.compile(r"[-+]?\d+(\.\d+)?(e[-+]?\d+)?", re.IGNORECASE)
RE_SYMBOL = re.compile(r"[a-z][-a-z0-9]*", re.IGNORECASE)

class SyntaxError(Exception):
    def __init__(self, s):
        Exception.__init__(self, s)

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
    >>> read('''(a 1 "test")''')
    [<a>, 1, 'test']
    >>> read("(a (b c) d)")
    [<a>, [<b>, <c>], <d>]
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
            return a
        elif t == Token.STRING:
            return v
        elif t == Token.NUMBER:
            return v
        elif t == Token.SYMBOL:
            return Symbol(v)

    return parse(tokenise(s))

def eval(s):
    pass

if __name__ == "__main__":
    import doctest
    doctest.testmod()

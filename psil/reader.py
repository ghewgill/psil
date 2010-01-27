import re

from .symbol import Symbol

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

RE_NUMBER = re.compile(r"(?:[-+]?\d+(\.\d+)?(e[-+]?\d+)?|(0x[0-9a-f]+))(?!\w)", re.IGNORECASE)
RE_SYMBOL = re.compile(r"[^ \t\n\(\)]+", re.IGNORECASE)
RE_STRING = re.compile(PY_STRING_LITERAL_RE, re.VERBOSE)

class SyntaxError(Exception):
    def __init__(self, s):
        Exception.__init__(self, s)

class Singleton(object):
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return self.name

class Token(object):
    LPAREN = Singleton("LPAREN")
    RPAREN = Singleton("RPAREN")
    QUOTE  = Singleton("QUOTE")
    QQUOTE = Singleton("QQUOTE")
    COMMA  = Singleton("COMMA")
    SPLICE = Singleton("SPLICE")
    SYMBOL = Singleton("SYMBOL")
    NUMBER = Singleton("NUMBER")
    STRING = Singleton("STRING")

def tokenise(s):
    """
    >>> [x[1] for x in tokenise("1")]
    [1]
    >>> [x[1] for x in tokenise("0x42")]
    [66]
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
    >>> [x[1] for x in tokenise("(a(b))")]
    ['(', 'a', '(', 'b', ')', ')']
    >>> list(tokenise("foo bar baz"))
    [(SYMBOL, 'foo', (1, 0)), (SYMBOL, 'bar', (1, 4)), (SYMBOL, 'baz', (1, 8))]
    >>> list(tokenise("( ) ' `\\n, ,@ \\"a\\" ; comment\\n1.234 symbol"))
    [(LPAREN, '(', (1, 0)), (RPAREN, ')', (1, 2)), (QUOTE, "'", (1, 4)), (QQUOTE, '`', (1, 6)), (COMMA, ',', (2, 0)), (SPLICE, ',@', (2, 2)), (STRING, 'a', (2, 5)), (NUMBER, 1.234, (3, 0)), (SYMBOL, 'symbol', (3, 6))]
    """
    lineno = 1
    col_offset = 0
    i = 0
    while True:
        while i < len(s) and s[i].isspace():
            if s[i] == "\n":
                lineno += 1
                col_offset = 0
            else:
                col_offset += 1
            i += 1
        if i >= len(s):
            break
        if   s[i] == "(":
            yield (Token.LPAREN, s[i], (lineno, col_offset))
            col_offset += 1
            i += 1
        elif s[i] == ")":
            yield (Token.RPAREN, s[i], (lineno, col_offset))
            col_offset += 1
            i += 1
        elif s[i] == "'":
            yield (Token.QUOTE, s[i], (lineno, col_offset))
            col_offset += 1
            i += 1
        elif s[i] == "`":
            yield (Token.QQUOTE, s[i], (lineno, col_offset))
            col_offset += 1
            i += 1
        elif s[i] == ",":
            if s[i+1] == "@":
                yield (Token.SPLICE, s[i:i+2], (lineno, col_offset))
                col_offset += 2
                i += 2
            else:
                yield (Token.COMMA, s[i], (lineno, col_offset))
                col_offset += 1
                i += 1
        elif s[i] == '"':
            m = RE_STRING.match(s[i:])
            if m:
                yield (Token.STRING, eval(m.group(0)), (lineno, col_offset))
                col_offset += m.end(0)
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
                    yield (Token.NUMBER, x, (lineno, col_offset))
                elif m.group(3):
                    yield (Token.NUMBER, int(m.group(3), 16), (lineno, col_offset))
                else:
                    yield (Token.NUMBER, int(m.group(0)), (lineno, col_offset))
                col_offset += m.end(0)
                i += m.end(0)
            else:
                m = RE_SYMBOL.match(s[i:])
                if m:
                    yield (Token.SYMBOL, m.group(0), (lineno, col_offset))
                    col_offset += m.end(0)
                    i += m.end(0)
                else:
                    raise SyntaxError(s[i:])

Symbol.quote            = Symbol.new("quote")
Symbol.quasiquote       = Symbol.new("quasiquote")
Symbol.unquote          = Symbol.new("unquote")
Symbol.unquote_splicing = Symbol.new("unquote-splicing")

Symbol.define           = Symbol.new("define")
Symbol.defmacro         = Symbol.new("defmacro")
Symbol.if_              = Symbol.new("if")
Symbol.lambda_          = Symbol.new("lambda")
Symbol.set              = Symbol.new("set!")

def parse(tokens, nextoken = None):
    """
    >>> parse(tokenise("(a b c)"))
    [<a>, <b>, <c>]
    >>> parse(tokenise("'()"))
    [<quote>, []]
    >>> parse(tokenise("("))
    Traceback (most recent call last):
        ...
    psil.reader.SyntaxError: unclosed parenthesis
    >>> parse(tokenise("())"))
    []
    """
    if nextoken is None:
        try:
            nextoken = next(tokens)
        except StopIteration:
            return None
    t, v, pos = nextoken
    if t == Token.LPAREN:
        a = []
        while True:
            try:
                nextoken = next(tokens)
            except StopIteration:
                raise SyntaxError("unclosed parenthesis")
            if nextoken[0] == Token.RPAREN:
                break
            a.append(parse(tokens, nextoken))
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
        raise SyntaxError(nextoken)

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

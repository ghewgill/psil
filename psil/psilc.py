import compiler

from .symbol import Symbol

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

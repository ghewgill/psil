import ast
import sys

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

#InlineFuncs = {
#    "+": "(lambda *x: sum(x))",
#    "*": "(lambda *x: functools.reduce(operator.mul, x, 1))",
#    "==": "(lambda *x: all(map(lambda i: x[i] == x[i+1], range(len(x)-1))))",
#    "and": "(lambda *x: functools.reduce(operator.and_, x))",
#    "append": "(lambda *x: functools.reduce(operator.concat, x))",
#    "cadr": "(lambda x: x[1])",
#    "car": "(lambda x: x[0])",
#    "concat": "(lambda *x: ''.join([str(y) for y in x]))",
#    "make_list": "list",
#    "not": "(lambda x: not x)",
#    "reverse": "(lambda x: list(reversed(x)))",
#}

def operator(op):
    if isinstance(op, ast.Add):
        return "+"
    elif isinstance(op, ast.BitAnd):
        return "&"
    elif isinstance(op, ast.BitXor):
        return "^"
    elif isinstance(op, ast.Div):
        return "/"
    elif isinstance(op, ast.Eq):
        return "=="
    elif isinstance(op, ast.FloorDiv):
        return "//"
    elif isinstance(op, ast.Gt):
        return ">"
    elif isinstance(op, ast.GtE):
        return ">="
    elif isinstance(op, ast.In):
        return "in"
    elif isinstance(op, ast.Is):
        return "is"
    elif isinstance(op, ast.IsNot):
        return "is not"
    elif isinstance(op, ast.LShift):
        return "<<"
    elif isinstance(op, ast.Lt):
        return "<"
    elif isinstance(op, ast.LtE):
        return "<="
    elif isinstance(op, ast.Mod):
        return "%"
    elif isinstance(op, ast.Mult):
        return "*"
    elif isinstance(op, ast.Not):
        return "not"
    elif isinstance(op, ast.NotEq):
        return "!="
    elif isinstance(op, ast.NotIn):
        return "not in"
    elif isinstance(op, ast.Pow):
        return "**"
    elif isinstance(op, ast.RShift):
        return ">>"
    elif isinstance(op, ast.Sub):
        return "-"
    elif isinstance(op, ast.USub):
        return "-"
    else:
        print("unhandled operator:", op, file=sys.stderr)
        sys.exit(1)

def expr(node):
    #print("node:", node)
    if isinstance(node, ast.Attribute):
        return "{0}.{1}".format(expr(node.value), node.attr)
    elif isinstance(node, ast.BinOp):
        return "({0} {1} {2})".format(expr(node.left), operator(node.op), expr(node.right))
    elif isinstance(node, ast.Call):
        func = ("({0})" if isinstance(node.func, ast.Lambda) else "{0}").format(expr(node.func))
        args = None
        if node.args is not None:
            args = ", ".join(expr(x) for x in node.args)
        elif node.starargs is not None:
            if isinstance(node.starargs, list):
                args = ", ".join(expr(x) for x in node.starargs)
            else:
                args = "*" + expr(node.starargs)
        return "{0}({1})".format(func, args)
    elif isinstance(node, ast.Compare):
        return "({0} {1})".format(expr(node.left), " ".join("{0} {1}".format(operator(op), expr(comp)) for op, comp in zip(node.ops, node.comparators)))
    elif isinstance(node, ast.IfExp):
        return "({1} if {0} else {2})".format(expr(node.test), expr(node.body), expr(node.orelse) if node.orelse else "None")
    elif isinstance(node, ast.Lambda):
        return "lambda {0}: {1}".format(", ".join(x.arg for x in node.args.args), expr(node.body))
    elif isinstance(node, ast.List):
        return "[{0}]".format(", ".join(expr(x) for x in node.elts))
    elif isinstance(node, ast.Num):
        return repr(node.n)
    elif isinstance(node, ast.Name):
        f = None #InlineFuncs.get(node.id)
        if f:
            return f
        else:
            return node.id
    elif isinstance(node, ast.Subscript):
        if isinstance(node.slice, ast.Index):
            return "{0}[{1}]".format(expr(node.value), expr(node.slice.value))
        elif isinstance(node.slice, ast.Slice):
            return "{0}[{1}:{2}]".format(expr(node.value), expr(node.slice.lower) if node.slice.lower else "", expr(node.slice.upper) if node.slice.upper else "")
        else:
            print("unhandled slice:", node.slice, file=sys.stderr)
            sys.exit(1)
    elif isinstance(node, ast.Str):
        return repr(node.s)
    elif isinstance(node, ast.UnaryOp):
        return "({0}{1})".format(operator(node.op), expr(node.operand))
    else:
        print("unhandled expr:", node, file=sys.stderr)
        sys.exit(1)

def stmt(node, source):
    if isinstance(node, list):
        for x in node:
            stmt(x, source)
    elif isinstance(node, ast.Assign):
        source.line("".join([expr(x)+" = " for x in node.targets]) + expr(node.value))
    elif isinstance(node, ast.Expr):
        source.line(expr(node.value))
    elif isinstance(node, ast.FunctionDef):
        source.line("def " + node.name + "(" + ", ".join(x.arg for x in node.args.args) + "):")
        source.indent()
        stmt(node.body, source)
        source.dedent()
    elif isinstance(node, ast.If):
        source.line("if " + expr(node.tests[0][0]) + ":")
        source.indent()
        stmt(node.tests[0][1], source)
        source.dedent()
        if node.else_:
            source.line("else:")
            source.indent()
            stmt(node.else_, source)
            source.dedent()
    elif isinstance(node, ast.Return):
        source.line("return " + expr(node.value))
    else:
        print("unhandled stmt:", node, file=sys.stderr)
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
    ast.walk(node)
    if isinstance(node, (ast.Module, ast.Interactive)):
        stmt(node.body, source)
    elif isinstance(node, ast.Expression):
        source.line(expr(node.body))
    else:
        print("unhandled mod:", node, file=sys.stderr)
        sys.exit(1)

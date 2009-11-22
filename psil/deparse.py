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

def operator(op):
    if isinstance(op, ast.Add):
        return "+"
    elif isinstance(op, ast.Eq):
        return "=="
    elif isinstance(op, ast.Mod):
        return "%"
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
        func = ("({0})" if isinstance(node, ast.Lambda) else "{0}").format(expr(node.func))
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
        return "lambda " + ", ".join(node.args) + ": " + expr(node.body)
    elif isinstance(node, ast.List):
        return "[{0}]".format(", ".join(expr(x) for x in node.elts))
    elif isinstance(node, ast.Num):
        return repr(node.n)
    elif isinstance(node, ast.Name):
        f = InlineFuncs.get(node.id)
        if f:
            return f
        else:
            return node.id

    #elif isinstance(node, compiler.ast.Add):
    #    return "(%s + %s)" % (expr(node.left), expr(node.right))
    #elif isinstance(node, compiler.ast.AssName):
    #    return node.name
    #elif isinstance(node, compiler.ast.Bitand):
    #    return "(" + " & ".join([expr(x) for x in node.nodes]) + ")"
    #elif isinstance(node, compiler.ast.Bitxor):
    #    return "(" + " ^ ".join([expr(x) for x in node.nodes]) + ")"
    #elif isinstance(node, compiler.ast.CallFunc):
    #    if isinstance(node.node, compiler.ast.Lambda):
    #        return "(" + expr(node.node) + ")(" + ", ".join([expr(x) for x in node.args]) + ")"
    #    else:
    #        return expr(node.node) + "(" + ", ".join([expr(x) for x in node.args]) + ")"
    #elif isinstance(node, compiler.ast.Compare):
    #    return "(" + expr(node.expr) + "".join([" " + x[0] + " " + expr(x[1]) + ")" for x in node.ops])
    #elif isinstance(node, compiler.ast.Const):
    #    return repr(node.value)
    #elif isinstance(node, compiler.ast.Div):
    #    return "(%s / %s)" % (expr(node.left), expr(node.right))
    #elif isinstance(node, compiler.ast.Getattr):
    #    return expr(node.expr) + "." + node.attrname
    #elif isinstance(node, compiler.ast.If):
    #    return "(" + expr(node.tests[0][1]) + " if " + expr(node.tests[0][0]) + " else " + (expr(node.else_) if node.else_ else "None") + ")"
    #elif isinstance(node, compiler.ast.Lambda):
    #    if hasattr(node, "name"):
    #        return node.name
    #    else:
    #        return "lambda " + ", ".join(node.argnames) + ": " + expr(node.code)
    #elif isinstance(node, compiler.ast.LeftShift):
    #    return "(%s << %s)" % (expr(node.left), expr(node.right))
    #elif isinstance(node, compiler.ast.List):
    #    return "[" + ", ".join([expr(x) for x in node.nodes]) + "]"
    #elif isinstance(node, compiler.ast.Mod):
    #    return "(%s %% %s)" % (expr(node.left), expr(node.right))
    #elif isinstance(node, compiler.ast.Mul):
    #    return "(%s * %s)" % (expr(node.left), expr(node.right))
    #elif isinstance(node, compiler.ast.Name):
    #    f = InlineFuncs.get(node.name)
    #    if f:
    #        return f
    #    else:
    #        return node.name
    #elif isinstance(node, compiler.ast.Not):
    #    return "not %s" % expr(node.expr)
    #elif isinstance(node, compiler.ast.Power):
    #    return "(%s ** %s)" % (expr(node.left), expr(node.right))
    #elif isinstance(node, compiler.ast.RightShift):
    #    return "(%s >> %s)" % (expr(node.left), expr(node.right))
    #elif isinstance(node, compiler.ast.Slice):
    #    return expr(node.expr) + "[" + (expr(node.lower) if node.lower else "") + ":" + (expr(node.upper) if node.upper else "") + "]"
    #elif isinstance(node, compiler.ast.Sub):
    #    return "(%s - %s)" % (expr(node.left), expr(node.right))
    #elif isinstance(node, compiler.ast.Subscript):
    #    return "%s[%s]" % (expr(node.expr), expr(node.subs))
    #elif isinstance(node, compiler.ast.UnarySub):
    #    return "-(%s)" % expr(node.expr)
    else:
        print("unhandled expr:", node, file=sys.stderr)
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
    #compiler.walk(node, LiftLambda())
    if isinstance(node, ast.Assign):
        source.line("".join([expr(x)+" = " for x in node.targets]) + expr(node.value))
    elif isinstance(node, ast.FunctionDef):
        source.line("def " + node.name + "(" + ", ".join(node.args) + "):")
        source.indent()
        gen_source(node.body, source)
        source.dedent()
    elif isinstance(node, ast.If):
        source.line("if " + expr(node.tests[0][0]) + ":")
        source.indent()
        gen_source(node.tests[0][1], source)
        source.dedent()
        if node.else_:
            source.line("else:")
            source.indent()
            gen_source(node.else_, source)
            source.dedent()
    elif isinstance(node, ast.Return):
        source.line("return " + expr(node.value))
    elif isinstance(node, ast.Suite):
        for x in node.body:
            gen_source(x, source)
    else:
        source.line(expr(node))

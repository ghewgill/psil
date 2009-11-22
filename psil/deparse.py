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

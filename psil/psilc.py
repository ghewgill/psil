import ast

from . import deparse
from .symbol import Symbol

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
        return ast.BinOp(build_ast(p[1]), ast.Add(), build_ast(p[2]))
    else:
        return compiler.ast.Add((compile_add(p[:-1]), build_ast(p[-1])))

def compile_define(p):
    if isinstance(p[1], list):
        stmt = [build_ast(x) for x in p[2:]]
        if not isinstance(stmt[-1], ast.Assign):
            stmt[-1] = ast.Return(stmt[-1])
        return ast.FunctionDef(pydent(p[1][0].name), [x.name for x in p[1][1:]], ast.Suite(stmt), None, None)
    else:
        return ast.Assign([ast.Name(pydent(p[1].name), ast.Store)], build_ast(p[2]))

def compile_divide(p):
    if len(p) == 2:
        return compiler.ast.Div((compiler.ast.Const(1), build_ast(p[1])))
    elif len(p) == 3:
        return compiler.ast.Div((build_ast(p[1]), build_ast(p[2])))
    else:
        return compiler.ast.Div((compile_divide(p[:-1]), build_ast(p[-1])))

def compile_equals(p):
    return ast.Compare(build_ast(p[1]), (ast.Eq() for x in p[1::2]), (build_ast(x) for x in p[2::2]))

def compile_lambda(p):
    if len(p) > 3:
        return compiler.ast.Lambda([pydent(x.name) for x in p[1]], [], 0, [build_ast(x) for x in p[2:]])
    else:
        return ast.Lambda([pydent(x.name) for x in p[1]], build_ast(p[2]))

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
            return ast.List([q(x) for x in p], ast.Load)
        elif isinstance(p, Symbol):
            return compiler.ast.CallFunc(compiler.ast.Name("sym"), [compiler.ast.Const(p.name)])
        else:
            return ast.Num(p)
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
    Symbol.new("%"): lambda p: ast.BinOp(build_ast(p[1]), ast.Mod(), build_ast(p[2])),
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
    Symbol.new("apply"): lambda p: ast.Call(build_ast(p[1]), None, None, [build_ast(x) for x in p[2:]], None),
    Symbol.new("if"): lambda p: ast.IfExp(build_ast(p[1]), build_ast(p[2]), build_ast(p[3]) if len(p) >= 4 else None),
    Symbol.new("in"): lambda p: compiler.ast.Compare(build_ast(p[1]), [("in", build_ast(p[2]))]),
    Symbol.new("index"): lambda p: compiler.ast.Subscript(build_ast(p[1]), 0, build_ast(p[2])),
    Symbol.new("lambda"): compile_lambda,
    Symbol.new("list"): lambda p: compiler.ast.List([build_ast(x) for x in p[1:]]),
    Symbol.new("not"): lambda p: compiler.ast.Not(build_ast(p[1])),
    Symbol.new("not-in"): lambda p: compiler.ast.Compare(build_ast(p[1]), [("not in", build_ast(p[2]))]),
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
                return ast.Call(ast.Attribute(build_ast(p[1]), p[0].name[1:], ast.Load), [build_ast(x) for x in p[2:]], None, None, None)
            else:
                return ast.Call(ast.Name(pydent(p[0].name), ast.Load), [build_ast(x) for x in p[1:]], None, None, None)
        else:
            return ast.Call(build_ast(p[0]), [build_ast(x) for x in p[1:]], None, None, None)
    elif isinstance(p, Symbol):
        return ast.Name(pydent(p.name), ast.Load)
    else:
        return ast.Num(p)

def psilc(p):
    tree = build_ast(p)
    def dump(node, depth):
        print("  "*depth, node, sep="")
        for x in ast.iter_child_nodes(node):
            dump(x, depth+1)
    print("ast:")
    dump(tree, 0)
    source = deparse.SourceGenerator()
    deparse.gen_source(tree, source)
    print("source:")
    print(str(source))
    return str(source)

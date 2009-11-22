import ast

from . import deparse
from .symbol import Symbol

def pydent(s):
    if s == "try": s = "try_"
    s = s.replace("-", "_")
    s = s.replace(".", "_")
    s = s.replace(">", "_")
    s = s.replace("?", "_")
    return s

def compile_add(p):
    if len(p) == 2:
        return build_ast(p[1])
    elif len(p) == 3:
        return ast.BinOp(build_ast(p[1]), ast.Add(), build_ast(p[2]))
    else:
        return ast.BinOp(compile_add(p[:-1]), ast.Add(), build_ast(p[-1]))

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
        return ast.BinOp(ast.Num(1), ast.Div(), build_ast(p[1]))
    elif len(p) == 3:
        return ast.BinOp(build_ast(p[1]), ast.Div(), build_ast(p[2]))
    else:
        return ast.BinOp(compile_divide(p[:-1]), ast.Div(), build_ast(p[-1]))

def compile_floordivide(p):
    if len(p) == 2:
        return ast.BinOp(ast.Num(1), ast.FloorDiv(), build_ast(p[1]))
    elif len(p) == 3:
        return ast.BinOp(build_ast(p[1]), ast.FloorDiv(), build_ast(p[2]))
    else:
        return ast.BinOp(compile_divide(p[:-1]), ast.FloorDiv(), build_ast(p[-1]))

def compile_equals(p):
    return ast.Compare(build_ast(p[1]), (ast.Eq() for x in p[1::2]), (build_ast(x) for x in p[2::2]))

def compile_lambda(p):
    if len(p) > 3:
        return ast.Lambda([pydent(x.name) for x in p[1]], [build_ast(x) for x in p[2:]])
    else:
        return ast.Lambda([pydent(x.name) for x in p[1]], build_ast(p[2]))

def compile_multiply(p):
    if len(p) == 2:
        return build_ast(p[1])
    elif len(p) == 3:
        return ast.BinOp(build_ast(p[1]), ast.Mult(), build_ast(p[2]))
    else:
        return ast.BinOp(compile_multiply(p[:-1]), ast.Mult(), build_ast(p[-1]))

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
        return ast.UnaryOp(ast.USub(), build_ast(p[1]))
    elif len(p) == 3:
        return ast.BinOp(build_ast(p[1]), ast.Sub(), build_ast(p[2]))
    else:
        return ast.BinOp(compile_subtract(p[:-1]), ast.Sub(), build_ast(p[-1]))

CompileFuncs = {
    Symbol.new("+"): compile_add,
    Symbol.new("-"): compile_subtract,
    Symbol.new("*"): compile_multiply,
    Symbol.new("/"): compile_divide,
    Symbol.new("//"): compile_floordivide,
    Symbol.new("%"): lambda p: ast.BinOp(build_ast(p[1]), ast.Mod(), build_ast(p[2])),
    Symbol.new("&"): lambda p: ast.BinOp(build_ast(p[1]), ast.BitAnd(), build_ast(p[2])),
    Symbol.new("**"): lambda p: ast.BinOp(build_ast(p[1]), ast.Pow(), build_ast(p[2])),
    Symbol.new(">>"): lambda p: ast.BinOp(build_ast(p[1]), ast.RShift(), build_ast(p[2])),
    Symbol.new("<<"): lambda p: ast.BinOp(build_ast(p[1]), ast.LShift(), build_ast(p[2])),
    Symbol.new("^"): lambda p: ast.BinOp(build_ast(p[1]), ast.BitXor(), build_ast(p[2])),
    Symbol.new("<"): lambda p: ast.Compare(build_ast(p[1]), (ast.Lt() for x in p[1::2]), (build_ast(x) for x in p[2::2])),
    Symbol.new(">"): lambda p: ast.Compare(build_ast(p[1]), (ast.Gt() for x in p[1::2]), (build_ast(x) for x in p[2::2])),
    Symbol.new("<="): lambda p: ast.Compare(build_ast(p[1]), (ast.LtE() for x in p[1::2]), (build_ast(x) for x in p[2::2])),
    Symbol.new(">="): lambda p: ast.Compare(build_ast(p[1]), (ast.GtE() for x in p[1::2]), (build_ast(x) for x in p[2::2])),
    Symbol.new("=="): compile_equals,
    Symbol.new("!="): lambda p: ast.BinOp(build_ast(p[1]), ast.NotEq(), build_ast(p[2])),
    Symbol.new("is"): lambda p: ast.BinOp(build_ast(p[1]), ast.Is(), build_ast(p[2])),
    Symbol.new("is-not"): lambda p: ast.BinOp(build_ast(p[1]), ast.IsNot(), build_ast(p[2])),
    Symbol.new("define"): compile_define,
    Symbol.new("dict-set"): lambda p: ast.Assign([ast.Subscript(build_ast(p[1]), ast.Index(build_ast(p[2])), ast.Store)], build_ast(p[3])),
    #Symbol.new("caadr"): lambda p: compiler.ast.Subscript(compiler.ast.Subscript(build_ast(p[1]), 0, compiler.ast.Const(1)), 0, compiler.ast.Const(0)),
    Symbol.new("caar"): lambda p: ast.Subscript(ast.Subscript(build_ast(p[1]), ast.Index(ast.Num(0)), ast.Load), ast.Index(ast.Num(0)), ast.Load),
    #Symbol.new("cadddr"): lambda p: compiler.ast.Subscript(build_ast(p[1]), 0, compiler.ast.Const(3)),
    #Symbol.new("caddr"): lambda p: compiler.ast.Subscript(build_ast(p[1]), 0, compiler.ast.Const(2)),
    Symbol.new("cadr"): lambda p: ast.Subscript(build_ast(p[1]), ast.Index(ast.Num(1)), ast.Load),
    Symbol.new("car"): lambda p: ast.Subscript(build_ast(p[1]), ast.Index(ast.Num(0)), ast.Load),
    Symbol.new("cdar"): lambda p: ast.Subscript(ast.Subscript(build_ast(p[1]), ast.Index(ast.Num(0)), ast.Load), ast.Slice(ast.Num(1), None, None), ast.Load),
    #Symbol.new("cddr"): lambda p: compiler.ast.Slice(build_ast(p[1]), 0, compiler.ast.Const(2), None),
    Symbol.new("cdr"): lambda p: ast.Subscript(build_ast(p[1]), ast.Slice(ast.Num(1), None, None), ast.Load),
    Symbol.new("cons"): lambda p: ast.BinOp(ast.List([build_ast(p[1])], ast.Load), ast.Add(), build_ast(p[2])),
    Symbol.new("apply"): lambda p: ast.Call(build_ast(p[1]), None, None, build_ast(p[2]), None),
    Symbol.new("if"): lambda p: ast.IfExp(build_ast(p[1]), build_ast(p[2]), build_ast(p[3]) if len(p) >= 4 else None),
    Symbol.new("in"): lambda p: ast.BinOp(build_ast(p[1]), ast.In(), build_ast(p[2])),
    Symbol.new("index"): lambda p: ast.Subscript(build_ast(p[1]), ast.Index(build_ast(p[2])), ast.Load),
    Symbol.new("lambda"): compile_lambda,
    Symbol.new("list"): lambda p: ast.List([build_ast(x) for x in p[1:]], ast.Load),
    Symbol.new("not"): lambda p: ast.UnaryOp(ast.Not(), build_ast(p[1])),
    Symbol.new("not-in"): lambda p: ast.BinOp(build_ast(p[1]), ast.NotIn(), build_ast(p[2])),
    Symbol.new("quote"): compile_quote,
    Symbol.new("set!"): lambda p: ast.Assign([ast.Name(p[1].name, ast.Store)], build_ast(p[2])),
    Symbol.new("slice"): lambda p: ast.Subscript(build_ast(p[1]), ast.Slice(build_ast(p[2]), build_ast(p[3]), None), ast.Load),
    Symbol.new("string->symbol"): lambda p: ast.Call(ast.Name("intern"), [build_ast(p[1])], None, None, None),
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
    #print("ast:")
    #dump(tree, 0)
    source = deparse.SourceGenerator()
    deparse.gen_source(tree, source)
    #print("source:")
    #print(str(source))
    return str(source)

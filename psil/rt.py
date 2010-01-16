import ast
import builtins
import marshal
import os
import py_compile

from . import interpreter
from .compiler import psilc

def _import(fn, globals):
    try:
        return __import__(fn, globals=globals)
    except ImportError:
        psilname = fn + ".psil"
        pycname = fn + ".pyc"
        try:
            psilstat = os.stat(psilname)
        except OSError:
            raise ImportError("no such module")
        timestamp = int(psilstat.st_mtime)
        try:
            pycstat = os.stat(pycname)
        except OSError:
            pycstat = None
        if pycstat is None or pycstat.st_mtime < timestamp:
            f = open(psilname)
            code = f.read()
            f.close()
            body = []
            t = interpreter.tokenise(code)
            while True:
                p = interpreter.parse(t)
                if p is None:
                    break
                p = interpreter.macroexpand_r(p)
                if p is None:
                    continue
                tree = psilc(p)
                body.append(tree)
            tree = ast.Module(body)
            ast.fix_missing_locations(tree)
            codeobject = compile(tree, psilname, 'exec')

            fc = open(pycname, 'wb')
            fc.write(b'\0\0\0\0')
            py_compile.wr_long(fc, timestamp)
            marshal.dump(codeobject, fc)
            fc.flush()
            fc.seek(0, 0)
            fc.write(py_compile.MAGIC)
            fc.close()
            py_compile.set_creator_type(pycname)

            return builtins.__import__(fn, globals=globals)

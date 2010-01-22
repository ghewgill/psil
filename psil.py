import sys

import psil.interpreter

Interactive = True

a = 1
while a < len(sys.argv) and sys.argv[a].startswith("-"):
    if sys.argv[a] == "-c":
        psil.interpreter.Compile = True
    elif sys.argv[a] == "-e":
        a += 1
        psil.interpreter.psil(sys.argv[a])
        Interactive = False
    elif sys.argv[a] == "--test":
        import doctest
        a += 1
        if a < len(sys.argv):
            doctest.testfile(sys.argv[a])
        else:
            import psil.rt
            doctest.testmod(psil.compiler, optionflags=doctest.ELLIPSIS)
            doctest.testmod(psil.deparse, optionflags=doctest.ELLIPSIS)
            doctest.testmod(psil.interpreter, optionflags=doctest.ELLIPSIS)
            doctest.testmod(psil.rt, optionflags=doctest.ELLIPSIS)
            doctest.testmod(psil.symbol, optionflags=doctest.ELLIPSIS)
            doctest.testfile("psil.test", optionflags=doctest.ELLIPSIS)
            doctest.testfile("integ.test", optionflags=doctest.ELLIPSIS)
        sys.exit(0)
    a += 1

if a < len(sys.argv):
    # TODO: command line args to script
    psil.interpreter.include(sys.argv[a])
elif Interactive:
    from psil.interpreter import Globals, rep
    Globals.symbols["quit"] = lambda: sys.exit(0)
    import traceback
    print("PSIL interactive mode")
    print("Use (quit) to exit")
    try:
        import readline
    except ImportError:
        print("NOTE: readline module not available, line editing disabled")
        pass
    while True:
        try:
            s = input("> ")
        except EOFError:
            print()
            break
        try:
            rep(s)
        except SystemExit:
            raise
        except:
            traceback.print_exc()

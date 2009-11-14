import sys

from psil.interpreter import psil
import psil.interpreter

Interactive = True

a = 1
while a < len(sys.argv) and sys.argv[a].startswith("-"):
    if sys.argv[a] == "-c":
        psil.interpreter.Compile = True
    elif sys.argv[a] == "-e":
        a += 1
        psil(sys.argv[a])
        Interactive = False
    elif sys.argv[a] == "--test":
        import doctest
        a += 1
        if a < len(sys.argv):
            doctest.testfile(sys.argv[a])
        else:
            doctest.testmod(psil.interpreter, optionflags=doctest.ELLIPSIS)
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
    try:
        import readline
    except ImportError:
        pass
    import traceback
    print("PSIL interactive mode")
    print("Use (quit) to exit")
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

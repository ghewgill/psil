# Psil - Python S-expression Intermediate Language
Greg Hewgill  
<http://hewgill.com>

Psil is a Lisp family language designed for close integration with Python.

## Requirements

Psil requires Python 3.1 or later.

## Usage

To run a REPL (interactive read-eval-print-loop):

    $ python3.1 psil.py
    PSIL interactive mode
    Use (quit) to exit
    > 

To run a Psil script in a file:

    $ python3.1 psil.py hello.psil
    hello world

    or (on Unix-like systems):

    $ ./hello.psil
    hello world

To run Psil code from within Python:

    #!/usr/bin/env python3.1

    from psil.interpreter import psil

    square = psil("""
        (lambda (x)
            (* x x))
    """)

    print(square(5))

A slightly more advanced example where the `glob=globals()` is needed so that
the Psil code can see back into the Python module for the `fact` function:

    #!/usr/bin/env python3.1

    from psil.interpreter import psil

    fact = psil("""
        (lambda (x)
          (if (== x 0)
              1
              (* x (fact (- x 1)))))
    """, glob=globals())

    print(fact(5))

The `psil.test` file is a doctest module with many examples including macros.
To run the tests:

    $ python3.1 psil.py --test

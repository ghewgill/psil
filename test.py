from psil import psil

fact = psil("""
    (lambda (x)
      (if (== x 1)
          1
          (* x (fact (- x 1)))))""", glob = globals())

print fact(5)

sq = lambda x: x * x
print psil("(sq 5)", glob = globals())
foo = psil("(lambda (x) (sq x))", glob = globals())
print foo(4)

print psil("(import os) (getattr os \"name\")")

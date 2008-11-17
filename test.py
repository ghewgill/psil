from psil import psil

fact = psil("""
    (lambda (x)
      (if (= x 1)
          1
          (* x (fact (- x 1)))))""")

print psil("(import 'os) (getattr os \"name\")")

print fact(5)

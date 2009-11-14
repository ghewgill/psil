class Symbol(object):
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return "<%s>" % self.name
    names = {}
    gensym_counter = 0
    @staticmethod
    def new(name):
        if name in Symbol.names:
            return Symbol.names[name]
        s = Symbol(name)
        Symbol.names[name] = s
        return s
    @staticmethod
    def gensym():
        Symbol.gensym_counter += 1
        return Symbol.new("_g_%d" % Symbol.gensym_counter)

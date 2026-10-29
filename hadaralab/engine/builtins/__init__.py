"""Registry of built-in functions.

Every builtin has the signature  f(interp, args, nargout)  and returns
None (no output), a single value, or a Multi(...) of several values.
"""

BUILTINS = {}
HELP = {}     # name -> (signature, English description, Arabic description, category)


def builtin(*names, sig=None, en="", ar="", cat="General"):
    def deco(f):
        for n in names:
            BUILTINS[n] = f
        HELP[names[0]] = (sig or f"{names[0]}(...)", en, ar, cat)
        return f
    return deco


from . import core, control, plotting  # noqa: E402,F401  (registers functions)

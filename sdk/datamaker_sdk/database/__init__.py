from .database import RedshiftUtils,AthenaUtils
from .magics import RedshiftMagics,AthenaMagics

global __redshift__
global __athena__
__redshift__ = None
__athena__ = None

def check_in_jupyter():
    try:
        get_ipython()
        return True
    except NameError:
        return False

def get_redshift():
    global __redshift__
    if __redshift__ == None:
        __redshift__ = RedshiftUtils()
        if check_in_jupyter():
            ip = get_ipython()
            magics = RedshiftMagics(ip, __redshift__)
            ip.register_magics(magics)

    return __redshift__


def get_athena():
    global __athena__
    if __athena__ == None:
        __athena__ = AthenaUtils()
        if check_in_jupyter():
            ip = get_ipython()
            magics = AthenaMagics(ip, __athena__)
            ip.register_magics(magics)
    return __athena__

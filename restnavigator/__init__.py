__version__ = '1.0'

try:
    from .halnav import Navigator  # NOQA
except ImportError:
    # for setup.py and docs
    pass

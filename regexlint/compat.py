try:
    from StringIO import StringIO # Can't pickle cStringIO
except ImportError:
    from io import StringIO

def iteritems(d):
    if hasattr(d, 'iteritems'):
        return d.iteritems()
    else:
        return d.items()

def tobytes(s):
    if isinstance(s, type(u'')):
        s = bytes(s, 'latin-1')
    return s

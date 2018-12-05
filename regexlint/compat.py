def tobytes(s):
    if isinstance(s, type(u'')):
        s = bytes(s, 'latin-1')
    return s

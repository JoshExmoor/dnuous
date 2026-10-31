def synchsafe2dec(string):
    """
    Convert a 4 byte string encoded with the synchsafe scheme into a C{int}
    """
    # chop our list of bytes into a list of bits
    bitlist = []
    for byte in bytearray(string):
        bitlist += dec2bin(byte, 8)
    bitlist = synchsafe2bin(bitlist)
    x = bin2dec(bitlist)
    return x

def dec2synchsafe(xx):
    """
    Convert an C{int} into a 4 byte string encoded with the synchsafe scheme
    """

    #bin2byte(bin2synchsafe(dec2bin(len(data), 28)))
    xx = bin2byte(bin2synchsafe(dec2bin(xx, 28)))
    assert len(xx) == 4
    return xx


def synchsafe2bin(x):
    assert len(x) == 32
    out = []
    c = 0
    while len(x) > 0:
        c += 1
        y = x.pop()
        if c == 8:
            c = 0
        else:
            out.append(y)
    out.reverse()
    assert len(out) == 28
    return out

def byte2bin(y, p=0):
    res2 = []
    for x in bytearray(y):
        res = []
        while x > 0:
            res.append(x & 1)
            x = x >> 1
        if p > 0:
            res.extend([0] * (p - len(res)))
        res.reverse()
        res2.extend(res)
    return res2

def bin2byte(x):
    i = 0
    out = []
    x.reverse()
    b = 1
    ttl = 0
    for y in x:
        i += 1
        ttl += y * b
        b *= 2
        if i == 8:
            i = 0
            out.append(ttl)
            b = 1
            ttl = 0
    if b > 1:
        out.append(ttl)
    out.reverse()
    return bytes(out)

def bin2dec(x):
    x.reverse()
    b = 1
    ttl = 0
    for y in x:
        ttl += y * b
        b *= 2
    return ttl

def dec2bin(x, p=0):
    res = []
    while x > 0:
        res.append(x & 1)
        x = x >> 1
    if p > 0:
        res.extend([0] * (p - len(res)))
    res.reverse()
    return res

def bin2synchsafe(x):
    assert len(x) == 28
    x.reverse()
    out = []
    c = 0
    while len(x) > 0:
        c += 1
        if c == 1:
            out.append(0)
        y = x.pop()
        out.append(y)
        if c == 7:
            c = 0
    return out

def unsynchstr(data):
    lastfound = -1
    while 1:
        lastfound = data.find(b'\xff', lastfound + 1)
        if lastfound == -1:
            break
        if (lastfound + 1) == len(data):
            data = data + b'\x00'
        elif (data[lastfound+1] & 0xe0) == 0xe0 or data[lastfound+1] == 0:
            data = data[:lastfound+1] + b'\x00' + data[lastfound+1:]

    return data

def deunsynchstr(data):
    return data.replace(b'\xff\x00', b'\xff')

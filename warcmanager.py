# Copyright (c) 2013 David Bern


import zlib

from twisted.web.client import _URI

from hanzo.warctools import WarcRecord
from hanzo.httptools import RequestMessage, ResponseMessage

def dump(record, content=True):
    """ Dumps a warctools WarcRecord to a string """
    s = 'Headers:\n'
    for (h, v) in record.headers:
        s += '\t%s:%s\n' % (h, v)
    if content and record.content:
        s += 'Content Headers:\n'
        content_type, content_body = record.content
        s += '\t %s: %s\n' % (record.CONTENT_TYPE, content_type)
        s += '\t %s: %s\n' % (record.CONTENT_LENGTH, len(content_body))
        s += 'Content:\n'
        ln = min(2048, len(content_body))
        s += content_body[:ln]
        if ln < len(content_body):
            s += '\t...\n'
    else:
        s += 'Content: none\n\n'
    if record.errors:
        print 'Errors:'
        for e in record.errors:
            s += '\t%s\n' % str(e)
    return s

class MetaRecordInfo(object):
    """
    Stores information needed to retrieve a WARC Record
    This functions similar to a CDX entry
    """
    def __init__(self, uri, offset, rtype, filename):
        self.uri = uri
        self.offset = offset
        self.rtype = rtype
        self.filename = filename
        
    def uriEquals(self, uri, ignoreScheme=False):
        self_uri = _URI.fromBytes(self.uri)
        comp_uri = _URI.fromBytes(uri)
        if ignoreScheme:
            self_uri.scheme = comp_uri.scheme = None
        return self_uri.toBytes() == comp_uri.toBytes()
        

class WarcReplayHandler:
    metarecordinfo = MetaRecordInfo
    
    def __init__(self):
        self.clear()
        
    def clear(self):
        self.metaRecords = []
        self.responseMetaRecords = []
    
    @staticmethod
    def loadWarcFileRecords(name):
        """ Generator function for records from the file 'name' """
        f = WarcRecord.open_archive(name, gzip="auto")
        for (offset, r, err) in f.read_records(limit=None):
            if err:
                print "warc errors at %s:%d" % (name, offset or 0)
                for e in err:
                    print '\t', e
            if r:
                yield (r, offset)
        f.close()
        
    def loadWarcFile(self, name):
        for r, off in self.loadWarcFileRecords(name):
            i = self.metarecordinfo(r.url, off, r.type, name)
            if r.type == WarcRecord.RESPONSE:
                self.responseMetaRecords.append(i)
            self.metaRecords.append(i)
    
    def recordFromUri(self, uri):
        p = [m for m in self.responseMetaRecords if m.uriEquals(uri, ignoreScheme=True)]
        if len(p) < 1:
            return None
        return self.readRecord(p[0].filename, p[0].offset)
    
    @staticmethod
    def readRecord(filename, offset):
        w = WarcRecord.open_archive(filename, offset=offset)
        g = w.read_records(limit=1)
        r = g.next()[1]
        w.close()
        return r
    
    @staticmethod
    def extractPayload(record):
        m = ResponseMessage(RequestMessage())
        m.feed(record.content[1])
        m.close()
        b = m.get_body()
        
        z = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            b = z.decompress(b)
        except zlib.error:
            pass
        return b
# Copyright (c) 2013 David Bern


import argparse

from twisted.internet import reactor, protocol
from twisted.web.client import _URI

from hanzo.httptools import RequestMessage, ResponseMessage

from TwistedWebProxyServer import WebProxyServerProtocol
from warcmanager import WarcReplayHandler

def _copy_attrs(to, frum, attrs):
    map(lambda a: setattr(to, a, getattr(frum, a)), attrs)

class WarcReplayProtocol(WebProxyServerProtocol):
    def __init__(self, wrp, *args, **kwargs):
        WebProxyServerProtocol.__init__(self, *args, **kwargs)
        self._wrp = wrp
        
    @staticmethod
    def getRecordUri(request_uri, connect_uri):
        req_uri = _URI.fromBytes(request_uri)
        con_uri = _URI.fromBytes(connect_uri)
        # Remove default port from URL
        if con_uri.port == (80 if con_uri.scheme == 'http' else 443):
            con_uri.netloc = con_uri.host
        # Copy parameters from the relative req_uri to the con_uri
        _copy_attrs(con_uri, req_uri, ['path','params','query','fragment'])
        return con_uri.toBytes()
    
    def writeRecordToTransport(self, r, t):
        m = ResponseMessage(RequestMessage())
        m.feed(r.content[1])
        m.close()        
        b = m.get_body()
        
        # construct new headers
        new_headers = []
        old_headers = []
        for k, v in m.header.headers:
            if not k.lower() in ("connection", "content-length",
                                 "cache-control","accept-ranges", "etag",
                                 "last-modified", "transfer-encoding"):
                new_headers.append((k, v))
            old_headers.append(("X-Archive-Orig-%s" % k, v))
        
        new_headers.append(("Content-Length", "%d" % len(b)))
        new_headers.append(("Connection", "keep-alive"))
        # write the response
        t.write("%s %d %s\r\n" % (m.header.version,
                                  m.header.code,
                                  m.header.phrase))
        h = new_headers + old_headers
        t.write("\r\n".join(["%s: %s" % (k, v) for k, v in h]))
        t.write("\r\n\r\n")
        t.write(b)
    
    def requestParsed(self, request):
        record_uri = self.getRecordUri(request.uri, self.connect_uri)
        #print "requestParsed:", record_uri
        r = self._wrp.recordFromUri(record_uri)
        
        if r is not None:
            self.writeRecordToTransport(r, self.transport)
        else:
            print "404: ", record_uri
            resp = "URL not found in archives."
            self.transport.write("HTTP/1.0 404 Not Found\r\n"\
                                 "Connection: keep-alive\r\n"\
                                 "Content-Type: text/plain\r\n"\
                                 "Content-Length: %d\r\n\r\n"\
                                 "%s\r\n" % (len(resp)+2, resp))

class ReplayServerFactory(protocol.ServerFactory):
    protocol = WarcReplayProtocol
    
    def __init__(self, warcFiles=[], wrp=None):
        if wrp is not None:
            self.wrp = wrp
        else:
            self.wrp = WarcReplayHandler()
        for n in warcFiles:
            self.wrp.loadWarcFile(n)
    
    def buildProtocol(self, addr):
        p = self.protocol(self.wrp)
        p.factory = self
        return p

if __name__=='__main__':
    parser = argparse.ArgumentParser(
                             description='WarcReplay')
    parser.add_argument('-p', '--port', default='1080',
                        help='Port to run the proxy server on.')
    parser.add_argument('-w', '--warc', default='out.warc.gz',
                        help='WARC file to load')
    args = parser.parse_args()
    args.port = int(args.port)

    rsf = ReplayServerFactory(warcFiles=[args.warc])
    reactor.listenTCP(args.port, rsf)
    print "Proxy running on port", args.port
    reactor.run()

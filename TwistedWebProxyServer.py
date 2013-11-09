# Copyright (c) 2013 David Bern


# TODO: Merge with mitmtwisted.py

from twisted.internet import ssl
from twisted.web.client import _URI
from twisted.web._newclient import HTTPParser, ParseError, Request

class HTTPServerParser(HTTPParser):
    """
    Parses the headers and content length of an HTTP Request packet
    
    Should supply a finisher and override requestParsed
    Either call setBodyDecoder() or override rawDataReceived
    """
    @staticmethod
    def parseContentLength(connHeaders):
        """ Parses the content length from connHeaders """
        contentLengthHeaders = connHeaders.getRawHeaders('content-length')
        if contentLengthHeaders is not None and len(contentLengthHeaders) == 1:
            return int(contentLengthHeaders[0])
        else:
            raise ValueError(
                          "Too many content-length headers; request is invalid")
        return None
    
    def __init__(self, finisher):
        self.finisher = finisher
        self._bodyDecoder = None
        
    def setBodyDecoder(self, d):
        """ Will call bodyDecoder.dataReceived with raw body data """
        self._bodyDecoder = d
    
    def statusReceived(self, status):
        self.status = status
        
    def allHeadersReceived(self):
        parts = self.status.split(' ', 2)
        if len(parts) != 3:
            raise ParseError("wrong number of parts", self.status)
        method, request_uri, _ = parts
        
        if method == 'GET':
            self.contentLength = 0
        else:
            self.contentLength = self.parseContentLength(self.connHeaders)
            print "HTTPServerParser Header's Content length", self.contentLength
            # TOFIX: need to include a bodyProducer with the request
            # so that it knows to set a content-length
            self.switchToBodyMode(self._bodyDecoder)
        self.requestParsed(Request(method, request_uri, self.headers, None))
        if self.contentLength == 0:
            self._finished(self.clearLineBuffer())
            
    def _finished(self, rest):
        """ Called when the entire HTTP request + body is finished """
        self.finisher(rest)
    
    def requestParsed(self, request):
        """ Called with a request after it is parsed """
        pass

class WebProxyServerProtocol(HTTPParser):
    """
    Creates a web proxy for HTTP and HTTPS.
    
    
    allHeadersReceived -> resume -> (requestParsed -> dataFromServerParser)
    """
    certinfo = { 'key':'ca.key', 'cert':'ca.crt' }
    serverParser = HTTPServerParser
    
    @staticmethod
    def convertUriToRelative(uri):
        """ Converts an absolute URI to a relative one """
        parsedURI = _URI.fromBytes(uri)
        parsedURI.scheme = parsedURI.netloc = None
        return parsedURI.toBytes()
    
    @staticmethod
    def parseHttpStatus(status):
        """ Returns (method, connect_uri, http_version) """
        parts = status.split(' ', 2)
        if len(parts) != 3:
            raise ParseError("wrong number of parts", status)
        return parts
    
    @staticmethod
    def parseHostPort(addr, defaultPort=443):
        """ Parses 'host:port' into (host, port), given a defaultPort """
        port = defaultPort
        if b':' in addr:
            addr, port = addr.rsplit(b':')
            try:
                port = int(port)
            except ValueError:
                port = defaultPort
        return (addr, port)
    
    def __init__(self):
        self.useSSL = False
        self._rawDataBuffer = ''
        self._serverParser = None

    def statusReceived(self, status):
        self.status = status

    def rawDataReceived(self, data):
        """ Receives raw data from the proxied browser """
        #print "WebProxyServerProtocol rawDataReceived:", len(data), ":"
        if self._serverParser is not None:
            self._serverParser.dataReceived(data)
        else:
            # _rawDataBuffer is relayed when resume() is called
            self._rawDataBuffer += data
    
    def dataFromServerParser(self, data):
        """ Called after self._serverParser receives rawData """
        print "WebProxyServerProtocol dataFromServerParser:", len(data)
        
    def requestParsed(self, request):
        """ Called after self._serverParser parses a Request """
        print "  Request uri:",request.uri
        # Wikipedia does not accept absolute URIs:
        request.uri = self.convertUriToRelative(request.uri)
        # Check if any of the Connection connHeaders is 'close'
        conns = map(self._serverParser.connHeaders.getRawHeaders,
                    ['proxy-connection','connection'])
        #hasClose = any(map(lambda y: any(map(lambda a: a.lower() == 'close', y)), filter(lambda a: a or False, conns)))
        hasClose = any([x.lower() == 'close' for y in conns if y for x in y])
        # HACK!!! Force close a connection if there is content-length because
        # I haven't implemented anything to check the length of the POST data
        request.persistent = \
            False if hasClose or self._serverParser.contentLength != 0 \
            else True
    
    def createHttpServerParser(self):
        if self._serverParser is not None:
            self._serverParser.connectionLost(None)
            self._serverParser = None
        self._serverParser = self.serverParser(self.serverParserFinished)
        self._serverParser.rawDataReceived = self.dataFromServerParser
        self._serverParser.requestParsed = self.requestParsed
        self._serverParser.connectionMade() # initializes instance vars
        
    def serverParserFinished(self, rest):
        assert len(rest) == 0
        self.createHttpServerParser()
        
    def _allHeadersReceived(self):
        """
        Parses the HTTP headers and starts a connection to the sever.
        After the connection is made, all data should come in raw (body mode)
        and should be sent to an HTTPServerParser
        """
        self.transport.pauseProducing()
        method, connect_uri, _ = self.parseHttpStatus(self.status)
        
        self.useSSL = method == 'CONNECT'
        if self.useSSL:
            connect_uri = 'https://' + connect_uri
        if connect_uri[:4].lower() != 'http':
            # TOFIX: Should check for host in the headers and not just
            # the status line
            raise ParseError("HTTP status line did not have an absolute uri")
        
        self.connect_uri = connect_uri
        HTTPParser.allHeadersReceived(self) # self.switchToBodyMode(None)
        
    def allHeadersReceived(self):
        """
        Called when all HTTP Proxy headers have been received.
        Instantly calls resume(). Override for other functionality.
        """
        self._allHeadersReceived()
        self.resume()
    
    def resume(self):
        """
        Called when a connection to the remote server is established.
        Relay to the serverParser any extra data we received while waiting for
        the endpoint to connect, such as HTTP POST data
        """
        self.createHttpServerParser()
        
        if not self.useSSL:
            # Outer header data for the SSL connection should not be parsed
            # Since this is plain HTTP, these inject already parsed data
            # into the new _serverParser
            self._serverParser.status = self.status
            self._serverParser.headers = self.headers
            self._serverParser.connHeaders = self.connHeaders
            self._serverParser.allHeadersReceived()
        
        if len(self._rawDataBuffer) > 0:
            print "Spill-over data", len(self._rawDataBuffer)
            self._serverParser.dataReceived(self._rawDataBuffer)
            self._rawDataBuffer = ''
        
        if self.useSSL:
            self.transport.write('HTTP/1.0 200 Connection established\r\n\r\n')
            ctx = ssl.DefaultOpenSSLContextFactory(
                                    self.certinfo['key'], self.certinfo['cert'])
            self.transport.startTLS(ctx)
        self.transport.resumeProducing()

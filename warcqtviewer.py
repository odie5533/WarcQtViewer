import zlib
import sys, os

from PySide import QtCore, QtGui, QtUiTools, QtWebKit, QtNetwork
from PySide import QtXml # Necessary for py2exe @UnusedImport
import pkg_resources  # Necessary for py2exe. Used by warctools @UnusedImport

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

class WarcRecordItem(QtGui.QStandardItem):
    def __init__(self, rtype, offset, filename, uri=None):
        """
        Creates a generic representation of a WARC Record
        """
        self.rtype = rtype
        self.offset = offset
        self.filename = filename
        self.uri = uri
        super(WarcRecordItem, self).__init__()
    
    def toString(self):
        return self.rtype + (': ' + self.uri if self.uri else '')
        
    def data(self, i):
        if i == QtCore.Qt.DisplayRole:
            return self.toString()
        else:
            return super(WarcRecordItem, self).data(i)

class TwistedApp(QtCore.QObject):
    def __init__(self):
        QtCore.QObject.__init__(self, None)
        
        if getattr(sys, 'frozen', False) and getattr(sys, '_MEIPASS', False):
            basedir = sys._MEIPASS  # @UndefinedVariable
        else:
            try:
                basedir = os.path.dirname(__file__)
            except:
                basedir = ""
        # dynamically loads a Qt ui file without compiling it to python:
        loader = QtUiTools.QUiLoader()
        f = QtCore.QFile(os.path.join(basedir, "mainwindow.ui"))
        f.open(QtCore.QFile.ReadOnly)
        self.ui = loader.load(f)
        f.close()
        
        self.setProxy(1080)
        self.webView = None
        
        self.ui.actionOpen.triggered.connect(self.openAction)
        self.ui.actionExtract.triggered.connect(self.actionExtract)
        
        self.model = QtGui.QStandardItemModel()
        self.ui.listView.setModel(self.model)
        self.ui.listView.clicked.connect(self.showItem)
        self.ui.listView.doubleClicked.connect(self.previewItem)
        self.ui.listView.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        
        self.show = self.ui.show
        
    def setProxy(self, port):
        proxy = QtNetwork.QNetworkProxy()
        proxy.setType(QtNetwork.QNetworkProxy.HttpProxy)
        proxy.setHostName("127.0.0.1")
        proxy.setPort(port)
        QtNetwork.QNetworkProxy.setApplicationProxy(proxy)
        
    def loadWarcFile(self, name):
        """ Generator function for records from the file 'name' """
        f = WarcRecord.open_archive(name, gzip="auto")
        for (offset, r, err) in f.read_records(limit=None):
            print offset
            if err:
                print "warc errors at %s:%d" % (name, offset or 0)
                for e in err:
                    print '\t', e
            if r:
                yield WarcRecordItem(r.type, offset, name, r.url)
        f.close()
        
    def showItem(self, index):
        i = index.model().itemFromIndex(index) # QStandardItem
        r = self.recordFromWarcRecordItem(i)
        self.ui.plainTextEdit.setPlainText(dump(r))
        
    def previewItem(self, index):
        i = index.model().itemFromIndex(index) # QStandardItem
        self.showWebView()
        self.gotoUrl(i.uri)
        
    def openAction(self):
        """ Called when the Open button is pressed in the menu """
        f = QtGui.QFileDialog.getOpenFileName(None, "Open Image", "",
                                 "WARC files (*.warc *.warc.gz)\nAny files (*)")
        if not f or not f[0]: # f[0] might be ''
            return
        self.model.clear()
        for o in self.loadWarcFile(f[0]): # f is a tuple. first part is the name
            self.model.appendRow(o)
            
    @staticmethod
    def urlToFilename(url):
        n = url.rsplit('/', 1)[1]
        if '.' not in n:
            n += '.html'
        return n
    
    def recordFromWarcRecordItem(self, i):
        return self.readSingleWarcRecord(i.filename, i.offset)
    
    @staticmethod
    def readSingleWarcRecord(filename, offset):
        w = WarcRecord.open_archive(filename, offset=offset)
        g = w.read_records(limit=1)
        r = g.next()[1]
        w.close()
        return r

    def actionExtract(self):
        item = self.ui.listView.selectionModel().currentIndex()
        if not item or not item.model():
            print "No item selected for extraction"
            return
        i = item.model().itemFromIndex(item)
        
        if not i or i.rtype != WarcRecord.RESPONSE:
            print "Please select a response record to extract"
            return
        r = self.recordFromWarcRecordItem(i)
        m = ResponseMessage(RequestMessage())
        m.feed(r.content[1])
        m.close()
        ret = QtGui.QFileDialog.getSaveFileName(None,
                      "Save url response from " + r.url,
                      self.urlToFilename(r.url),
                      "")
        if not ret or not ret[0]:
            return
        b = m.get_body()
        
        z = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            b = z.decompress(b)
        except zlib.error:
            pass
        
        f = open(ret[0], 'wb')
        f.write(b)
        f.close()
        
        
    def showWebView(self):
        if self.webView is None:
            self.webView = QtWebKit.QWebView(self.ui.splitter_right)
            self.ui.splitter_right.addWidget(self.webView)

    def gotoUrl(self, url):
        self.webView.load(QtCore.QUrl(url))

if __name__ == "__main__":
    # Thanks to https://groups.google.com/forum/#!msg/pyinstaller/fbl5XOOSAtk/zstUlkcHIN4J
    # This stuff is required for the PyInstaller exe to work.
    from twisted.internet import reactor  # @UnusedImport
    del sys.modules['twisted.internet.reactor']
    #
    
    app = QtGui.QApplication(sys.argv)
    
    import qt4reactor
    qt4reactor.install()

    myapp = TwistedApp()
    myapp.show()
    
    sys.exit(app.exec_())
    #reactor.runReturn()

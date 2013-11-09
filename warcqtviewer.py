import zlib
import sys, os

from PySide import QtCore, QtGui, QtUiTools, QtWebKit, QtNetwork
from PySide import QtXml # Necessary for py2exe @UnusedImport
import pkg_resources  # Necessary for py2exe. Used by warctools @UnusedImport

from hanzo.warctools import WarcRecord
from hanzo.httptools import RequestMessage, ResponseMessage

from warcmanager import MetaRecordInfo, WarcReplayHandler, dump
from warcreplay import ReplayServerFactory

class WarcRecordItem(QtGui.QStandardItem, MetaRecordInfo):
    def __init__(self, *args, **kwargs):
        """
        Creates a generic representation of a WARC Record
        """
        MetaRecordInfo.__init__(self, *args, **kwargs)
        QtGui.QStandardItem.__init__(self)
    
    def toString(self):
        return self.rtype + (': ' + self.uri if self.uri else '')
        
    def data(self, i):
        if i == QtCore.Qt.DisplayRole:
            return self.toString()
        else:
            return QtGui.QStandardItem.data(self, i)

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
        
        self.wrp = WarcReplayHandler()
        self.wrp.metarecordinfo = WarcRecordItem
        
        self.rsf = ReplayServerFactory(wrp=self.wrp)
        reactor.listenTCP(1080, self.rsf)
        print reactor
        
    def setProxy(self, port):
        proxy = QtNetwork.QNetworkProxy()
        proxy.setType(QtNetwork.QNetworkProxy.HttpProxy)
        proxy.setHostName("127.0.0.1")
        proxy.setPort(port)
        QtNetwork.QNetworkProxy.setApplicationProxy(proxy)
        
    def showItem(self, index):
        i = index.model().itemFromIndex(index) # QStandardItem
        r = self.wrp.readRecord(i.filename, i.offset)
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
        self.wrp.loadWarcFile(f[0])
        for o in self.wrp.metaRecords: # f is a tuple. first part is the name
            self.model.appendRow(o)
            
    @staticmethod
    def urlToFilename(url):
        n = url.rsplit('/', 1)[1]
        if '.' not in n:
            n += '.html'
        return n

    def actionExtract(self):
        item = self.ui.listView.selectionModel().currentIndex()
        if not item or not item.model():
            print "No item selected for extraction"
            return
        i = item.model().itemFromIndex(item)
        
        if not i or i.rtype != WarcRecord.RESPONSE:
            print "Please select a response record to extract"
            return
        r = self.wrp.readRecord(i.filename, i.offset)
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
    del sys.modules['twisted.internet.reactor']
    
    app = QtGui.QApplication(sys.argv)
    
    import qt4reactor
    qt4reactor.install()
    
    from twisted.internet import reactor

    myapp = TwistedApp()
    myapp.show()
    
    sys.exit(app.exec_())
    #reactor.run()

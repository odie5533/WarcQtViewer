import zlib
import sys, os

from PySide import QtCore, QtGui, QtUiTools, QtWebKit, QtNetwork
from PySide import QtXml # Necessary for py2exe @UnusedImport
import pkg_resources  # Necessary for py2exe. Used by warctools @UnusedImport

from hanzo.warctools import WarcRecord
from hanzo.httptools import RequestMessage, ResponseMessage

class WarcRecordItem(QtGui.QStandardItem):
    def __init__(self, record):
        self.record = record
        super(WarcRecordItem, self).__init__()
    
    def toString(self):
        s = self.record.type
        if self.record.url:
            s += ': ' + self.record.url
        return s
    
    def dump(self, content=True):
        s = 'Headers:\n'
        for (h, v) in self.record.headers:
            s += '\t%s:%s\n' % (h, v)
        if content and self.record.content:
            s += 'Content Headers:\n'
            content_type, content_body = self.record.content
            s += '\t %s: %s\n' % (self.record.CONTENT_TYPE, content_type)
            s += '\t %s: %s\n' % (self.record.CONTENT_LENGTH, len(content_body))
            s += 'Content:\n'
            ln = min(2048, len(content_body))
            s += content_body[:ln]
            if ln < len(content_body):
                s += '\t...\n'
        else:
            s += 'Content: none\n\n'
        if self.record.errors:
            print 'Errors:'
            for e in self.record.errors:
                s += '\t%s\n' % str(e)
        return s
        
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
        for (offset, record, err) in f.read_records(limit=None):
            print offset
            if err:
                print "warc errors at %s:%d" % (name, offset or 0)
                for e in err:
                    print '\t', e
            if record:
                yield WarcRecordItem(record)
        f.close()
        
    def showItem(self, index):
        i = index.model().itemFromIndex(index) # QStandardItem
        self.ui.plainTextEdit.setPlainText(i.dump())
        
    def previewItem(self, index):
        i = index.model().itemFromIndex(index) # QStandardItem
        self.showWebView()
        self.gotoUrl(i.record.url)
        
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
            
    def actionExtract(self):
        i = self.ui.listView.selectionModel().currentIndex()
        if not i or not i.model():
            print "No item selected for extraction"
            return
        it = i.model().itemFromIndex(i)
        
        r = it.record
        if not r or r.type != WarcRecord.RESPONSE:
            print "Please select a response record to extract"
            return
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
    import sys
    app = QtGui.QApplication(sys.argv)

    myapp = TwistedApp()
    myapp.show()

    app.exec_()

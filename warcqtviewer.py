# Copyright (c) 2013 David Bern


import sys
import os

from PySide import QtCore, QtGui, QtUiTools, QtWebKit, QtNetwork
from PySide import QtXml # Necessary for py2exe @UnusedImport
import pkg_resources  # Necessary for py2exe. Used by warctools @UnusedImport

from warcreplay.warcmanager import MetaRecordInfo, WarcReplayHandler, dump
from warcreplay.warcreplay import ReplayServerFactory


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
        
        port = 1080
        
        # dynamically loads a Qt ui file without compiling it to python:
        loader = QtUiTools.QUiLoader()
        f = QtCore.QFile(os.path.join(self.getBaseDir(), "mainwindow.ui"))
        f.open(QtCore.QFile.ReadOnly)
        self.ui = loader.load(f)
        assert isinstance(self.ui, QtGui.QMainWindow)
        f.close()

        self.webViewShowing = False
        
        self.webView = self.createWebView(port)
        
        self.ui.actionOpen.triggered.connect(self.openAction)
        self.ui.actionExtract.triggered.connect(self.actionExtract)
        self.ui.actionClear.triggered.connect(self.actionClear)
        
        self.model = QtGui.QStandardItemModel()
        self.ui.listView.setModel(self.model)
        self.ui.listView.clicked.connect(self.showItem)
        self.ui.listView.doubleClicked.connect(self.previewItem)
        self.ui.listView.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        
        self.show = self.ui.show
        
        self.wrp = WarcReplayHandler()
        self.wrp.metarecordinfo = WarcRecordItem
        
        self.rsf = ReplayServerFactory(wrp=self.wrp)
        reactor.listenTCP(port, self.rsf)
        
    @staticmethod
    def getBaseDir():
        """
        Basedir changes if the application is running from a PyInstaller onefile
        """
        if getattr(sys, 'frozen', False) and getattr(sys, '_MEIPASS', False):
            return sys._MEIPASS  # @UndefinedVariable
        else:
            try:
                return os.path.dirname(__file__)
            except:
                return ""
            
    def createWebView(self, port=1080):
        """
        This webView ignores all SSL errors
        :rtype : QtWebKit.QWebView
        """
        w = QtWebKit.QWebView()
        nam = w.page().networkAccessManager()
        assert isinstance(nam, QtNetwork.QNetworkAccessManager)
        proxy = QtNetwork.QNetworkProxy()
        proxy.setType(QtNetwork.QNetworkProxy.HttpProxy)
        proxy.setHostName("127.0.0.1")
        proxy.setPort(port)
        nam.setProxy(proxy)
        nam.sslErrors.connect(self.sslErrorHandler)
        return w

    @staticmethod
    def sslErrorHandler(reply, _):
        """
        :type reply: QtNetwork.QNetworkReply
        """
        reply.ignoreSslErrors()
        
    def showItem(self, index):
        """
        Called when an item is single-clicked
        :type index: QtCore.QModelIndex
        """
        i = index.model().itemFromIndex(index)
        """:type : WarcRecordItem"""
        r = self.wrp.readRecord(i.filename, i.offset)
        self.ui.plainTextEdit.setPlainText(dump(r))

    def previewItem(self, index):
        """
        Called when an item is double-clicked
        :type index: QtCore.QModelIndex
        """
        i = index.model().itemFromIndex(index)
        """:type : WarcRecordItem"""
        self.showWebView()
        self.gotoUrl(i.uri)
    
    def openAction(self):
        """ Called when the Open button is pressed in the menu """
        filt = "WARC files (*.warc *.warc.gz)\nAny files (*)"
        f, _ = QtGui.QFileDialog.getOpenFileName(None, "Open WARC", "", filt)
        if not f:
            return
        self.model.clear()
        self.wrp.loadWarcFile(f)
        map(self.model.appendRow, self.wrp.metaRecords)
            
    def actionClear(self):
        self.model.clear()
        self.wrp.clear()
            
    @staticmethod
    def urlToFilename(url):
        """
        Creates a filename of sorts from a given url
        :type url: str
        :rtype: str
        """
        n = url.rsplit('/', 1)[1]
        if '.' not in n:
            n += '.html'
        return n

    def actionExtract(self):
        """ Called when the Extract button is pressed in the menu """
        item = self.ui.listView.selectionModel().currentIndex()
        if not item or not item.model():
            print "No item selected for extraction"
            return
        i = item.model().itemFromIndex(item)
        """:type : WarcRecordItem"""
        
        if not i or i.rtype != 'response':
            print "Please select a response record to extract"
            return
        title = "Save url response from " + i.uri
        f, _ = QtGui.QFileDialog.getSaveFileName(None, title,
                                                 self.urlToFilename(i.uri),
                                                 "")
        if not f:
            return
        
        b = self.wrp.extractPayload(self.wrp.readRecord(i.filename, i.offset))
        f = open(f, 'wb')
        f.write(b)
        f.close()
        
    def showWebView(self):
        if not self.webViewShowing:
            self.ui.splitter_right.addWidget(self.webView)

    def gotoUrl(self, url):
        self.webView.load(QtCore.QUrl(url))

if __name__ == "__main__":
    # Thanks to
    # https://groups.google.com/forum/#!msg/pyinstaller/fbl5XOOSAtk/zstUlkcHIN4J
    # This is required for the PyInstaller exe to work.
    del sys.modules['twisted.internet.reactor']
    
    app = QtGui.QApplication(sys.argv)
    
    import qt4reactor
    qt4reactor.install()
    
    from twisted.internet import reactor

    myapp = TwistedApp()
    myapp.show()
    
    sys.exit(app.exec_())
    #reactor.run()

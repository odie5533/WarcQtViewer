# -*- mode: python -*-
a = Analysis(['warcqtviewer.py'])
a.binaries.append(('mainwindow.ui', 'mainwindow.ui', 'BINARY'))
for d in a.datas:
    if 'pyconfig' in d[0]: 
        a.datas.remove(d)
        break
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='WarcQtViewer.exe',
          debug=False,
          strip=None,
          upx=False,
          console=False )
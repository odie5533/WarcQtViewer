# -*- mode: python -*-
a = Analysis(['warcqtviewer.py'])
a.binaries.append(('mainwindow.ui', 'mainwindow.ui', 'DATA'))
for d in range(len(a.binaries)):
    if a.binaries[d][0].lower() == 'ssleay32.dll':
        print a.binaries[d]
        a.binaries[d] = ('ssleay32.dll', 'C:\\\OpenSSL-Win32\\ssleay32.dll', 'BINARY')
    if a.binaries[d][0].lower() == 'libeay32.dll':
        print a.binaries[d]
        a.binaries[d] = ('libeay32.dll', 'C:\\OpenSSL-Win32\\libeay32.dll', 'BINARY')
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
          console=True )
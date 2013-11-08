from distutils.core import setup
import py2exe

setup(
    name = "WarcQtViewer",
    windows = [
        {
            'script':'pyqt.py'
        },
    ],
    data_files= [ "mainwindow.ui"],
    options = {
        "py2exe":{
            "compressed":1,
            "optimize":2,
            "dll_excludes":["MSVCP90.dll"]
        }
    }
)

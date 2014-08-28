#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import os
import tempfile

from PySide import QtGui
import pygments
from pygments.formatter import Formatter

from datadialogs import BaseDialog


def hex2QColor(c):
    r=int(c[0:2],16)
    g=int(c[2:4],16)
    b=int(c[4:6],16)
    return QtGui.QColor(r,g,b)    


class QFormatter(Formatter):
    
    def __init__(self):

        Formatter.__init__(self, style='tango')
        self.data=[]
        
        self.styles={}
        for token, style in self.style:
            qtf=QtGui.QTextCharFormat()

            if style['color']:
                qtf.setForeground(hex2QColor(style['color'])) 
            if style['bgcolor']:
                qtf.setBackground(hex2QColor(style['bgcolor'])) 
            if style['bold']:
                qtf.setFontWeight(QtGui.QFont.Bold)
            if style['italic']:
                qtf.setFontItalic(True)
            if style['underline']:
                qtf.setFontUnderline(True)
            self.styles[str(token)] = qtf
    
    def format(self, tokensource, outfile):
        global styles
        self.data=[]
        for ttype, value in tokensource:
            l=len(value)
            t=str(ttype)                
            self.data.extend([self.styles[t],]*l)


class Highlighter(QtGui.QSyntaxHighlighter):

    def __init__(self, parent):

        QtGui.QSyntaxHighlighter.__init__(self, parent)

        self.formatter=QFormatter()
        self.lexer = pygments.lexers.PythonLexer()
        
    def highlightBlock(self, text):
        """
        Takes a block and applies format to the document. 
        """
        
        text=unicode(self.document().toPlainText())+'\n'
        pygments.highlight(text, self.lexer, self.formatter)
        p = self.currentBlock().position()
        for i in range(len(unicode(text))):
            try:
                self.setFormat(i, 1, self.formatter.data[p+i])
            except IndexError:
                pass

class ScriptDialog(BaseDialog):
    """Dialog to plot arbitrary NeXus data in one or two dimensions"""
 
    def __init__(self, file_name=None, parent=None):

        super(ScriptDialog, self).__init__(parent)
 
        layout = QtGui.QVBoxLayout()
        self.text_box = QtGui.QPlainTextEdit()
        self.text_box.setFont(QtGui.QFont('Courier'))
        self.file_name = file_name
        from consoleapp import _nexpy_dir
        self.default_directory = os.path.join(_nexpy_dir, 'scripts')
        self.text_box.setMinimumWidth(700)
        self.text_box.setMinimumHeight(600)
        layout.addWidget(self.text_box)
        
        run_button = QtGui.QPushButton('Run Script')
        run_button.clicked.connect(self.run_script)
        self.argument_box = QtGui.QLineEdit()
        self.argument_box.setMinimumWidth(200)
        save_button = QtGui.QPushButton('Save')
        save_button.clicked.connect(self.save_script)
        save_as_button = QtGui.QPushButton('Save as...')
        save_as_button.clicked.connect(self.save_script_as)
        self.delete_button = QtGui.QPushButton('Delete')
        self.delete_button.clicked.connect(self.delete_script)
        close_button = QtGui.QPushButton('Close Window')
        close_button.clicked.connect(self.accept)
        button_layout = QtGui.QHBoxLayout()
        button_layout.addWidget(run_button)
        button_layout.addWidget(self.argument_box)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(save_as_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        if self.file_name:
            with open(self.file_name, 'r') as f:
                text = f.read()
            self.text_box.setPlainText(text)
            self.setWindowTitle("Script Editor: "+self.file_name)
        else:
            self.delete_button.setVisible(False)
            self.setWindowTitle("Script Editor")
        self.hl = Highlighter(self.text_box.document())
        
    def get_text(self):
        return self.text_box.document().toPlainText()+'\n'

    def run_script(self):
        from consoleapp import _mainwindow
        text = self.get_text()
        if 'sys.argv' in text:
            file_name = tempfile.mkstemp('.py')[1]
            with open(file_name, 'w') as f:
                f.write(self.get_text())
            args = self.argument_box.text()
            _mainwindow.console.execute('run -i %s %s' % (file_name, args))
            os.remove(file_name)
        else:
            _mainwindow.console.execute(self.get_text())

    def save_script(self):
        if self.file_name:
            with open(self.file_name, 'w') as f:
                f.write(self.get_text())
        else:
            self.save_script_as()

    def save_script_as(self):
        file_filter = ';;'.join(("Python Files (*.py)", "Any Files (*.* *)"))
        file_name, _ = QtGui.QFileDialog().getSaveFileName(self,
                            "Choose a Filename", dir=self.default_directory,
                            filter=file_filter)
        if file_name:
            with open(file_name, 'w') as f:
                f.write(self.get_text())
            self.file_name = file_name
            self.setWindowTitle("Script Editor: "+self.file_name)
            from consoleapp import _mainwindow
            _mainwindow.add_script_action(self.file_name)
            self.delete_button.setVisible(True)

    def delete_script(self):
        if self.file_name:
            ret = self.confirm_action(
                      "Are you sure you want to delete '%s'?" % self.file_name,
                      "This cannot be reversed")
            if ret == QtGui.QMessageBox.Ok:
                os.remove(self.file_name)
                from consoleapp import _mainwindow
                _mainwindow.remove_script_action(self.file_name)
                self.accept()

    def accept(self):    
        super(ScriptDialog, self).accept()

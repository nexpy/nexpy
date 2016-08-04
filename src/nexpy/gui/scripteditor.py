#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six

import os
import sys
import tempfile
import pygments
from pygments.formatter import Formatter

from .pyqt import QtCore, QtGui, getSaveFileName

from .datadialogs import BaseDialog
from .utils import confirm_action


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
        
        text=six.text_type(self.document().toPlainText())+'\n'
        pygments.highlight(text, self.lexer, self.formatter)
        p = self.currentBlock().position()
        for i in range(len(six.text_type(text))):
            try:
                self.setFormat(i, 1, self.formatter.data[p+i])
            except IndexError:
                pass



class NXPlainTextEdit(QtGui.QPlainTextEdit):

    def __init__(self, parent):
        super(NXPlainTextEdit, self).__init__()
        self.setFont(QtGui.QFont('Courier'))
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)
        self.parent = parent
        self.blockCountChanged.connect(self.parent.update_line_numbers)

    def paintEvent(self, event):
        super(NXPlainTextEdit, self).paintEvent(event)
        self.parent.update_line_numbers(self.blockCount())

    def resizeEvent(self, event):
        super(NXPlainTextEdit, self).resizeEvent(event)
        self.parent.update_line_numbers(self.blockCount())

    @property
    def count(self):
        return self.blockCount()

    @property
    def line_height(self):
        return self.fontMetrics().height()

    @property
    def lines(self):
        return int(self.viewport().size().height() /
                   self.line_height)

       
class NXScriptWindow(QtGui.QDialog):

    def __init__(self, parent=None):
        super(NXScriptWindow, self).__init__(parent)
        layout = QtGui.QVBoxLayout()
        self.tabs = QtGui.QTabWidget(self)
        layout.addWidget(self.tabs)
        self.setLayout(layout)
        self.setWindowTitle('Script Editor')
        self.tabs.currentChanged.connect(self.update)

    def __repr__(self):
        return 'NXScriptWindow()'

    @property
    def editors(self):
        return [self.tabs.widget(idx) for idx in range(self.tabs.count())]

    def update(self):
        for editor in self.editors:
            editor.adjustSize()
        if self.tabs.count() == 0:
            self.setVisible(False)

    def closeEvent(self, event):
        self.close()
        event.accept()
        
    def close(self):
        for editor in self.editors:
            editor.close()
        self.setVisible(False)


class NXScriptEditor(QtGui.QWidget):
    """Dialog to plot arbitrary NeXus data in one or two dimensions"""
 
    def __init__(self, file_name=None, parent=None):

        if parent is None:
            from .consoleapp import _mainwindow
            self.mainwindow = _mainwindow
        else:
            self.mainwindow = parent
        self.window = self.mainwindow.editors

        QtGui.QWidget.__init__(self, parent=self.window.tabs)
 
        self.file_name = file_name
        self.default_directory = self.mainwindow.script_dir

        layout = QtGui.QVBoxLayout()
        self.text_layout = QtGui.QHBoxLayout()
        if sys.platform == 'darwin':
            self.number_box = QtGui.QLabel('1')
            self.number_box.setFont(QtGui.QFont('Courier'))
            self.number_box.setAlignment(QtCore.Qt.AlignTop | 
                                         QtCore.Qt.AlignRight)
            self.number_box.setStyleSheet("QLabel {padding: 1px 0}")
            self.text_layout.addWidget(self.number_box)
        self.text_box = NXPlainTextEdit(self)
        self.text_layout.addWidget(self.text_box)
        layout.addLayout(self.text_layout)
        
        run_button = QtGui.QPushButton('Run Script')
        run_button.clicked.connect(self.run_script)
        run_button.setAutoDefault(False)
        self.argument_box = QtGui.QLineEdit()
        self.argument_box.setMinimumWidth(200)
        save_button = QtGui.QPushButton('Save')
        save_button.clicked.connect(self.save_script)
        save_as_button = QtGui.QPushButton('Save as...')
        save_as_button.clicked.connect(self.save_script_as)
        self.delete_button = QtGui.QPushButton('Delete')
        self.delete_button.clicked.connect(self.delete_script)
        close_button = QtGui.QPushButton('Close Tab')
        close_button.clicked.connect(self.close)
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
            self.label = os.path.basename(self.file_name)
            with open(self.file_name, 'r') as f:
                text = f.read()
            self.text_box.setPlainText(text)
            self.window.tabs.addTab(self, self.label)
            self.update_line_numbers(self.text_box.count)
        else:
            self.label = 'Untitled %s' % (self.window.tabs.count()+1)
            self.delete_button.setVisible(False)
            self.window.tabs.addTab(self, self.label)
        self.index = self.window.tabs.indexOf(self)

        self.window.tabs.adjustSize()
        self.window.tabs.setCurrentWidget(self)

        self.hl = Highlighter(self.text_box.document())

    def __repr__(self):
        return 'NXScriptEditor(%s)' % self.label
        
    def get_text(self):
        return self.text_box.document().toPlainText()+'\n'

    def update_line_numbers(self, count):
        if sys.platform != 'darwin':
            return
        first_block = self.text_box.firstVisibleBlock()
        first_line = first_block.blockNumber() + 1
        lines = min(count - first_line + 1, 
                    int(self.text_box.viewport().size().height() /
                        self.text_box.line_height))
        self.number_box.setText('\n'.join([str(i) for i in 
                                           range(first_line, 
                                                 first_line+lines)]))
        if first_line > 1:
            self.number_box.setStyleSheet("QLabel {padding: 0}")
        else:
            self.number_box.setStyleSheet("QLabel {padding: 1px 0}")

    def run_script(self):
        text = self.get_text()
        if 'sys.argv' in text:
            file_name = tempfile.mkstemp('.py')[1]
            with open(file_name, 'w') as f:
                f.write(self.get_text())
            args = self.argument_box.text()
            self.mainwindow.console.execute('run -i %s %s' % (file_name, args))
            os.remove(file_name)
        else:
            self.mainwindow.console.execute(self.get_text())

    def save_script(self):
        if self.file_name:
            with open(self.file_name, 'w') as f:
                f.write(self.get_text())
        else:
            self.save_script_as()

    def save_script_as(self):
        file_filter = ';;'.join(("Python Files (*.py)", "Any Files (*.* *)"))
        file_name = getSaveFileName(self, "Choose a Filename", 
                                    self.default_directory, filter=file_filter)
        if file_name:
            with open(file_name, 'w') as f:
                f.write(self.get_text())
            self.file_name = file_name
            self.window.tabs.setTabText(self.index, os.path.basename(self.file_name))
            self.mainwindow.add_script_action(self.file_name)
            self.delete_button.setVisible(True)

    def delete_script(self):
        if self.file_name:
            ret = confirm_action(
                      "Are you sure you want to delete '%s'?" % self.file_name,
                      "This cannot be reversed")
            if ret == QtGui.QMessageBox.Ok:
                os.remove(self.file_name)
                self.mainwindow.remove_script_action(self.file_name)
                self.close()

    def close(self):
        self.window.tabs.removeTab(self.index)
        self.deleteLater()
        self.window.update()

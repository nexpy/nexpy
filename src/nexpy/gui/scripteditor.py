# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import os
import tempfile

import pygments
from pygments.formatter import Formatter

from .datadialogs import NXPanel, NXTab
from .pyqt import QtCore, QtGui, QtWidgets, getSaveFileName
from .utils import confirm_action, in_dark_mode
from .widgets import NXLineEdit, NXPushButton


def hex2QColor(c):
    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)
    return QtGui.QColor(r, g, b)


class NXFormatter(Formatter):

    def __init__(self):

        if in_dark_mode():
            super().__init__(style='monokai')
        else:
            super().__init__(style='tango')
        self.data = []
        self.styles = {}
        for token, style in self.style:
            qtf = QtGui.QTextCharFormat()
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

    def __repr__(self):
        return f"NXFormatter(style='{self.style_name}')"

    def format(self, tokensource, outfile):
        self.data = []
        for ttype, value in tokensource:
            v = len(value)
            t = str(ttype)
            self.data.extend([self.styles[t], ]*v)


class NXHighlighter(QtGui.QSyntaxHighlighter):

    def __init__(self, parent):

        super().__init__(parent)

        self.formatter = NXFormatter()
        self.lexer = pygments.lexers.PythonLexer()

    def highlightBlock(self, text):
        """
        Takes a block and applies format to the document.
        """

        text = str(self.document().toPlainText())+'\n'
        pygments.highlight(text, self.lexer, self.formatter)
        p = self.currentBlock().position()
        for i in range(len(str(text))):
            try:
                self.setFormat(i, 1, self.formatter.data[p+i])
            except IndexError:
                pass


class NXScrollBar(QtWidgets.QScrollBar):

    def sliderChange(self, change):
        if (self.signalsBlocked() and
                change == QtWidgets.QAbstractSlider.SliderValueChange):
            self.blockSignals(False)


class NXScriptTextEdit(QtWidgets.QPlainTextEdit):

    def __init__(self, slot=None, parent=None):
        super().__init__(parent)
        self.setFont(QtGui.QFont('Courier'))
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self.setWordWrapMode(QtGui.QTextOption.NoWrap)
        self.setTabStopWidth(4 * self.fontMetrics().width(' '))
        self.blockCountChanged.connect(parent.update_line_numbers)
        self.scrollbar = NXScrollBar(parent=self)
        self.setVerticalScrollBar(self.scrollbar)
        if slot:
            self.scrollbar.valueChanged.connect(slot)

    def __repr__(self):
        return 'NXScriptTextEdit()'

    @property
    def count(self):
        return self.blockCount()


class NXScriptWindow(NXPanel):

    def __init__(self, parent=None):
        super().__init__('Editor', title='Script Editor', close=False,
                         parent=parent)
        self.tab_class = NXScriptEditor

    def __repr__(self):
        return 'NXScriptWindow()'

    def activate(self, file_name):
        if file_name:
            label = os.path.basename(file_name)
        else:
            label = f'Untitled {self.count+1}'
        super().activate(label, file_name)
        if file_name:
            self.tab.default_directory = os.path.dirname(file_name)
        else:
            self.tab.default_directory = self.mainwindow.script_dir


class NXScriptEditor(NXTab):
    """Dialog to plot arbitrary NeXus data in one or two dimensions"""

    def __init__(self, label, file_name=None, parent=None):

        super().__init__(label, parent=parent)

        self.file_name = file_name

        self.number_box = QtWidgets.QPlainTextEdit('1')
        self.number_box.setFont(QtGui.QFont('Courier'))
        self.number_box.setFixedWidth(35)
        self.number_box.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self.number_box.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self.text_box = NXScriptTextEdit(slot=self.scroll_numbers, parent=self)
        self.text_layout = self.make_layout(self.number_box, self.text_box,
                                            align='justified')
        self.text_layout.setSpacing(0)

        run_button = NXPushButton('Run Script', self.run_script)
        self.argument_box = NXLineEdit(width=200)
        save_button = NXPushButton('Save', self.save_script)
        save_as_button = NXPushButton('Save as...', self.save_script_as)
        self.delete_button = NXPushButton('Delete', self.delete_script)
        close_button = NXPushButton('Close Tab', self.panel.close)
        button_layout = self.make_layout(run_button, self.argument_box,
                                         'stretch',
                                         save_button, save_as_button,
                                         self.delete_button, close_button)
        self.set_layout(self.text_layout, button_layout)

        if self.file_name:
            with open(self.file_name, 'r') as f:
                text = f.read()
            self.text_box.setPlainText(text)
            self.update_line_numbers()
        else:
            self.delete_button.setVisible(False)

        self.hl = NXHighlighter(self.text_box.document())

        self.text_box.setFocus()
        self.number_box.setFocusPolicy(QtCore.Qt.NoFocus)
        self.define_style()

    def define_style(self):
        if in_dark_mode():
            self.number_box.setStyleSheet('color: white; '
                                          'background-color: #444; '
                                          'padding: 0; margin: 0; border: 0')
            self.text_box.setStyleSheet('background-color: black')
        else:
            self.number_box.setStyleSheet('color: black; '
                                          'background-color: #eee; '
                                          'padding: 0; margin: 0; border: 0')
            self.text_box.setStyleSheet('background-color: white')
        self.highlighter = NXHighlighter(self.text_box.document())

    def get_text(self):
        text = self.text_box.document().toPlainText().strip()
        return text.replace('\t', '    ') + '\n'

    def update_line_numbers(self):
        count = self.text_box.count
        if count >= 1000:
            self.number_box.setWidth(40)
        self.number_box.setPlainText('\n'.join([str(i).rjust(len(str(count)))
                                                for i in range(1, count+1)]))
        self.scroll_numbers()

    def scroll_numbers(self):
        self.number_box.verticalScrollBar().setValue(
            self.text_box.verticalScrollBar().value())
        self.text_box.scrollbar.update()

    def run_script(self):
        text = self.get_text()
        if 'sys.argv' in text:
            file_name = tempfile.mkstemp('.py')[1]
            with open(file_name, 'w') as f:
                f.write(self.get_text())
            args = self.argument_box.text()
            self.mainwindow.console.execute(f'run -i {file_name} {args}')
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
        if self.file_name:
            default_name = self.file_name
        else:
            default_name = self.default_directory
        file_name = getSaveFileName(self, "Choose a Filename", default_name,
                                    filter=file_filter)
        if file_name:
            with open(file_name, 'w') as f:
                f.write(self.get_text())
            self.file_name = file_name
            self.tab_label = os.path.basename(self.file_name)
            self.mainwindow.add_script_action(self.file_name,
                                              self.mainwindow.script_menu)
            self.delete_button.setVisible(True)

    def delete_script(self):
        if self.file_name:
            if confirm_action(
                    f"Are you sure you want to delete '{self.file_name}'?",
                    "This cannot be reversed"):
                os.remove(self.file_name)
                self.mainwindow.remove_script_action(self.file_name)
                self.panel.close()

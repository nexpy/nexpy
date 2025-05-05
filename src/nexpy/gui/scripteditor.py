# -----------------------------------------------------------------------------
# Copyright (c) 2013-2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import tempfile
from pathlib import Path

import pygments
from pygments.formatter import Formatter

from .pyqt import QtCore, QtGui, QtWidgets, getSaveFileName
from .utils import confirm_action, in_dark_mode
from .widgets import NXLineEdit, NXPanel, NXPushButton, NXTab


def hex2QColor(c):
    """Convert a hex color code to a QColor."""
    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)
    return QtGui.QColor(r, g, b)


class NXFormatter(Formatter):

    def __init__(self):

        """Initialize the formatter for the syntax highlighter."""
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
        """
        Format a source of tokens into a list of styles.

        Parameters
        ----------
        tokensource : iterable
            An iterable of (token_type, token_value) pairs.
        outfile : file-like
            Ignored, but required by the Formatter API.

        Returns
        -------
        data : list
            A list of styles, one for each character in the source.
        """
        self.data = []
        for ttype, value in tokensource:
            v = len(value)
            t = str(ttype)
            self.data.extend([self.styles[t], ]*v)


class NXHighlighter(QtGui.QSyntaxHighlighter):

    def __init__(self, parent):

        """
        Initialize the syntax highlighter.

        Parameters
        ----------
        parent : QWidget
            The parent of the syntax highlighter.
        """
        super().__init__(parent)

        self.formatter = NXFormatter()
        self.lexer = pygments.lexers.PythonLexer()

    def highlightBlock(self, text):
        """
        Highlight the given block of text.

        The given text is the block of text which the syntax highlighter
        should highlight. The text is formatted according to the
        highlighting rules defined by the syntax highlighter.

        Parameters
        ----------
        text : str
            The block of text to be highlighted.
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
        """
        Reimplement QScrollBar.sliderChange to allow scrolling to be
        caught by a slot when the slider is moved.
        """
        if (self.signalsBlocked() and
                change == QtWidgets.QAbstractSlider.SliderValueChange):
            self.blockSignals(False)


class NXScriptTextEdit(QtWidgets.QPlainTextEdit):

    def __init__(self, slot=None, parent=None):
        """
        Initialize the script text editor.

        Parameters
        ----------
        slot : function, optional
            If given, connect the slot to the valueChanged signal of the
            vertical scrollbar.
        parent : QWidget, optional
            The parent of the script text editor.
        """
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
        """The number of blocks in the text box."""
        return self.blockCount()


class NXScriptWindow(NXPanel):

    def __init__(self, parent=None):
        """
        Initialize the script window.

        Parameters
        ----------
        parent : QWidget, optional
            The parent of the script window.
        """
        super().__init__('Editor', title='Script Editor', close=False,
                         parent=parent)
        self.tab_class = NXScriptEditor

    def __repr__(self):
        return 'NXScriptWindow()'

    def activate(self, file_name):
        """
        Activate a script window.

        Parameters
        ----------
        file_name : str, optional
            If given, open the file for editing. If not given, create a
            new empty script window.
        """
        if file_name:
            label = Path(file_name).name
        else:
            label = f'Untitled {self.count+1}'
        super().activate(label, file_name)
        if file_name:
            self.tab.default_directory = Path(file_name).parent
        else:
            self.tab.default_directory = self.mainwindow.script_dir


class NXScriptEditor(NXTab):
 
    def __init__(self, label, file_name=None, parent=None):

        """
        Initialize the script editor.

        Parameters
        ----------
        label : str
            The name of the tab.
        file_name : str, optional
            The name of the file to be edited. If given, open the file
            for editing. If not given, create a new empty script window.
        parent : QWidget, optional
            The parent of the script editor.
        """
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
        self.reload_button = NXPushButton('Reload', self.reload_script)
        self.delete_button = NXPushButton('Delete', self.delete_script)
        close_button = NXPushButton('Close Tab', self.panel.close)
        button_layout = self.make_layout(run_button, self.argument_box,
                                         'stretch',
                                         save_button, save_as_button,
                                         self.reload_button,
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
        """Modify the style when changing to light or dark mode."""
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
        """
        Return the text contained in the edit window.

        This method returns the text contained in the text box,
        replacing all tabs with 4 spaces and adding a newline at the
        end. This is suitable for writing to a file.
        """
        text = self.text_box.document().toPlainText().strip()
        return text.replace('\t', '    ') + '\n'

    def update_line_numbers(self):
        """
        Update the line numbers in the editor.

        This method updates the line numbers in the left column of the
        editor whenever the text is changed. The width of the line
        numbers is set to be wide enough to hold 3 or 4 digits,
        depending on the number of lines in the text.
        """
        count = self.text_box.count
        if count >= 1000:
            self.number_box.setWidth(40)
        self.number_box.setPlainText('\n'.join([str(i).rjust(len(str(count)))
                                                for i in range(1, count+1)]))
        self.scroll_numbers()

    def scroll_numbers(self):
        """
        Synchronize the scroll bar of the line numbers with the
        scroll bar of the text box.

        This method is called whenever the text box is scrolled.
        It sets the value of the line numbers scroll bar to the value
        of the text box scroll bar and updates the line numbers to
        ensure that the correct line numbers are displayed.
        """
        self.number_box.verticalScrollBar().setValue(
            self.text_box.verticalScrollBar().value())
        self.text_box.scrollbar.update()

    def run_script(self):
        """
        Run the script in the NeXpy console.

        This method runs the script in the edit window in the NeXpy
        console. If the script contains the string 'sys.argv', it
        is saved to a temporary file and the 'run' magic is used to
        run the script with the arguments given in the argument box.
        Otherwise, the script is executed directly in the NeXpy
        console.
        """
        text = self.get_text()
        if 'sys.argv' in text:
            file_name = tempfile.mkstemp('.py')[1]
            with open(file_name, 'w') as f:
                f.write(self.get_text())
            args = self.argument_box.text()
            self.mainwindow.console.execute(f'run -i {file_name} {args}')
            Path(file_name).unlink()
        else:
            self.mainwindow.console.execute(self.get_text())

    def save_script(self):
        """Save the script to a file."""
        if self.file_name:
            with open(self.file_name, 'w') as f:
                f.write(self.get_text())
        else:
            self.save_script_as()

    def save_script_as(self):
        """Save the script to a new file."""
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
            self.tab_label = Path(self.file_name).name
            self.mainwindow.add_script_action(self.file_name,
                                              self.mainwindow.script_menu)
            self.delete_button.setVisible(True)

    def reload_script(self):
        """Reload a script from a file.

        If the file has changed since it was last loaded, this will
        overwrite the current script with the new contents of the file.
        """
        if self.file_name:
            if confirm_action(
                    f"Are you sure you want to reload '{self.file_name}'?",
                    "This will overwrite the current script"):
                with open(self.file_name, 'r') as f:
                    text = f.read()
                self.text_box.setPlainText(text)
                self.update_line_numbers()

    def delete_script(self):
        """
        Delete a script from a file.

        If the file is currently open, this will delete it from the
        file system and close the script window. If the file is not
        currently open, this will delete it from the file system only.

        This method will ask for confirmation before taking any action.
        """
        if self.file_name:
            if confirm_action(
                    f"Are you sure you want to delete '{self.file_name}'?",
                    "This cannot be reversed"):
                Path(self.file_name).unlink()
                self.mainwindow.remove_script_action(self.file_name)
                self.panel.close()

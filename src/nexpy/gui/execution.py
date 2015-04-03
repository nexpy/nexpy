#!/usr/bin/env python 

from nexusformat.pyro.ssh import NeXPyroSSH
from PySide import QtGui, QtCore

def onClick(widget, function):
    QtCore.QObject.connect(widget,
                           QtCore.SIGNAL('clicked()'),
                           function)

class ExecManager:
    """
    There is one of these per NeXpy
    We use mgr=Manager
    """ 
    def __init__(self):
        self.task_id_unique = 0
        self.tasks = {}
        self.exec_hosts_recent = []
        self.exec_cmds_recent = []
     
    def newTask(self, host, command):
        self.task_id_unique += 1
        task = ExecTask(self.task_id_unique, host, command)
        self.tasks[self.task_id_unique] = task
        task.run()
        
    def terminate(self, task_id):
        task = self.tasks[task_id]
        print "KILLING", task
        task.terminate()
        del self.tasks[task_id]

    def finalize(self):
        for task_id in self.tasks:
            self.tasks[task_id].terminate()

class ExecTask:
    """
    A remote task tracked by the manager
    """
    def __init__(self, task_id, hostname, command):
        self.task_id = task_id
        self.hostname = hostname
        self.command = command
        self.status = "PROTO"
        self.user = "wozniak"
        self.ssh = None
    
    def __repr__(self):
        return "(%i) on %s: %s" % \
            (self.task_id,self.hostname,self.command)
            
    def run(self):
        self.ssh = NeXPyroSSH(self.user, self.hostname,
                              command=self.command)

    def terminate(self):
        self.ssh.terminate()

class ExecWindow(QtGui.QMainWindow):
 
    def __init__(self, mgr):
        super(ExecWindow, self).__init__()
        self.mgr = mgr

        self.outputViews = {}

        self.label = QtGui.QLabel(self)
        self.label.move(25,20)
        self.combobox = QtGui.QComboBox(self)
        self.combobox.move(25,50)
        self.combobox.SizeAdjustPolicy = \
            QtGui.QComboBox.AdjustToContents

        self.refresher = QtGui.QPushButton('&Refresh', self)
        self.refresher.move(25,75)
        onClick(self.refresher, self.refresh)
        self.outviewer = QtGui.QPushButton('Show &Output', self)
        self.outviewer.move(125,75)
        onClick(self.outviewer, self.outview)
        self.killer = QtGui.QPushButton('&Kill', self)
        self.killer.move(225,75)
        onClick(self.killer, self.kill_task)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.combobox)
        layout.addWidget(self.killer)
        self.setLayout(layout)
        self.setWindowTitle("Execution list")    
        self.setGeometry(100, 100, 1000, 150)
        self.refresh()
    
    def refresh(self):
        tasks = self.mgr.tasks
        count = len(tasks)
        self.label.setText("Tasks (%i):"%count)
        # Map combobox indices to task IDs
        self.comboboxMap = {}
        self.combobox.clear()
        idx = 0
        for task_id in tasks:
            task = tasks[task_id]
            done,exitcode = task.ssh.isDone()
            prefix = ""
            if done: prefix = "(exit:%i) "%exitcode
            text = prefix + repr(task)
            self.combobox.addItem(text)
            self.comboboxMap[idx] = task_id
            idx += 1
        self.combobox.adjustSize()
        self.show()
        self.raise_()
            
    def outview(self):
        idx = self.combobox.currentIndex()
        if idx < 0: return # combobox is empty
        task_id = self.comboboxMap[idx]
        if task_id in self.outputViews:
            outputView = self.outputViews[task_id]
        else:
            task = self.mgr.tasks[task_id]
            outputView = ExecOutput(task_id, task)
            self.outputViews[task_id] = outputView
        outputView.refresh()

    def kill_task(self):
        idx = self.combobox.currentIndex()
        if idx < 0: return # combobox is empty
        task_id = self.comboboxMap[idx]
        self.mgr.terminate(task_id)
        self.refresh()

class ExecOutput(QtGui.QMainWindow):
    def __init__(self, task_id, task):
        super(ExecOutput, self).__init__()
        self.task = task
        self.setWindowTitle("NeXpy: Output: (%i)"%task_id)
        self.setGeometry(100, 100, 800, 600)
        labelHost = QtGui.QLabel(self)
        # labelHost.move(25,25)
        labelHost.setGeometry(25,25,300,25)
        labelHost.setText("hostname: " + task.ssh.host)
        self.editor = QtGui.QTextEdit(self)
        self.editor.move(25,50)
        self.editor.setFixedWidth(750)
        self.editor.setFixedHeight(500)
        self.refresher = QtGui.QPushButton('&Refresh', self)
        self.refresher.move(25,560)
        onClick(self.refresher, self.refresh)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(labelHost)
        layout.addWidget(self.editor)
        self.setLayout(layout)

    def refresh(self):
        self.editor.setText(self.task.ssh.command)
        self.editor.append("-----------------------")
        text = self.task.ssh.getOutput()
        self.editor.append(text)
        self.show()
        self.raise_()

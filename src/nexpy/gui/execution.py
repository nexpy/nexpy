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
        self.label = QtGui.QLabel(self)
        self.label.move(25,20)
        self.combobox = QtGui.QComboBox(self)
        self.combobox.move(25,50)

        self.refresher = QtGui.QPushButton('&Refresh', self)
        self.refresher.move(25,75)
        onClick(self.refresher, self.refresh)
        self.killer = QtGui.QPushButton('&Kill', self)
        self.killer.move(125,75)
        onClick(self.killer, self.kill_task)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.combobox)
        layout.addWidget(self.killer)
        self.setLayout(layout)
        self.setWindowTitle("Execution list")    
        self.setGeometry(100, 100, 400, 150)
        self.refresh()
    
    def refresh(self):
        tasks = self.mgr.tasks
        count = len(tasks)
        self.label.setText("Tasks (%i):"%count)
        # Map combobox indices to task IDs
        self.comboboxMap = {}
        self.combobox.clear()
        i = 0 
        for task_id in tasks:
            task = tasks[task_id]
            self.combobox.addItem(repr(task))
            self.comboboxMap[i] = task_id
            i += 1
        self.combobox.adjustSize()
        self.show()
            
    def kill_task(self):
        idx = self.combobox.currentIndex()
        if idx < 0: return # combobox is empty
        task_id = self.comboboxMap[idx]
        self.mgr.terminate(task_id)
        self.refresh()

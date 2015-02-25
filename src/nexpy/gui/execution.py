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
        self.exec_task_id_unique = 0    
        self.exec_tasks = {}
        self.exec_hosts_recent = []
        self.exec_cmds_recent = []
     
    def newTask(self, host, command):
        self.exec_task_id_unique += 1
        task = ExecTask(self.exec_task_id_unique, host, command)
        self.exec_tasks[self.exec_task_id_unique] = task 
        task.run()

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
        print "INIT"
        self.label = QtGui.QLabel(self)
        self.label.move(25,20)
        self.menu = QtGui.QComboBox(self)
        self.menu.move(25,50)

        self.refresher = QtGui.QPushButton('&Refresh', self)
        self.refresher.move(25,75)
        onClick(self.refresher, self.refresh)
        self.killer = QtGui.QPushButton('&Kill', self)
        self.killer.move(125,75)
        onClick(self.killer, self.kill_task)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.menu)
        layout.addWidget(self.killer)
        self.setLayout(layout)
        self.setWindowTitle("Execution list")    
        self.setGeometry(100, 100, 400, 150)
        self.refresh()
    
    def refresh(self):
        print "REFRESH"
        tasks = self.mgr.exec_tasks
        count = len(tasks)
        self.label.setText("Tasks (%i):"%count)
        # Map menu indices to task IDs
        self.menuMap = {}
        self.menu.clear()
        i = 0 
        for task_id in tasks:
            task = tasks[task_id]
            self.menu.addItem(repr(task))
            self.menuMap[i] = task_id
            i += 1
        self.menu.adjustSize()
        self.show()
            
    def kill_task(self):
        idx = self.menu.currentIndex()
        if idx < 0: return
        task_id = self.menuMap[idx]
        task = self.mgr.exec_tasks[task_id]
        print "KILLING", task
        task.terminate()
        
        
        

#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import logging
import os

from PySide import QtGui, QtCore
from Pyro4.errors import CommunicationError

from nexusformat.nexus import (NeXusError, NXgroup, NXfield, NXattr,
                               NXroot, NXentry, NXdata, NXparameters)
from nexusformat.pyro.globus import GlobusCatalog
from nexusformat.pyro.ssh import NeXPyroSSH
from nexpy.gui.datadialogs import BaseDialog


class RemoteDialog(BaseDialog):
    """Dialog to open a remote file.
    """ 
    def __init__(self, parent=None, defaults=(None, None)):

        super(RemoteDialog, self).__init__(parent)
 
        token_file = os.path.join(os.path.expanduser('~'),'.nexpy',
                                  'globusonline', 'gotoken.txt')
        self.globus = GlobusCatalog(token_file)

        catalog_layout = QtGui.QHBoxLayout()
        self.catalog_combo = QtGui.QComboBox()
        for catalog in self.globus.get_catalogs():
            try:
                self.catalog_combo.addItem(catalog['config']['name'])
            except:
                pass
        self.catalog_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.catalog_combo.currentIndexChanged.connect(self.get_datasets)
        catalog_layout.addWidget(QtGui.QLabel('Catalog: '))
        catalog_layout.addWidget(self.catalog_combo)
        catalog_layout.addStretch()
        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(catalog_layout)
        self.layout.addWidget(self.buttonbox())
        self.setLayout(self.layout)
        self.dataset_combo = None
        self.member_combo = None
        self.ssh_controls = False # SSH controls not yet constructed

        catalog, dataset = defaults
        
        if catalog:
            try:
                idx = self.catalog_combo.findText(catalog)
                self.catalog_combo.setCurrentIndex(idx)
                self.get_datasets()
                if dataset:
                    idx = self.dataset_combo.findText(dataset)
                    self.dataset_combo.setCurrentIndex(idx)
                    self.get_members()
            except:
                pass                    
  
        self.setWindowTitle("Open Remote File")

    def get_datasets(self):
        if self.dataset_combo is None:
            dataset_layout = QtGui.QHBoxLayout()
            self.dataset_combo = QtGui.QComboBox()
            self.dataset_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
            self.dataset_combo.currentIndexChanged.connect(self.get_members)
            dataset_layout.addWidget(QtGui.QLabel('Dataset: '))
            dataset_layout.addWidget(self.dataset_combo)
            dataset_layout.addStretch()
            self.layout.insertLayout(1, dataset_layout)       
        else:
            self.dataset_combo.clear()
            if self.member_combo:
                self.member_combo.clear()
        for dataset in self.globus.get_datasets(self.catalog):
            try:
                self.dataset_combo.addItem(dataset['name'])
            except:
                pass

    def get_members(self):
        if self.member_combo is None:
            member_layout = QtGui.QHBoxLayout()
            self.member_combo = QtGui.QComboBox()
            self.member_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
            self.member_combo.currentIndexChanged.connect(self.get_member)
            member_layout.addWidget(QtGui.QLabel('Member: '))
            member_layout.addWidget(self.member_combo)
            member_layout.addStretch()
            self.layout.insertLayout(2, member_layout) 
        else:
            self.member_combo.clear()
        for member in self.globus.get_members(self.dataset):
            try:
                self.member_combo.addItem(member['data_uri'])
            except:
                pass

    def get_member(self):
        self.globus.get_member(self.member)
        if not self.ssh_controls:
            pyro_layout = QtGui.QHBoxLayout()
            user_label = QtGui.QLabel('Remote user:')
            self.user_box = QtGui.QLineEdit(os.getenv('USER'))
            self.user_box.setMinimumWidth(100)
            port_label = QtGui.QLabel('Local port:')
            self.port_box = QtGui.QLineEdit('8801')
            self.port_box.setMinimumWidth(100)
            self.ssh_start_button = QtGui.QPushButton("Start SSH")
            self.ssh_stop_button = QtGui.QPushButton("Stop SSH")
            self.ssh_stop_button.setEnabled(False)
            self.ssh_start_button.clicked.connect(self.ssh_start)
            self.ssh_stop_button.clicked.connect(self.ssh_stop)

            pyro_layout.addStretch()
            pyro_layout.addWidget(user_label)
            pyro_layout.addWidget(self.user_box)
            pyro_layout.addWidget(port_label)
            pyro_layout.addWidget(self.port_box)
            pyro_layout.addWidget(self.ssh_start_button)
            pyro_layout.addWidget(self.ssh_stop_button)
            pyro_layout.addStretch()
            self.layout.insertLayout(3, pyro_layout)
            self.ssh_controls = True

    def ssh_start(self):
        logging.info("")
        self.globus.ssh_start(self.user, self.port)
        self.ssh_stop_button.setEnabled(True)
        self.ssh_start_button.setEnabled(False)

    def ssh_stop(self):
        logging.info("")
        assert(self.ssh_session != None)
        self.globus.ssh_stop()
        self.ssh_start_button.setEnabled(True)
        self.ssh_stop_button.setEnabled(False)

    @property
    def catalog(self):
        try:
            return self.catalog_combo.currentText()
        except Exception:
            return None

    @property
    def dataset(self):
        try:
            return self.dataset_combo.currentText()
        except Exception:
            return None

    @property
    def member(self):
        try:
            return self.member_combo.currentText()
        except Exception:
            return None

    @property
    def user(self):
        try:
            return self.user_box.text()
        except Exception:
            return None

    @property
    def port(self):
        try:
            return int(self.port_box.text())
        except Exception:
            return None

    def accept(self):
        try:
            root = self.globus.load(self.user, self.port)
            from nexpy.gui.consoleapp import _mainwindow, _shell
            name = _mainwindow.treeview.tree.get_name(root.nxfilename)               
            _mainwindow.treeview.tree[name] = _shell[name] = root
            _mainwindow.remote_defaults = (self.catalog, self.dataset)
            logging.info(
                "Opening remote NeXus file '%s' on '%s' as workspace '%s'"
                % (root.nxfilename, root._file, name))
            super(RemoteDialog, self).accept()
        except CommunicationError as e:
            msgBox = QtGui.QMessageBox()
            msgBox.setText("Could not connect to: " + uri)
            msgBox.setIcon(QtGui.QMessageBox.Critical)
            logging.debug("Connection failed to: " + uri + "\n\n" + str(e))
            msgBox.exec_()
        except NeXusError:
            super(RemoteDialog, self).reject()


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
        self.ssh = NeXPyroSSH(self.user, self.hostname, command=self.command)

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
        self.refresher.clicked.connect(self.refresh)
        self.outviewer = QtGui.QPushButton('Show &Output', self)
        self.outviewer.move(125,75)
        self.outviewer.clicked.connect(self.outview)
        self.killer = QtGui.QPushButton('&Kill', self)
        self.killer.move(225,75)
        self.killer.clicked.connect(self.kill_task)
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
        self.refresher.clicked.connect(self.refresh)
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

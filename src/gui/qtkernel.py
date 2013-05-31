from contextlib import contextmanager
import logging
from Queue import Empty
import sys

from IPython.external.qt import QtCore, QtGui
import zmq

from IPython.utils.traitlets import Any, Bool, Type
from IPython.utils import io
from IPython.zmq.ipkernel import Kernel
from IPython.zmq.session import Message, Session
from IPython.zmq.displayhook import ZMQShellDisplayHook
from IPython.zmq.zmqshell import (ZMQDisplayPublisher,
    ZMQInteractiveShell)
from IPython.zmq.iostream import OutStream


class LazyTerm(io.IOTerm):
    """ Dynamically look up cin,cout,cerr from sys.
    """
    def __init__(self, *args, **kwds):
        pass

    @property
    def cin(self):
        return sys.stdin
    @property
    def cout(self):
        return sys.stdout
    @property
    def cerr(self):
        return sys.stderr

@contextmanager
def redirect_output(session, pub_socket):
    sys.stdout = OutStream(session, pub_socket, u'stdout')
    sys.stderr = OutStream(session, pub_socket, u'stderr')
    try:
        yield
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__


class QtDisplayHook(ZMQShellDisplayHook):
    pub_socket = Any()

class QtDisplayPublisher(ZMQDisplayPublisher):
    pub_socket = Any()


class QtInteractiveShell(ZMQInteractiveShell):
    """ A subclass of ZMQInteractiveShell for inprocess Qt use.
    """

    displayhook_class = Type(QtDisplayHook)
    display_pub_class = Type(QtDisplayPublisher)

    def init_io(self):
        io.Term = LazyTerm()


class QtSession(Session):
    """ A session object for the kernel side.
    """

    def send(self, socket, msg_or_type, content=None, parent=None, ident=None,
             buffers=None, subheader=None, track=False, header=None):
        """send a message via a socket, using a uniform message pattern.

        Parameters
        ----------
        socket : zmq.Socket
            The socket on which to send.
        msg_or_type : Message/dict or str
            if str : then a new message will be constructed from content,parent
            if Message/dict : then content and parent are ignored, and the message
            is sent.  This is only for use when sending a Message for a second time.
        content : dict, optional
            The contents of the message
        parent : dict, optional
            The parent header, or parent message, of this message
        ident : bytes, optional
            The zmq.IDENTITY prefix of the destination.
            Only for use on certain socket types.
        subheader : dict or None
            Extra header keys for this message's header (ignored if msg_or_type
            is a message).
        buffers : list or None
            The already-serialized buffers to be appended to the message.
        track : bool
            Whether to track.  Only for use with Sockets, because ZMQStream
            objects cannot track messages.

        Returns
        -------
        msg : dict
            The message, as constructed by self.msg(msg_type,content,parent)
        """
        if isinstance(msg_or_type, (Message, dict)):
            msg = dict(msg_or_type)
        else:
            msg = self.msg(msg_or_type, content, parent)
        socket.send_json(msg)
        return msg

    def recv(self, socket, mode=zmq.NOBLOCK):
        """recv a message on a socket.
        
        Receive an optionally identity-prefixed message, as sent via session.send().
        
        Parameters
        ----------
        
        socket : zmq.Socket
            The socket on which to recv a message.
        mode : int, optional
            the mode flag passed to socket.recv
            default: zmq.NOBLOCK
        
        Returns
        -------
        (ident,msg) : tuple
            always length 2. If no message received, then return is (None,None)
        ident : bytes or None
                the identity prefix is there was one, None otherwise.
        msg : dict or None
                The actual message.  If mode==zmq.NOBLOCK and no message was waiting,
                it will be None.
        """
        try:
            msg = socket.recv_multipart(mode)
        except Empty:
            return None, None
        return None, msg


class QtKernel(Kernel):
    """ An in-process Qt kernel.
    """

    user_ns = Any()
    user_module = Any()

    stdin_socket = Any()
    iopub_socket = Any()
    shell_socket = Any()

    started = Bool(False)

    def __init__(self, **kwargs):
        super(Kernel, self).__init__(**kwargs)

        # Initialize the InteractiveShell subclass
        self.shell = QtInteractiveShell.instance(config=self.config,
            profile_dir = self.profile_dir, user_ns=self.user_ns,
            user_module=self.user_module)
        self.shell.displayhook.session = self.session
        self.shell.displayhook.pub_socket = self.iopub_socket
        self.shell.display_pub.session = self.session
        self.shell.display_pub.pub_socket = self.iopub_socket

        # FIXME: find a better logger name.
        self.log = logging.getLogger(__name__)

        # TMP - hack while developing
        self.shell._reply_content = None

        # Build dict of handlers for message types
        msg_types = [ 'execute_request', 'complete_request',
                      'object_info_request', 'history_request',
                      'connect_request', 'shutdown_request']
        self.handlers = {}
        for msg_type in msg_types:
            self.handlers[msg_type] = getattr(self, msg_type)

    def start(self):
        """ Start a Qt timer to do the event loop.
        """
        if not self.started:
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.do_one_iteration)
            self.timer.start(1000*self._poll_interval)
            self.started = True

    def do_one_iteration(self):
        """ Do one iteration of the kernel's evaluation loop.
        """
        ident, msg = self.session.recv(self.shell_socket, zmq.NOBLOCK)
        if msg is None:
            return

        # Print some info about this message and leave a '--->' marker, so it's
        # easier to trace visually the message chain when debugging.  Each
        # handler prints its message at the end.
        # Eventually we'll move these from stdout to a logger.
        self.log.debug('\n*** MESSAGE TYPE:'+str(msg['header']['msg_type'])+'***')
        self.log.debug('   Content: '+str(msg['content'])+'\n   --->\n   ')

        # Find and call actual handler for message
        handler = self.handlers.get(msg['header']['msg_type'], None)
        if handler is None:
            self.log.error("UNKNOWN MESSAGE TYPE:" +str(msg))
        else:
            with redirect_output(self.session, self.iopub_socket):
                handler(self.shell_socket, ident, msg)

    def _raw_input(self, prompt, ident, parent):
        """ raw_input([prompt]) -> string
        
        Read a string from an input dialog.
        """
        # Parent widget?
        dlg = QtGui.QInputDialog()
        dlg.setInputMode(QtGui.QInputDialog.TextInput)
        dlg.setLabelText(prompt)
        dlg.setWindowTitle(u'Input')
        code = dlg.exec_()
        if code == QtGui.QDialog.Accepted:
            text = unicode(dlg.textValue())
        else:
            text = ''
        return text


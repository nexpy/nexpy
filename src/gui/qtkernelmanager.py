""" Defines a KernelManager for an in-process kernel.
"""

# System library imports.
from Queue import Queue
import zmq
from IPython.external.qt import QtCore

# IPython imports.
from IPython.config.loader import Config
from IPython.utils.traitlets import Any, Bool, HasTraits, Instance
from IPython.frontend.qt.util import MetaQObjectHasTraits, SuperQObject
#from IPython.zmq.session import Session
#from IPython.zmq.kernelmanager import validate_string_dict, validate_string_list

# NeXpy imports
from qtkernel import QtSession, QtKernel

class SocketChannelQObject(SuperQObject):

    # The Session object.
    session = None

    # The queue of messages back to the kernel.
    msg_queue = None

    # Emitted when the channel is started.
    started = QtCore.Signal()

    # Emitted when the channel is stopped.
    stopped = QtCore.Signal()

    #---------------------------------------------------------------------------
    # 'ZMQSocketChannel' interface
    #---------------------------------------------------------------------------

    def __init__(self, session):
        """Create a channel

        Parameters
        ----------
        session : :class:`session.Session`
            The session to use.
        """
        super(SocketChannelQObject, self).__init__()
        self.session = session
        self.msg_queue = Queue()

    def start(self):
        """ Reimplemented to emit signal.
        """
        self.started.emit()

    def stop(self):
        """ Reimplemented to emit signal.
        """
        self.stopped.emit()

    def send_json(self, msg, flags=0):
        """ Call the frontend callback.
        """
        self.call_handlers(msg)

    def recv_multipart(self, mode=zmq.NOBLOCK):
        """ Receive a message from the frontend.
        """
        block = not (mode & zmq.NOBLOCK)
        msg = self.msg_queue.get(block)
        return msg


class QtShellSocketChannel(SocketChannelQObject):
    """The DEALER channel for issuing request/replies to the kernel.
    """

    # Emitted when any message is received.
    message_received = QtCore.Signal(object)

    # Emitted when a reply has been received for the corresponding request
    # type.
    execute_reply = QtCore.Signal(object)
    complete_reply = QtCore.Signal(object)
    object_info_reply = QtCore.Signal(object)
    history_reply = QtCore.Signal(object)

    # Emitted when the first reply comes back.
    first_reply = QtCore.Signal()

    # Used by the first_reply signal logic to determine if a reply is the
    # first.
    _handlers_called = False

    # flag for whether execute requests should be allowed to call raw_input:
    allow_stdin = True

    #---------------------------------------------------------------------------
    # 'ShellSocketChannel' interface
    #---------------------------------------------------------------------------

    def call_handlers(self, msg):
        """ Reimplemented to emit signals instead of making callbacks.
        """
        # Emit the generic signal.
        self.message_received.emit(msg)

        # Emit signals for specialized message types.
        msg_type = msg['header']['msg_type']
        signal = getattr(self, msg_type, None)
        if signal:
            signal.emit(msg)

        if not self._handlers_called:
            self.first_reply.emit()
            self._handlers_called = True

    #---------------------------------------------------------------------------
    # 'QtShellSocketChannel' interface
    #---------------------------------------------------------------------------
    def execute(self, code, silent=False,
                user_variables=None, user_expressions=None, allow_stdin=None):
        """Execute code in the kernel.

        Parameters
        ----------
        code : str
            A string of Python code.

        silent : bool, optional (default False)
            If set, the kernel will execute the code as quietly possible.

        user_variables : list, optional
            A list of variable names to pull from the user's namespace.  They
            will come back as a dict with these names as keys and their
            :func:`repr` as values.

        user_expressions : dict, optional
            A dict with string keys and  to pull from the user's
            namespace.  They will come back as a dict with these names as keys
            and their :func:`repr` as values.

        allow_stdin : bool, optional
            Flag for 
            A dict with string keys and  to pull from the user's
            namespace.  They will come back as a dict with these names as keys
            and their :func:`repr` as values.

        Returns
        -------
        The msg_id of the message sent.
        """
        if user_variables is None:
            user_variables = []
        if user_expressions is None:
            user_expressions = {}
        if allow_stdin is None:
            allow_stdin = self.allow_stdin
     
        # Don't waste network traffic if inputs are invalid
        if not isinstance(code, basestring):
            raise ValueError('code %r must be a string' % code)
        validate_string_list(user_variables)
        validate_string_dict(user_expressions)

        # Create class for content/msg creation. Related to, but possibly
        # not in Session.
        content = dict(code=code, silent=silent,
                       user_variables=user_variables,
                       user_expressions=user_expressions,
                       allow_stdin=allow_stdin,
                       )
        msg = self.session.msg('execute_request', content)
        self._queue_request(msg)
        return msg['header']['msg_id']

    def complete(self, text, line, cursor_pos, block=None):
        """Tab complete text in the kernel's namespace.

        Parameters
        ----------
        text : str
            The text to complete.
        line : str
            The full line of text that is the surrounding context for the
            text to complete.
        cursor_pos : int
            The position of the cursor in the line where the completion was
            requested.
        block : str, optional
            The full block of code in which the completion is being requested.

        Returns
        -------
        The msg_id of the message sent.
        """
        content = dict(text=text, line=line, block=block, cursor_pos=cursor_pos)
        msg = self.session.msg('complete_request', content)
        self._queue_request(msg)
        return msg['header']['msg_id']

    def object_info(self, oname, detail_level=0):
        """Get metadata information about an object.

        Parameters
        ----------
        oname : str
            A string specifying the object name.
        detail_level : int, optional
            The level of detail for the introspection (0-2)

        Returns
        -------
        The msg_id of the message sent.
        """
        content = dict(oname=oname, detail_level=detail_level)
        msg = self.session.msg('object_info_request', content)
        self._queue_request(msg)
        return msg['header']['msg_id']

    def history(self, raw=True, output=False, hist_access_type='range', **kwargs):
        """Get entries from the history list.

        Parameters
        ----------
        raw : bool
            If True, return the raw input.
        output : bool
            If True, then return the output as well.
        hist_access_type : str
            'range' (fill in session, start and stop params), 'tail' (fill in n)
             or 'search' (fill in pattern param).

        session : int
            For a range request, the session from which to get lines. Session
            numbers are positive integers; negative ones count back from the
            current session.
        start : int
            The first line number of a history range.
        stop : int
            The final (excluded) line number of a history range.

        n : int
            The number of lines of history to get for a tail request.

        pattern : str
            The glob-syntax pattern for a search request.

        Returns
        -------
        The msg_id of the message sent.
        """
        content = dict(raw=raw, output=output, hist_access_type=hist_access_type,
                                                                    **kwargs)
        msg = self.session.msg('history_request', content)
        self._queue_request(msg)
        return msg['header']['msg_id']

    def shutdown(self, restart=False):
        """Request an immediate kernel shutdown.

        Upon receipt of the (empty) reply, client code can safely assume that
        the kernel has shut down and it's safe to forcefully terminate it if
        it's still alive.

        The kernel will send the reply via a function registered with Python's
        atexit module, ensuring it's truly done as the kernel is done with all
        normal operation.
        """
        # Send quit message to kernel. Once we implement kernel-side setattr,
        # this should probably be done that way, but for now this will do.
        msg = self.session.msg('shutdown_request', {'restart':restart})
        self._queue_request(msg)
        return msg['header']['msg_id']

    def reset_first_reply(self):
        """ Reset the first_reply signal to fire again on the next reply.
        """
        self._handlers_called = False

    def _queue_request(self, msg):
        self.msg_queue.put(msg)


class QtSubSocketChannel(SocketChannelQObject):
    """The SUB channel which listens for messages that the kernel publishes.
    """

    # Emitted when any message is received.
    message_received = QtCore.Signal(object)

    # Emitted when a message of type 'stream' is received.
    stream_received = QtCore.Signal(object)

    # Emitted when a message of type 'pyin' is received.
    pyin_received = QtCore.Signal(object)

    # Emitted when a message of type 'pyout' is received.
    pyout_received = QtCore.Signal(object)

    # Emitted when a message of type 'pyerr' is received.
    pyerr_received = QtCore.Signal(object)

    # Emitted when a message of type 'display_data' is received
    display_data_received = QtCore.Signal(object)

    # Emitted when a crash report message is received from the kernel's
    # last-resort sys.excepthook.
    crash_received = QtCore.Signal(object)

    # Emitted when a shutdown is noticed.
    shutdown_reply_received = QtCore.Signal(object)

    #---------------------------------------------------------------------------
    # 'SubSocketChannel' interface
    #---------------------------------------------------------------------------

    def call_handlers(self, msg):
        """ Reimplemented to emit signals instead of making callbacks.
        """
        # Emit the generic signal.
        self.message_received.emit(msg)
        # Emit signals for specialized message types.
        msg_type = msg['header']['msg_type']
        signal = getattr(self, msg_type + '_received', None)
        if signal:
            signal.emit(msg)
        elif msg_type in ('stdout', 'stderr'):
            self.stream_received.emit(msg)

    def flush(self):
        """ Reimplemented to ensure that signals are dispatched immediately.
        """
        QtCore.QCoreApplication.instance().processEvents()

    def _handle_recv(self):
        # Get all of the messages we can
        while True:
            try:
                ident,msg = self.session.recv(self.socket)
            except zmq.ZMQError:
                # Check the errno?
                # Will this trigger POLLERR?
                break
            else:
                if msg is None:
                    break
                self.call_handlers(msg)


class QtStdInSocketChannel(SocketChannelQObject):
    """A reply channel to handle raw_input requests that the kernel makes.
    """

    # Emitted when any message is received.
    message_received = QtCore.Signal(object)

    # Emitted when an input request is received.
    input_requested = QtCore.Signal(object)

    #---------------------------------------------------------------------------
    # 'StdInSocketChannel' interface
    #---------------------------------------------------------------------------

    def call_handlers(self, msg):
        """ Reimplemented to emit signals instead of making callbacks.
        """
        # Emit the generic signal.
        self.message_received.emit(msg)

        # Emit signals for specialized message types.
        msg_type = msg['header']['msg_type']
        if msg_type == 'input_request':
            self.input_requested.emit(msg)

    def input(self, string):
        """Send a string of raw input to the kernel."""
        content = dict(value=string)
        msg = self.session.msg('input_reply', content)
        self._queue_reply(msg)

    def _queue_reply(self, msg):
        self.msg_queue.put(msg)


class QtHBSocketChannel(SocketChannelQObject):
    """ Dummy heartbeat.
    """
   
    _paused = False

    # Emitted when the kernel has died.
    kernel_died = QtCore.Signal(object)

    #---------------------------------------------------------------------------
    # 'HBSocketChannel' interface
    #---------------------------------------------------------------------------

    def call_handlers(self, since_last_heartbeat):
        """ Reimplemented to emit signals instead of making callbacks.
        """
        # Emit the generic signal.
        self.kernel_died.emit(since_last_heartbeat)

    def pause(self):
        self._paused = True

    def unpause(self):
        self._paused = False


class QtKernelManager(HasTraits, SuperQObject):
    """ A kernel manager for the frontend.
    """
    __metaclass__ = MetaQObjectHasTraits

    # config object for passing to child configurables
    config = Instance(Config)

    # The Session to use for communication with the kernel.
    session = Instance(Session,(),{})

    # The kernel itself.
    kernel = Instance(QtKernel)

    user_ns = Any()
    user_module = Any()

    shell_channel = Instance(QtShellSocketChannel)
    sub_channel = Instance(QtSubSocketChannel)
    stdin_channel = Instance(QtStdInSocketChannel)
    hb_channel = Instance(QtHBSocketChannel)

    # Emitted when the kernel manager has started listening.
    started_kernel = QtCore.Signal()

    # Emitted when the kernel manager has started listening.
    started_channels = QtCore.Signal()

    # Emitted when the kernel manager has stopped listening.
    stopped_channels = QtCore.Signal()

    # Whether channels are running or not.
    channels_running = Bool(True)

    #---------------------------------------------------------------------------
    # 'KernelManager' interface
    #---------------------------------------------------------------------------

    #------ Kernel process management ------------------------------------------

    def start_kernel(self, *args, **kw):
        self.kernel.start()

    def shutdown_kernel(self, *args, **kw):
        pass

    def restart_kernel(self, *args, **kw):
        pass

    #------ Channel management -------------------------------------------------

    def start_channels(self, *args, **kw):
        """ Reimplemented to emit signal.
        """
        self.started_channels.emit()

    def stop_channels(self):
        """ Reimplemented to emit signal.
        """ 
        self.stopped_channels.emit()

    #### Traits stuff #########################################################

    def _stdin_channel_default(self):
        return QtStdInSocketChannel(self.session)
    def _sub_channel_default(self):
        return QtSubSocketChannel(self.session)
    def _shell_channel_default(self):
        return QtShellSocketChannel(self.session)
    def _hb_channel_default(self):
        return QtHBSocketChannel(self.session)

    def _kernel_default(self):
        kernel = QtKernel(
            session=QtSession(session=self.session.session,config=self.config),
            user_ns=self.user_ns,
            user_module=self.user_module,
            iopub_socket=self.sub_channel,
            shell_socket=self.shell_channel,
            stdin_socket=self.stdin_channel,
        )
        return kernel

from logging import getLogger
from threading import Thread
from time import sleep

from signalrc.ws_transport import WebSocketsTransport

logger = getLogger('signalr.client')


class SignalRClient:
    def __init__(self, url, hub, session=None):
        self.url = url
        self._invokes_counter = -1
        self.token = None
        self.id = None
        self.invokes_data = {}
        self.received = EventHook()
        self.error = EventHook()
        self.starting = EventHook()
        self.stopping = EventHook()
        self.exception = EventHook()
        self.is_open = False
        self._transport = WebSocketsTransport(self.url, session)
        self._message_listener = None
        self.started = False
        self.hub_name = hub
        self.received.add_hooks(self.handle_hub_message, self.handle_error)
        self._hub_handlers = {}

    def handle_hub_message(self, data):
        if 'R' in data and not isinstance(data['R'], bool):
            if 'R' in self._hub_handlers:
                self._hub_handlers['R'].trigger_hooks({'R': data['R']})
        messages = data['M'] if 'M' in data and len(data['M']) > 0 else {}
        for inner_data in messages:
            method = inner_data['M']
            if method in self._hub_handlers:
                arguments = inner_data['A']
                self._hub_handlers[method].trigger_hooks(*arguments)

    def handle_error(self, data):
        if 'E' in data:
            invoke_index = int(data.get('I', -1))
            self.error.trigger_hooks({'error': data['E'],
                                      'call_arguments': self.invokes_data.get(invoke_index)})

    def start(self):
        logger.info('Starting connection')
        self.starting.trigger_hooks()

        negotiate_data = self._transport.negotiate(self.hub_name)
        self.token = negotiate_data['ConnectionToken']
        self.id = negotiate_data['ConnectionId']

        self._transport.init_connection(self.token, self.hub_name)
        self.is_open = True
        self._message_listener = Thread(target=self.wrapped_listener)
        self._message_listener.start()
        self.started = True

    def wrapped_listener(self):
        while self.is_open:
            try:
                data = self._transport.receive()
                self.received.trigger_hooks(data)
            except Exception as error:
                logger.exception('Failed to receive the data via transport')
                try:
                    self.exception.trigger_hooks(error)
                finally:
                    self.is_open = False

    def close(self):
        logger.info('Closing connection')
        if self.is_open:
            self.is_open = False
            self._message_listener.join()
            self._transport.close()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def run_while_open(self):
        while self.is_open:
            sleep(0.01)

    def invoke(self, method, *data):
        self._invokes_counter += 1
        self._transport.send({'H': self.hub_name, 'M': method, 'A': data,
                              'I': self._invokes_counter})
        self.invokes_data[self._invokes_counter] = {'hub_name': self.hub_name, 'method': method,
                                                    'data': data}

    def subscribe_to_event(self, event_id, handler):
        if event_id not in self._hub_handlers:
            self._hub_handlers[event_id] = EventHook()
        self._hub_handlers[event_id].add_hooks(handler)


class EventHook:
    def __init__(self):
        self._handlers = []

    def add_hooks(self, *handlers):
        self._handlers.extend(handlers)
        return self

    def trigger_hooks(self, *args, **kwargs):
        for handler in self._handlers:
            handler(*args, **kwargs)



import json
from logging import getLogger
from urllib.parse import urlparse, urlunparse, quote_plus

from requests import Session
from websocket import create_connection


logger = getLogger('signalr.websocket')


class WebSocketsTransport:
    protocol_version = '1.5'

    def __init__(self, base_url, session):
        self.base_url = base_url
        if session is None:
            session = Session()
        self._session = session
        self.ws = None

    def negotiate(self, hub_name):
        data = json.dumps([{'name': hub_name}])
        url = self._get_base_url('negotiate', connectionData=data)
        negotiate = self._session.get(url)

        negotiate.raise_for_status()

        return negotiate.json()

    @staticmethod
    def __get_ws_url_from(url):
        parsed = urlparse(url)
        scheme = 'wss' if parsed.scheme == 'https' else 'ws'
        url_data = (scheme, parsed.netloc, parsed.path, parsed.params, parsed.query,
                    parsed.fragment)

        return urlunparse(url_data)

    def init_connection(self, token, hub):
        ws_url = self.__get_ws_url_from(self._get_url('connect', token, hub))

        self.ws = create_connection(ws_url,
                                    header=self._get_headers(),
                                    cookie=self._get_cookie_str(),
                                    enable_multithread=True)
        self._session.get(self._get_url('start', token, hub))

        return self.receive

    def receive(self):
        message = self.ws.recv()
        if len(message) > 0:
            data = json.loads(message)
            return data

    def send(self, data):
        self.ws.send(json.dumps(data))

    def close(self):
        self.ws.close()
        self._session.close()

    def _get_headers(self):
        if self._session.auth:
            self._session.auth(self._session)
        return ['{}: {}'.format(name, value) for name, value in self._session.headers.items()]

    def _get_cookie_str(self):
        return '; '.join(['{}={}'.format(name, value)
                          for name, value in self._session.cookies.items()])

    def _get_url(self, action, token, hub, **kwargs):
        args = kwargs.copy()
        args['transport'] = 'webSockets'
        args['connectionToken'] = token
        args['connectionData'] = json.dumps([{'name': hub}])
        return self._get_base_url(action, **args)

    def _get_base_url(self, action, **kwargs):
        args = kwargs.copy()
        args['clientProtocol'] = self.protocol_version
        query = '&'.join(['{key}={value}'.format(key=key, value=quote_plus(args[key]))
                          for key in args])

        return '{url}/{action}?{query}'.format(url=self.base_url, action=action, query=query)
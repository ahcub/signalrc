import json
from base64 import b64decode
from zlib import MAX_WBITS, decompress

from signalrc.signalrc import SignalRClient


def decode_message(message):
    deflated_msg = decompress(b64decode(message), -MAX_WBITS)
    return json.loads(deflated_msg.decode())


def on_debug(**msg):
    print(msg)
    if 'R' in msg and type(msg['R']) is not bool:
        decoded_msg = decode_message(msg['R'])
        print(decoded_msg)


def on_message(msg):
    decoded_msg = decode_message(msg)
    print(decoded_msg)


def on_error(msg):
    print(msg)


signalr_client = SignalRClient("https://socket.bittrex.com/signalr", hub='c2')

signalr_client.start()

signalr_client.received.add_hooks(on_debug)
signalr_client.error.add_hooks(on_error)

signalr_client.subscribe_to_event('uE', on_message)

signalr_client.invoke('queryExchangeState', 'USD-BTC')
signalr_client.invoke('SubscribeToExchangeDeltas', 'USD-BTC')

signalr_client.run_while_open()

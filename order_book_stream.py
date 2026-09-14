import threading
import time
from typing import Any

import upstox_client


class D30OrderBook:
    """Single Upstox V3 full_d30 stream with a thread-safe latest snapshot."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.lock = threading.Lock()
        self.snapshot = {}
        self.instrument_key = None
        self.streamer = None
        self.thread = None
        self.error = None
        self.connected = False

    def _message(self, message: Any):
        if not isinstance(message, dict):
            return
        feeds = message.get('feeds') or {}
        if not isinstance(feeds, dict):
            return
        for key, value in feeds.items():
            if not isinstance(value, dict):
                continue
            with self.lock:
                self.snapshot = {'instrument_key': key, 'feed': value, 'currentTs': message.get('currentTs')}

    def _open(self):
        self.connected = True
        if self.instrument_key and self.streamer:
            try:
                self.streamer.subscribe([self.instrument_key], 'full_d30')
            except Exception as exc:
                self.error = str(exc)

    def _error(self, error):
        self.error = str(error)
        self.connected = False

    def _close(self, *_args):
        self.connected = False

    def _run(self):
        try:
            config = upstox_client.Configuration()
            config.access_token = self.access_token
            client = upstox_client.ApiClient(config)
            self.streamer = upstox_client.MarketDataStreamerV3(client)
            self.streamer.on('open', self._open)
            self.streamer.on('message', self._message)
            self.streamer.on('error', self._error)
            self.streamer.on('close', self._close)
            self.streamer.auto_reconnect(True, 2, 10)
            self.streamer.connect()
        except Exception as exc:
            self.error = str(exc)
            self.connected = False

    def start(self, instrument_key: str):
        if not instrument_key:
            raise ValueError('instrument_key is required')
        if self.thread is None or not self.thread.is_alive():
            self.instrument_key = instrument_key
            self.thread = threading.Thread(target=self._run, daemon=True, name='nifty-vision-d30')
            self.thread.start()
            return
        if self.instrument_key == instrument_key:
            return
        old = self.instrument_key
        try:
            if old:
                self.streamer.unsubscribe([old])
            self.instrument_key = instrument_key
            self.streamer.subscribe([instrument_key], 'full_d30')
            with self.lock:
                self.snapshot = {}
        except Exception as exc:
            self.error = str(exc)

    def get(self):
        with self.lock:
            return dict(self.snapshot)

    def status(self):
        return {'connected': self.connected, 'error': self.error, 'instrument_key': self.instrument_key}


_streams = {}
_streams_lock = threading.Lock()


def get_stream(access_token: str) -> D30OrderBook:
    key = access_token[-16:] if access_token else 'missing'
    with _streams_lock:
        if key not in _streams:
            _streams[key] = D30OrderBook(access_token)
        return _streams[key]

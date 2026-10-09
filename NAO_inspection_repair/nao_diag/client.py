# -*- coding: utf-8 -*-
"""
@ Project            : CRA NAO 机器人验修半自动化工具箱
@ Author             : XCrane
"""

from __future__ import unicode_literals
import socket
import time
from .compat import PY2, safe_float, text_type, to_text

class NaoqiUnavailable(RuntimeError):
    pass

def _native_arg(value):
    if not PY2:
        return value
    if isinstance(value, text_type):
        return value.encode("utf-8")
    if isinstance(value, list):
        return [_native_arg(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_native_arg(item) for item in value)
    if isinstance(value, dict):
        return dict((_native_arg(key), _native_arg(item)) for key, item in value.items())
    return value

class _NativeProxyAdapter(object):

    def __init__(self, proxy):
        self._proxy = proxy

    def __getattr__(self, name):
        attribute = getattr(self._proxy, name)
        if name == "post":
            return _NativeProxyAdapter(attribute)
        if not callable(attribute):
            return attribute

        def invoke(*args, **kwargs):
            native_args = tuple(_native_arg(item) for item in args)
            native_kwargs = dict((_native_arg(key), _native_arg(item))
                                 for key, item in kwargs.items())
            return attribute(*native_args, **native_kwargs)
        return invoke

class NaoClient(object):

    def __init__(self, ip, port=9559, proxy_factory=None):
        self.ip = to_text(ip)
        self.port = int(port)
        self._proxy_factory = proxy_factory
        self._proxies = {}

    def _load_factory(self):
        if self._proxy_factory is not None:
            return self._proxy_factory
        try:
            from naoqi import ALProxy
        except ImportError as exc:
            raise NaoqiUnavailable(
                "无法导入 naoqi：请通过 run.ps1 启动，或把 pynaoqi 的 lib 目录加入 "
                "PYTHONPATH/PATH。Raw Error：%s" % to_text(exc)
            )
        self._proxy_factory = ALProxy
        return self._proxy_factory

    def proxy(self, service, refresh=False):
        service = to_text(service)
        if refresh or service not in self._proxies:
            factory = self._load_factory()
            proxy = factory(_native_arg(service), _native_arg(self.ip), self.port)
            self._proxies[service] = _NativeProxyAdapter(proxy) if PY2 else proxy
        return self._proxies[service]

    def try_proxy(self, service):
        try:
            return self.proxy(service), None
        except Exception as exc:
            return None, to_text(exc)

    def tcp_probe(self, timeout=3.0):
        started = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(float(timeout))
        try:
            sock.connect((self.ip, self.port))
            return (time.time() - started) * 1000.0
        finally:
            sock.close()

    def memory_value(self, key, default=None):
        try:
            return self.proxy("ALMemory").getData(key)
        except Exception:
            return default

    def memory_values(self, keys):
        keys = list(keys)
        memory = self.proxy("ALMemory")
        try:
            values = memory.getListData(keys)
            return dict(zip(keys, values))
        except Exception:
            result = {}
            for key in keys:
                try:
                    result[key] = memory.getData(key)
                except Exception:
                    result[key] = None
            return result

    def data_keys(self, filter_text):
        try:
            return list(self.proxy("ALMemory").getDataList(filter_text))
        except Exception:
            return []

    def call_optional(self, service, method, *args):
        proxy = self.proxy(service)
        function = getattr(proxy, method)
        return function(*args)

def pairs_to_dict(value):
    if not isinstance(value, (list, tuple)):
        return value
    result = {}
    for item in value:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            result[to_text(item[0])] = item[1]
        else:
            return value
    return result

def normalize_battery_percent(value):
    number = safe_float(value, None)
    if number is None:
        return None
    if 0.0 <= number <= 1.0:
        number *= 100.0
    return number

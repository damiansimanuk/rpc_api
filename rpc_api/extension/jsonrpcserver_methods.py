import inspect
from typing import Callable, Dict, Any, List, Union, Optional
from rpc_api.pubsub import EventsEmmitterHub
from jsonrpcserver.methods import Methods
import logging
import io
import pydoc

logger = logging.getLogger("rpc_api.jsonrpcserver")


class RpcJsonMethods(Methods):
    def __init__(self, evnetsEmmitter: EventsEmmitterHub = None, **kwargs: Any):
        Methods.__init__(self, **kwargs)
        self.evnetsEmmitter = evnetsEmmitter

        self.register("list")(self.list_functions)
        self.register("help")(self.help_functions)

        if evnetsEmmitter:
            self.register("rpc.on")(evnetsEmmitter.rpc_on)
            self.register("rpc.off")(evnetsEmmitter.rpc_off)

    async def event_emit(self, event: str, *params) -> int:
        await EventsEmmitterHub.event_emit(event, params)

    async def list_functions(self):
        """
        Lista las funciones disponibles y sus documentaciones
        """
        res = {}
        for n, m in self.items.items():
            if hasattr(m, "_base_function"):
                m = m._base_function
            out = io.StringIO()
            pydoc.Helper(output=out)(m)
            res[n] = str(out.getvalue())
            out.close()
        return res

    async def help_functions(self, method):
        """
        Lista las funciones disponibles y sus documentaciones
        """
        m = self.items[method]
        if hasattr(m, "_base_function"):
            m = m._base_function

        out = io.StringIO()
        pydoc.Helper(output=out)(m)
        res = str(out.getvalue())
        out.close()
        return res

    def register(self, function_name: str = None):
        def decorator(func: Callable) -> Callable:
            fname = function_name or func.__name__
            self.items[fname] = func
            return func
        return decorator


rpc_methods = RpcJsonMethods()


def register(function_name: str = None) -> Optional[Callable]:
    return rpc_methods.register(function_name)

"""Asynchronous dispatch"""
import asyncio
import collections
from json import JSONDecodeError
from json import loads as deserialize
from typing import Any, Iterable, Optional, Union

from apply_defaults import apply_config  # type: ignore
from jsonschema import ValidationError  # type: ignore

from jsonrpcserver.dispatcher import (add_handlers, config, create_requests,
                                      handle_exceptions, log_request, log_response,
                                      remove_handlers, schema, validate)
from jsonrpcserver.methods import Method, Methods, global_methods, validate_args
from jsonrpcserver.request import NOCONTEXT, Request
from jsonrpcserver.response import (BatchResponse, InvalidJSONResponse,
                                    InvalidJSONRPCResponse, Response, SuccessResponse)

from typing import Callable, Dict, Any, List, Union, Optional
import inspect
import asyncio
from pydantic import BaseModel, create_model, ValidationError, Schema, conint, condecimal
from rpc_api.common import get_schema_fields
import logging

logger = logging.getLogger("rpc_api.jsonrpcserver")


class Validator:
    def __init__(self, func: Callable):
        self.argspec = inspect.getfullargspec(func)
        self.has_kw = self.argspec.varkw is not None
        self.has_args = self.argspec.varargs is not None
        self.is_coroutine = asyncio.iscoroutinefunction(func)

        endpoint_signature = inspect.signature(func)
        arguments = set(self.argspec.args + self.argspec.kwonlyargs)
        self.args = set(self.argspec.args).intersection(set(endpoint_signature.parameters))
        self.arguments = arguments.intersection(set(endpoint_signature.parameters))

        self.func = func

        fields = get_schema_fields(func)
        self.model = None

        self.model_name = "model_" + func.__name__
        for n, ad in fields.items():
            a, d = ad
            if issubclass(a, BaseModel) and getattr(d, "extra", None) and d.extra.get("embed", False):
                self.model_name = n
                self.model = d

        if fields and not self.model:
            self.model = create_model(self.model_name, **fields)

    def get_validate_arguments(self, *args, **kwargs) -> Dict:
        if not self.model:
            return (args, kwargs)
        logger.debug(f"exec... {self.func.__name__}, {args}, {kwargs} ")
        all_args = dict(zip(self.args, args))
        all_args.update(kwargs)

        try:
            data = self.model(**all_args)
            all_args.update(**{f: getattr(data, f, None) for f in list(data.__fields__)})
            all_args.update(**{self.model_name: self.model})

            if self.has_kw:
                return ([], all_args)
            else:
                return ([], {k: all_args.get(k, None) for k in self.arguments})

        except ValidationError as e:
            raise TypeError(str(e))


class Caller:
    _validator = {}

    def get_validator(self, method: Method):
        validator = self._validator.get(method, None)
        if not validator:
            validator = Validator(method)
            self._validator[method] = validator

        return validator

    async def process_result(self, result: Any):
        return result

    async def call(self, method: Method, *args: Any, **kwargs: Any) -> Any:
        validator = self.get_validator(method)
        _args, _kwargs = validator.get_validate_arguments(*args, **kwargs)
        logger.info("call %r(%r, %r)", method, _args, _kwargs)
        if validator.is_coroutine:
            return await self.process_result(await method(*_args, **_kwargs))
        else:
            return await self.process_result(method(*_args, **_kwargs))


async def call(method: Method, *args: Any, **kwargs: Any) -> Any:
    return await validate_args(method, *args, **kwargs)(*args, **kwargs)

CALLER = Caller()


async def safe_call(request: Request, methods: Methods, *, caller: Caller, debug: bool) -> Response:
    with handle_exceptions(request, debug) as handler:
        if caller:
            result = await caller.call(
                methods.items[request.method], *request.args, **request.kwargs
            )
        else:
            result = await call(
                methods.items[request.method], *request.args, **request.kwargs
            )
        handler.response = SuccessResponse(result=result, id=request.id)
    return handler.response


async def call_requests(
    requests: Union[Request, Iterable[Request]], methods: Methods,
    caller: Caller,
    debug: bool
) -> Response:
    if isinstance(requests, collections.Iterable):
        responses = (safe_call(r, methods, caller=caller, debug=debug) for r in requests)
        return BatchResponse(await asyncio.gather(*responses))
    return await safe_call(requests, methods, caller=caller, debug=debug)


async def dispatch_pure(
    request: str,
    methods: Methods,
    *,
    caller: Caller,
    context: Any,
    convert_camel_case: bool,
    debug: bool
) -> Response:
    try:
        deserialized = validate(deserialize(request), schema)
    except JSONDecodeError as exc:
        return InvalidJSONResponse(data=str(exc), debug=debug)
    except ValidationError as exc:
        return InvalidJSONRPCResponse(data=None, debug=debug)
    return await call_requests(
        create_requests(
            deserialized, context=context, convert_camel_case=convert_camel_case
        ),
        methods,
        caller=caller,
        debug=debug,
    )


@apply_config(config)
async def dispatch(
    request: str,
    methods: Optional[Methods] = None,
    *,
    basic_logging: bool = False,
    convert_camel_case: bool = False,
    caller: Caller = CALLER,
    context: Any = NOCONTEXT,
    debug: bool = False,
    trim_log_values: bool = False,
    **kwargs: Any
) -> Response:
    # Use the global methods object if no methods object was passed.
    methods = global_methods if methods is None else methods
    # Add temporary stream handlers for this request, and remove them later
    if basic_logging:
        request_handler, response_handler = add_handlers()
    log_request(request, trim_log_values=trim_log_values)
    response = await dispatch_pure(
        request,
        methods,
        caller=caller,
        debug=debug,
        context=context,
        convert_camel_case=convert_camel_case,
    )
    log_response(str(response), trim_log_values=trim_log_values)
    # Remove the temporary stream handlers
    if basic_logging:
        remove_handlers(request_handler, response_handler)
    return response

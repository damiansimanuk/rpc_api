from typing import (Any, Callable, Dict, List, Optional, Sequence, Set, Type, Union, get_type_hints)
from functools import wraps, update_wrapper
import sys
from funcsigs import signature
import inspect
import functools
import typing 
from pydantic import BaseModel, create_model, ValidationError, Schema
from pydantic.schema import schema as pdschema
from enum import Enum
import asyncio
from copy import deepcopy
from pprint import pprint
from rpc_api.common import get_schema_fields, ParseType, Query, Path, Header, Body, Cookie, Form
 

class ParametersParserBase:
    def get_context(self, base_function: Callable, args: List, kwargs: Dict) -> Any:
        raise NotImplemented

    async def get_parameters(self, context: Any, parser_type: ParseType, args: List,
                             kwargs: Dict) -> Dict:
        raise NotImplemented

    async def get_path_parameters(self, context: Any, args: List, kwargs: Dict) -> Dict:
        raise NotImplemented

    async def get_query_parameters(self, context: Any, args: List, kwargs: Dict) -> Dict:
        """Pull a querystring value from the request."""
        raise NotImplemented

    async def get_headers_parameters(self, context: Any, args: List, kwargs: Dict) -> Dict:
        """Pull a value from the header data."""
        raise NotImplemented

    async def get_cookies_parameters(self, context: Any,  args: List, kwargs: Dict) -> Dict:
        """Pull a value from the cookiejar."""
        raise NotImplemented

    async def get_body_parameters(self, context: Any, args: List, kwargs: Dict) -> Dict:
        """Pull a json value from the request."""
        raise NotImplemented

    async def get_form_parameters(self, context: Any, args: List, kwargs: Dict) -> Dict:
        """Pull a json value from the request."""
        raise NotImplemented
 
    async def send_response(self, context: Any, data) -> Dict:
        """Pull a form value from the request."""
        raise NotImplemented

    async def send_error(self, context: Any, error) -> Dict:
        """Pull a form value from the request."""
        raise NotImplemented


class Parameters:
    def __init__(self, parser_mode: ParseType,
                 parser: ParametersParserBase,
                 model_name: str = None,
                 **fields: Dict[str, Any]):
        self.parser_mode = parser_mode
        self.model_name = model_name if model_name else "model_%s" % (parser_mode.value)
        self.fields = fields.copy()
        self.parser = parser
        self._model = None
        self._schema = None

    def update_fields(self, **fields: Dict[str, Any]):
        self.fields.update(fields)
        self._model = None

    def set_model(self, model):
        self.fields.clear()
        self._model = model
        self._schema = pdschema([self._model], ref_prefix='#/components/schemas/')

    @property
    def model(self) -> Callable:
        m = getattr(self, "_model", None)
        if m:
            return m

        if self.fields:
            pprint(self.fields)
            self._model = create_model(self.model_name, **self.fields)
            self._schema = pdschema([self._model], ref_prefix='#/components/schemas/')
            return self._model

    async def load(self, ctx, args: List[Any], kwargs: Dict[str, Any]) -> BaseModel:
        data = kwargs
        if self.parser:
            if self.parser_mode == ParseType.Header:
                data = await self.parser.get_headers_parameters(ctx, args, kwargs)
            elif self.parser_mode == ParseType.Path:
                data = await self.parser.get_path_parameters(ctx, args, kwargs)
            elif self.parser_mode == ParseType.Query:
                data = await self.parser.get_query_parameters(ctx, args, kwargs)
            elif self.parser_mode == ParseType.Body:
                data = await self.parser.get_body_parameters(ctx, args, kwargs)
            elif self.parser_mode == ParseType.Cookie:
                data = await self.parser.get_cookies_parameters(ctx, args, kwargs)
            else:
                data = await self.parser.get_parameters(ctx, self.parser_mode, args, kwargs)

        if self.model:
            return self.model(**data)
        return None
 
    def __repr__(self):
        if self.model:
            return self.model.__fields__.__repr__()
        else:
            return str(self.__class__)

    def spec(self, response_status="200") -> Dict[str, Any]:
        if self.model:
            if self.parser_mode in (ParseType.Query, ParseType.Header, ParseType.Path,
                                    ParseType.Cookie):
                return self.spec_parameters()
            elif self.parser_mode in (ParseType.Body, ParseType.Form, ParseType.Body):
                return self.spec_body()
            else:
                return self.spec_response(response_status)
        return deepcopy(self.default_response) 

    default_response = {
        "definitions": {},
        "parameters": [],
        "tags": ["Books"],
        "summary": "Retrieve Person from author",
        "description": "Retrieve Person items from the Book author \"to-one\" relationship",
        "responses": {
            "405": {
                "description": "Method Not Allowed"
            }
        },
        "requestBody": {"content": {}}
    }

    def spec_parameters(self):
        res = deepcopy(self.default_response)
        parameters = []
        definitions = self._schema["definitions"].copy()

        schm = definitions.pop(self.model_name)
        required = schm.get("required", [])
        properties = schm.get("properties", {})

        for pname, pdef in properties.items():
            param = {}
            param.update(
                **pdef,
                name=pname,
                required=(pname in required),
                **{"in": self.parser_mode.value},
                schema=pdef)

            parameters.append(param)

        res["definitions"] = definitions
        res["parameters"] = parameters
        return res

    def spec_body(self):
        res = deepcopy(self.default_response)
        definitions = self._schema["definitions"].copy()

        if not definitions.get(self.model_name, None):
            _name = self.model.__name__
            schm = {"$ref": '#/components/schemas/'+_name}
        else:
            schm = definitions.pop(self.model_name)

        ct = 'application/json'
        if self.parser_mode in (ParseType.Form):
            ct = 'application/x-www-form-urlencoded'

        res["requestBody"]["content"].update({
            ct: {
                "schema": schm
            }
        })
        res["definitions"] = definitions
        return res

    def spec_response(self, default_status="200"):
        res = deepcopy(self.default_response)
        definitions = self._schema["definitions"].copy()

        if not definitions.get(self.model_name, None):
            _name = self.model.__name__
            schm = {"$ref": '#/components/schemas/'+_name}
        else:
            schm = definitions.pop(self.model_name)

        res["responses"].setdefault(default_status, {}).update({
            "content": {
                'application/json': {
                    "schema": schm
                }
            }
        })
        res["definitions"] = definitions
        return res


class _ParametersInjections(object):
    function_caller = None

    def __init__(self, base_function: Callable,
                 parser: ParametersParserBase,
                 _parser_type: ParseType,
                 _model_name: str = None,
                 _model: BaseModel = None,
                 **params):
        self.fn_caller = None
        self.base_function = base_function
        self._parsers = {
           # ParseType.Header: Parameters(ParseType.Header, parser), 
        }
        self._parsers_response = Parameters(ParseType.Response, parser)
        self.parser = parser
        self._parser_type = _parser_type
        self._model_name = _model_name
        self._model = _model
        self.params = params
        self.overload(_parser_type=_parser_type, _model_name=_model_name, _model=_model, **params)

    def overload(self,
                 _parser_type: ParseType,
                 _model_name: str = None,
                 _model: BaseModel = None,
                 **params):

        if not _model_name and not _model and len(params) >= 1:
            _mn = list(params)[0]
            _m = params[_mn]
            if not isinstance(_m, tuple) and issubclass(_m, BaseModel):
                _model_name = _mn
                _model = _m
                
        # Si se debe configura la respuesta
        if _parser_type == ParseType.Response:
            _parser = self._parsers_response
        else:
            _parser = self._parsers.setdefault(_parser_type, Parameters(
                _parser_type, self.parser))

        _parser.update_fields(**params)

        if _model_name:
            _parser.model_name = _model_name

        if _model and issubclass(_model, BaseModel):
            _parser.set_model(_model)

    @staticmethod
    def create_update(
            base_function: Callable,  
            parser: ParametersParserBase,   
            _parser_type: ParseType,
            _model_name: str = None,  
            _model: BaseModel = None,  
            **params):

        if getattr(base_function, "_parameters_injector", None):
            base_function._parameters_injector.overload(
                _parser_type=_parser_type, _model_name=_model_name, _model=_model, **params)
            return base_function

        else:
            f = _ParametersInjections(
                base_function=base_function, parser=parser, _parser_type=_parser_type,
                _model_name=_model_name, _model=_model, **params)
            return f.create_caller()

    def create_caller(self):
        argspec = inspect.getfullargspec(self.base_function)
        has_kw = argspec.varkw is not None
        is_coroutine = asyncio.iscoroutinefunction(self.base_function)

        endpoint_signature = inspect.signature(self.base_function)
        arguments = set(argspec.args + argspec.kwonlyargs)
        argshits = set(argspec.args).intersection(set(endpoint_signature.parameters))
        arguments = arguments.intersection(set(endpoint_signature.parameters))

        @wraps(self.base_function)
        async def exec_fn(*args, **kw):            
            all_args = dict(zip(argshits, args))
            all_args.update(kw) 

            ctx = self.parser.get_context(self.base_function, args, kw)
            try:
                for k, p in self._parsers.items():
                    if p.model: 
                        data = await p.load(ctx, args, kw) 
                        all_args.update(
                            **{p.model_name: data},
                            **{f: getattr(data, f, None) for f in list(data.__fields__)})
                
                if has_kw:
                    partial_args = all_args
                else:
                    partial_args = {k: all_args.get(k, None) for k in arguments}

                if is_coroutine:
                    res = await self.base_function(**partial_args)
                else:
                    res = self.base_function(**partial_args)

                return await self.parser.send_response(context=ctx, data=res)

            except ValidationError as e:
                return await self.parser.send_error(context=ctx, error=e.errors()) 

            except Exception as e:
                return await self.parser.send_error(context=ctx, error=e)

        exec_fn._parameters_injector = self
        return exec_fn


class Parser:
    def __init__(self,  parambase: ParametersParserBase):
        self.parambase = parambase

    def response(self, _model_name=None, _model=None, **fields):
        return self.expect(ParseType.Response, _model_name, _model, **fields)

    def path(self, _model_name=None, _model=None, **fields):
        return self.expect(ParseType.Path, _model_name, _model, **fields)

    def body(self, _model_name=None, _model=None, **fields):
        return self.expect(ParseType.Body, _model_name, _model, **fields)

    def form(self, _model_name=None, _model=None, **fields):
        return self.expect(ParseType.Form, _model_name, _model, **fields)

    def json(self, _model_name=None, _model=None, **fields):
        return self.expect(ParseType.Body, _model_name, _model, **fields)

    def query(self, _model_name=None, _model=None, **fields):
        return self.expect(ParseType.Query, _model_name, _model, **fields)

    def expect(self, _parser_type: ParseType, _model_name: str = None, _model=None,  **fields):
        def decorator(func: Union[Callable, _ParametersInjections]) -> Callable:
            f = _ParametersInjections.create_update(base_function=func, 
                                                    parser=self.parambase,
                                                    _parser_type=_parser_type,
                                                    _model_name=_model_name, 
                                                    _model=_model,
                                                    **fields)
            return f
        return decorator

    def annotation(self, func: Callable) -> Callable:
        endpoint_signature = inspect.signature(func)
        signature_params = endpoint_signature.parameters

        fields = get_schema_fields(func)
        f = func
        for n, ad in fields.items():
            a, d = ad
            if getattr(d, "in_", None):
                if d.extra.get("embed", False):
                    f = _ParametersInjections.create_update(
                        base_function=f,
                        parser=self.parambase,
                        _parser_type=d.in_,
                        _model_name=n,
                        _model=a)
                else: 
                    f = _ParametersInjections.create_update(
                        base_function=f,
                        parser=self.parambase,
                        _parser_type=d.in_,
                        **{n: ad})
        return f

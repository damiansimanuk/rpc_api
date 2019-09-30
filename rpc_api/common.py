from typing import (Any, Callable, Dict, List, Optional, Sequence, Set, Type, Union, get_type_hints)
import inspect
from pydantic import BaseModel, create_model, ValidationError, Schema
from pydantic.schema import schema as pdschema
from enum import Enum
import sys


class ParseType(str, Enum):
    Path = "path"
    Query = "query"
    Form = "form"
    Body = "body"
    Response = "response"
    Header = "header"
    Cookie = "cookie"


class Path(Schema):
    in_ = ParseType.Path


class Query(Schema):
    in_ = ParseType.Query


class Form(Schema):
    in_ = ParseType.Form


class Body(Schema):
    in_ = ParseType.Body


class Header(Schema):
    in_ = ParseType.Header


class Cookie(Schema):
    in_ = ParseType.Cookie


class ParamExpect:
    def __new__(cls,
                type: Any,
                default: Any,
                *,
                alias: str = None,
                title: str = None,
                description: str = None,
                const: bool = None,
                gt: float = None,
                ge: float = None,
                lt: float = None,
                le: float = None,
                multiple_of: float = None,
                min_items: int = None,
                max_items: int = None,
                min_length: int = None,
                max_length: int = None,
                regex: str = None,
                deprecated: str = None,
                **extra: Any,):
        s = Schema(
            default=default,
            alias=alias,
            title=title,
            description=description,
            const=const,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            multiple_of=multiple_of,
            min_items=min_items,
            max_items=max_items,
            min_length=min_length,
            max_length=max_length,
            regex=regex,
            deprecated=deprecated,
            **extra,
        )
        return (type, s)


def get_schema_fields(call: Callable):
    endpoint_signature = inspect.signature(call)
    signature_params = endpoint_signature.parameters
    argspec = inspect.getfullargspec(call)
    fields = {}
    for param_name in (argspec.args + argspec.kwonlyargs):
        param = signature_params.get(param_name, None)
        if not param:
            continue

        if param.annotation is not param.empty:
            if param.default is not param.empty:
                fields[param_name] = (param.annotation, param.default)
            else:
                fields[param_name] = (param.annotation, ...)
        else:
            if param.default is not param.empty:
                fields[param_name] = (Any,  param.default)
            else:
                fields[param_name] = (Any, ...)

    return fields


def get_caller_instance(obj):
    f = sys._getframe(2)
    while f is not None:
        s = f.f_locals.get('self', None)
        if isinstance(s, obj):
            return s
        # co = f.f_code
        # print("co ", co, f.f_trace, f.f_locals.get('self', None))
        f = f.f_back

    return None

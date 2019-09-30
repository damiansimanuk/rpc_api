from typing import Dict, Any, Callable, List
from rpc_api.base_param import ParametersParserBase
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, Response
from starlette import status


class StarletteParameters(ParametersParserBase):

    def get_context(self, base_function: Callable, args: List, kwargs: Dict) -> Request:
        if isinstance(args[0], Request):
            return args[0]

        return args[1]

    async def get_parameters(self, context: Any, parser_type, args: List,
                             kwargs: Dict) -> Dict:
        raise NotImplemented

    async def get_path_parameters(self, context: Request, args: List, kwargs: Dict) -> Dict:
        """Pull a value from the request's ``path_params``."""
        return context.path_params

    async def get_query_parameters(self, context: Request, args: List, kwargs: Dict) -> Dict:
        """Pull a querystring value from the request."""
        return context.query_params._dict

    async def get_headers_parameters(self, context: Request, args: List, kwargs: Dict) -> Dict:
        """Pull a value from the header data."""
        return context.headers

    async def get_cookies_parameters(self, context: Request, args: List, kwargs: Dict) -> Dict:
        """Pull a value from the cookiejar."""
        return context.cookies

    async def get_body_parameters(self, context: Request, args: List, kwargs: Dict) -> Dict:
        """Pull a json value from the request."""
        try:
            return await context.json()
        except:
            return {}

    async def get_form_parameters(self, context: Request, args: List, kwargs: Dict) -> Dict:
        data = await context.form()
        return data._dict

    async def send_response(self, context: Request, data) -> Dict:
        """Pull a form value from the request."""
        print("context.method", context.method)
        if isinstance(data, Response):
            return data

        status_code = 201 if context.method in ("POST") else 200
        if isinstance(data, tuple) and len(data) > 1:
            status_code = data[1]
            data = data[0]

        if isinstance(data, dict):
            resp = JSONResponse(data)
        else:
            resp = JSONResponse({"data": data})
        resp.status_code = status_code
        return resp

    async def send_error(self, context: Any, error) -> Dict:
        """Pull a form value from the request."""
        if isinstance(error, (dict, str)):
            res = JSONResponse({"error": error})
        else:
            res = JSONResponse({"error": str(error)})
        res.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return res

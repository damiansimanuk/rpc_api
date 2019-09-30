import typing
from starlette.routing import BaseRoute
from starlette.schemas import BaseSchemaGenerator
from starlette.responses import JSONResponse, HTMLResponse, Response
from starlette.requests import Request
from pprint import pprint


class SchemaGenerator(BaseSchemaGenerator):
    def __init__(self, base_schema: dict) -> None:
        self.base_schema = base_schema

    def get_schema(self, routes: typing.List[BaseRoute]) -> dict:
        schema = dict(self.base_schema)
        schema.setdefault("paths", {})
        schema.setdefault("components", {})
        schema["components"].setdefault("schemas", {})
        endpoints_info = self.get_endpoints(routes)

        for endpoint in endpoints_info:

            parsed = self.parse_docstring(endpoint.func)

            if hasattr(endpoint.func, "_parameters_injector"):
                parsed.setdefault("parameters", [])
                parsed.setdefault("responses", {})
                parsed.setdefault("requestBody", {})

                for k, p in endpoint.func._parameters_injector._parsers.items():
                    res = p.spec()
                    # pprint(res)

                    definitions = res.pop("definitions")
                    schema["components"]["schemas"].update(definitions)
                    parsed["responses"].update(**res["responses"])
                    parsed["parameters"].extend(res["parameters"])
                    parsed["requestBody"].setdefault("content", {}).update(
                        res["requestBody"]["content"])

                if endpoint.func._parameters_injector._parsers_response.model:
                    default_status = "200"
                    if endpoint.http_method == "post":
                        default_status = "201"

                    res = endpoint.func._parameters_injector._parsers_response.spec(default_status)

                    # pprint(res)
                    definitions = res.pop("definitions")
                    schema["components"]["schemas"].update(definitions)
                    parsed["responses"].update(**res["responses"])

            if not parsed:
                parsed["summary"] = "Undocumented"

            if endpoint.path not in schema["paths"]:
                schema["paths"][endpoint.path] = {}

            schema["paths"][endpoint.path][endpoint.http_method] = parsed

        return schema

    def OpenAPIResponse(self, request: Request) -> Response:
        routes = request.app.routes
        schema = self.get_schema(routes=routes)
        return JSONResponse(schema)

    def SwaggerUIResponse(
        self,
        *,
        openapi_url: str,
        title: str,
        swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui-bundle.js",
        swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui.css",
        swagger_favicon_url: str = "https://fastapi.tiangolo.com/img/favicon.png",
        oauth2_redirect_url: typing.Optional[str] = None,
    ) -> HTMLResponse:

        html = f"""
        <! doctype html>
        <html>
        <head>
        <link type="text/css" rel="stylesheet" href="{swagger_css_url}">
        <link rel="shortcut icon" href="{swagger_favicon_url}">
        <title>{title}</title>
        </head>
        <body>
        <div id="swagger-ui">
        </div>
        <script src="{swagger_js_url}"></script>
        <!-- `SwaggerUIBundle` is now available on the page -->
        <script>
        const ui = SwaggerUIBundle({{
            url: '{openapi_url}',
        """

        if oauth2_redirect_url:
            html += f"oauth2RedirectUrl: window.location.origin + '{oauth2_redirect_url}',"

        html += """
            dom_id: '#swagger-ui',
            presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIBundle.SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            deepLinking: true
        })
        </script>
        </body>
        </html>
        """
        return HTMLResponse(html)

from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse
from rpc_api.base_param import Parser
from rpc_api.common import ParseType, ParamExpect, Query, Path, Body
from rpc_api.extension.starlette_param import StarletteParameters
from rpc_api.extension.starlette_schema import SchemaGenerator
from pydantic import BaseModel
from typing import (Any, Callable, Dict, List, Optional, Sequence, Set, Type, Union, get_type_hints)
from pprint import pprint
from starlette.middleware.base import BaseHTTPMiddleware
from json import dumps
from starlette.websockets import WebSocket
from starlette.endpoints import WebSocketEndpoint
from rpc_api.extension.jsonrpcserver_dispatcher import dispatch, Caller
from rpc_api.extension.jsonrpcserver_methods import RpcJsonMethods
from rpc_api.pubsub import EventsEmmitterHub
import logging

logger = logging.getLogger("rpc_api.jsonrpcserver")
request_handler = logging.StreamHandler()
logger.addHandler(request_handler)
logger.setLevel(logging.DEBUG)


param = Parser(StarletteParameters())

app = Starlette()


async def invoke_query(query):
    print("")
    print("----------------------")
    print(">>> Query::")
    pprint(query)
    response = await dispatch(dumps(query), rpc_methods, debug=False)
    print("----------------------")
    print("<<< Result...")
    if response.wanted:
        ret = response.deserialized()
        pprint(ret)
        return ret


htmlecho = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws/echo");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


htmlrpc = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <div>
            <select id="mySelect" style="width: 150px;">
                <option>Call</option>
                <option>subscribe</option>
                <option>unsubscribe</option>
                <option>notify</option>
            </select>
            <button type="button" onclick="myFunction()">Test</button>
        </div>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="on" style="width: 700px;">
            <button>Send</button>
        </form>
        <div id="div-msg" style="height: 300px; overflow: auto; margin-top: 20px;">
            <ul id='messages'>
            </ul>
        </div>
        <script>
            var ws = new WebSocket("ws://localhost:8000/ws");

            function add_msg(data) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(data)
                message.appendChild(content)
                messages.appendChild(message)

                var divmsg = document.getElementById('div-msg');                
                divmsg.scrollTop = divmsg.scrollHeight;
            }

            ws.onmessage = function(event) { 
                add_msg('Receive: '+ event.data);
            };

            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                add_msg('Send: '+ input.value);
                // input.value = ''
                event.preventDefault()
            };

            function myFunction() {
                var x = document.getElementById("mySelect").selectedIndex; 
                var input = document.getElementById("messageText")
                switch (x)
                {
                    case 0:
                        input.value = '{"jsonrpc": "2.0", "method": "call1", "params": {"name": "nombre X", "value": 45.89}, "id": 11}'
                        break;
                    case 1:
                        input.value = '{"jsonrpc": "2.0", "method": "rpc.on", "params": ["evento1"], "id": 12}'
                        break;
                    case 2:
                        input.value = '{"jsonrpc": "2.0", "method": "rpc.off", "params": ["evento1"], "id": 13}'
                        break;
                    case 3:
                        input.value = '{"jsonrpc": "2.0", "method": "notify1", "params": {"values":  "nombre X 45.89" }}'
                        break;
                    case 4:    
                        input.value = '{"jsonrpc": "2.0", "method": "Prueba2", "params": {"name": "nombre X", "value": 45.89}, "id": 14}'
                        break;
                }
                ws.send(input.value);
                add_msg('Send: '+ input.value);
            }
        </script>
    </body>
</html>
"""

rpc_methods = RpcJsonMethods()


@app.route("/echo")
async def get(request):
    return HTMLResponse(htmlecho)


@app.route("/rpc")
async def get(request):
    return HTMLResponse(htmlrpc)


@app.websocket_route("/ws/echo")
class Echo(WebSocketEndpoint):
    encoding = "text"

    async def on_receive(self, websocket, data):
        await websocket.send_text(f"Message text was: {data}")


@app.websocket_route("/ws")
class RpcJsonWs(WebSocketEndpoint, EventsEmmitterHub):

    encoding = "text"

    async def write_notifciation(self, notifciation):
        await self.transport.send_json(notifciation)

    def get_transport(self):
        return self

    async def on_connect(self, websocket: WebSocket) -> None:
        """Override to handle an incoming websocket connection"""
        # print("on_connect", websocket)
        self.transport = websocket
        self.caller = Caller()
        self.rpc = RpcJsonMethods(self, **rpc_methods.items)
        await websocket.accept()

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        # print("on_disconnect", websocket)
        await self.remove_transport()

    async def on_receive(self, websocket, data):
        # print("on_receive", websocket, data)
        response = await dispatch(data, self.rpc, caller=self.caller, debug=True)
        if response.wanted:
            await websocket.send_json(response.deserialized())


class Bar(BaseModel):
    countBar: int = None


@app.route("/rpc_call1/{name}")
@param.annotation
@rpc_methods.register("call1")
async def rpc_call1(name: str = Path("pepe"), value: float = Query(2.1)):
    return dict(name=name, value=value)


@app.route("/rpc_notify1")
@param.annotation
@rpc_methods.register("notify1")
async def rpc_notify1(values: str = Query("Notificacion Demo")):
    print("rpc_notify1 -------------------------", values)
    res = dict(values=values)
    await rpc_methods.event_emit("evento1", res)
    return res


@app.route("/execute/{function_name}")
@param.path(function_name=ParamExpect(str, "Prueba2"))
@param.query(name=ParamExpect(str, "pepe"), value=ParamExpect(float, 3))
async def path_query(function_name: str, name: str, value: float):
    # return JSONResponse({"message": f"name:{name}:{type(name)} function_name:{function_name} - value:{value}:{type(value)} Retorno:{None}"})
    res = await rpc_methods.items[function_name](name=name, value=value)
    query = {
        "jsonrpc": "2.0",
        "method": function_name,
        "params": {"name": name, "value": value},
        "id": 13
    }
    res = await invoke_query(query)
    print(res)
    return JSONResponse({"message": f"name:{name}:{type(name)} - function_name:{function_name} - value:{value}:{type(value)} Retorno:{res}"})


@app.route("/path_query2/{name}")
@param.annotation
@rpc_methods.register("Prueba2")
async def path_query(request: Any = None, name: str = Path("pepe"), value: float = Query(2.1), per_page: int = Query(100), page: int = Query(1), **kw):
    return {"message": f"name:{name}:{type(name)} - value:{value}:{type(value)} per_page:{per_page} page:{page} request:{type(request)} kw:{kw} "}


@app.route("/json", methods=["POST"])
@param.json(bar=Bar)
@param.response(bar=Bar)
async def json3(bar: Bar):
    return bar.dict()


@app.route("/json2", methods=["POST"])
@param.annotation
async def json(request, *, bar: Bar = Body(..., embed=False)):
    return {"message": f"bar:{bar}"}

schemas = SchemaGenerator(
    {"openapi": "3.0.0", "info": {"title": "Example API", "version": "1.0"}}
)


@app.route("/schema", methods=["GET"], include_in_schema=False)
def openapi_schema(request):
    return schemas.OpenAPIResponse(request)


@app.route("/docs", methods=["GET"])
def list_users(request):
    return schemas.SwaggerUIResponse(openapi_url="/schema", title="titulo - Swagger UI")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8081)

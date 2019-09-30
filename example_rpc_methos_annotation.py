import asyncio
from rpc_api.common import ParseType, get_schema_fields, Query
# from rpc_api.jsonrpcserver_annotation import RpcJsonMethods, register
# from jsonrpcserver.async_dispatcher import dispatch
from rpc_api.extension.jsonrpcserver_dispatcher import dispatch
from rpc_api.extension.jsonrpcserver_methods import RpcJsonMethods
from typing import Callable, Dict, Any, List, Union, Optional
from json import dumps
import logging
from pprint import pprint
from jsonrpcserver.response import ErrorResponse, BatchResponse
import pydoc
import io

logger = logging.getLogger("rpc_api.jsonrpcserver_annotation")
request_handler = logging.StreamHandler() 
logger.addHandler(request_handler)
logger.setLevel(logging.DEBUG)


rpc_methods = RpcJsonMethods()

async def invoke_query(query):
    print("")
    print("----------------------")
    print(">>> Query::")
    pprint(query)
    response = await dispatch(dumps(query), rpc_methods, debug=False)    
    print("----------------------")
    print("<<< Result...")
    if response.wanted:
        # pprint(response.deserialized())
        if isinstance(response, BatchResponse): 
            for r in response.responses:
                if isinstance(r, ErrorResponse): 
                    print(f"- ErrorResponse:{r.id}  code:{r.code}, message:'{r.message}', data:'{r.data}'")
                else:
                    pprint(r.deserialized())

        elif isinstance(response, ErrorResponse): 
            print(f"- ErrorResponse:{response.id} code:{response.code}, message:'{response.message}', data:'{response.data}'")

        else:
            pprint(response.deserialized())
            

async def Example():
    

    @rpc_methods.register()
    async def Prueba2(count: int,
                      *,
                      vIntSchema: int=Query(..., description="mi abuela"),
                      vInt: Union[int, float]=1,
                      vStr: str="hola") -> str:
        a = 3/vInt
        return {"count":count,"vIntSchema":vIntSchema ,"vInt":vInt,"vStr":vStr,"a":a}

    @rpc_methods.register()
    async def Echo(a=1, *args, **kwargs):
        return (a, args, kwargs)

 
    query1 = [{
        "jsonrpc": "2.0", 
        "method": "Prueba2", 
        "params": {
            "count": 5, 
            "vIntSchema": "2a0", 
        }, 
        "id": 10
        },{
        "jsonrpc": "2.0", 
        "method": "Prueba2", 
        "params": {
            "count": 5, 
            "vIntSchema": "20", 
        }, 
        "id": 11
        },{
        "jsonrpc": "2.0", 
        "method": "Prueba2", 
        "params": {
            "count": 5, 
            "vIntSchema": "20",
            "vInt" : 0,
            "variableSkip" : 2
        }, 
        "id": 12
        }]

    query2 = {
        "jsonrpc": "2.0", 
        "method": "Prueba2", 
        "params": {
            "count": 5, 
            "vIntSchema": "20",
            "vStrintDiscard": "Extra argument discard"
        }, 
        "id": 13
        }

    query3 = {
        "jsonrpc": "2.0", 
        "method": "Prueba2", 
        "params": { 
            "vIntSchema": "2a0", 
        }, 
        "id": 14
        }

    query4 = {
        "jsonrpc": "2.0", 
        "method": "Echo", 
        "params": {
            "count": 5, 
            "vIntSchema": "20",
            "vStrintDiscard": "Extra argument discard"
        }, 
        "id": 13
        }

    query5 = {
        "jsonrpc": "2.0", 
        "method": "Echo", 
        "params": [11,2,3], 
        "id": 13
        }

    await invoke_query(query1)
    await invoke_query(query2)
    await invoke_query(query3)
    await invoke_query(query4)
    await invoke_query(query5)

    await invoke_query({
        "jsonrpc": "2.0", 
        "method": "list", 
        "params": ["as"], 
        "id": 0
        })

    res = {}
    for n, m in rpc_methods.items.items():
        out = io.StringIO()
        pydoc.Helper(output=out)(m)
        res[n] = str(out.getvalue())
        out.close()
        # print(n)
        # print(res[n])
    # pprint(res)



if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(Example())

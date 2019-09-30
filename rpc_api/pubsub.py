import asyncio
from typing import Set, Dict, Union, List, NamedTuple
import logging
from pprint import pprint

logger = logging.getLogger(__name__ + ".pubsub")


class TaskQueue:
    def __init__(self, task: asyncio.Task, queue: asyncio.Queue):
        self.task: asyncio.Task = task
        self.queue: asyncio.Queue = queue


class Hub:

    def __init__(self):
        self._key_subs: Dict[str, Set] = {}

    def publish(self, keys: Union[List, Set, str], message: str):
        if isinstance(keys, str):
            keys = list((keys,))
        elif not isinstance(keys, list):
            keys = list(keys)

        for k in keys:
            if k in self._key_subs:
                for taskqueue in list(self._key_subs[k]):
                    if taskqueue.task.done():
                        self.remove_all(taskqueue)
                    else:
                        taskqueue.queue.put_nowait(message)

    def remove_all(self, taskqueue: TaskQueue):
        for k in self._key_subs:
            self._key_subs[k].remove(taskqueue)

    def remove(self, keys: Union[List, Set, str],  taskqueue: TaskQueue):
        if isinstance(keys, str):
            keys = list((keys,))
        elif not isinstance(keys, list):
            keys = list(keys)

        for k in keys:
            if k in self._key_subs:
                self._key_subs[k].remove(taskqueue)

    def add(self, keys: Union[List, Set, str],  taskqueue: TaskQueue):
        if isinstance(keys, str):
            keys = list((keys,))
        elif not isinstance(keys, list):
            keys = list(keys)

        for k in keys:
            if k not in self._key_subs:
                self._key_subs.update(**{k: set()})

            self._key_subs[k].add(taskqueue)

    def subscribe(self, keys: Union[List, Set, str] = None):
        return Subscribe(self, keys)


class Subscribe:

    def __init__(self, hub: Hub, keys: Union[List, Set, str] = None):
        self.hub = hub
        self.taskqueue = TaskQueue(asyncio.Task.current_task(), asyncio.Queue())
        if keys:
            self.subscribe(keys)

    @property
    def queue(self) -> asyncio.Queue:
        return self.taskqueue.queue

    @property
    def task(self) -> asyncio.Task:
        return self.taskqueue.task

    def subscribe(self,  keys: Union[List, Set, str]):
        self.hub.add(keys, self.taskqueue)

    def unsubscribe(self, keys: Union[List, Set, str]):
        self.hub.remove(keys, self.taskqueue)

    def unsubscribe_all(self):
        self.hub.remove_all(self.taskqueue)


class EventsEmmitterBase:
    EVENTS = {}

    async def write_transport(self, transport, notifciation):
        # tornado websocket
        # transport.write_message(notification)

        # starlette websocket
        # transport.send_json(notification)
        raise NotImplemented

    def get_transport(self):
        # from tornado.websocket import WebSocketHandler
        # return get_caller_instance(WebSocketHandler)
        raise NotImplemented

    def remove_transport(self):
        transport = self.get_transport()
        self.event_remove_transport_all(transport)

    async def rpc_on(self, *events: tuple) -> dict:
        logger.info("rpc.on: %r", events)
        transport = self.get_transport()
        for en in events:
            logger.info("rpc.on: %r", events)
            await self.event_add(en, transport)
        return {"event_name": "ok"}

    async def rpc_off(self, *events):
        logger.debug("rpc.off: %r", events)
        transport = self.get_transport()
        for en in events:
            await self.event_remove(en, transport)
        return {"event_name": "ok"}

    async def event_add(self, event: str, transport) -> None:
        logger.info("event_add %r", EventsEmmitterBase.EVENTS)
        EventsEmmitterBase.EVENTS[event] = EventsEmmitterBase.EVENTS.get(event, set()) | set([transport])

    async def event_remove(self, event: str, transport) -> None:
        tps = EventsEmmitterBase.EVENTS.get(event, None)
        if tps is not None:
            tps.remove(transport)

        if not EventsEmmitterBase.EVENTS[event]:
            del EventsEmmitterBase.EVENTS[event]

    async def event_remove_transport_all(self, transport) -> None:
        for en, tps in EventsEmmitterBase.EVENTS.items():
            if transport in tps:
                tps.remove(transport)

        logger.info("event_remove_transport_all %r ", EventsEmmitterBase.EVENTS.keys())

    async def event_emit(event: str, *params) -> int:
        logger.info("Emit '%s' => %r", event, params)

        if event not in EventsEmmitterBase.EVENTS.keys():
            return -1

        if not EventsEmmitterBase.EVENTS[event]:
            del EventsEmmitterBase.EVENTS[event]
            return -1

        count = 0
        notification = {'notification': event, 'params': params, "jsonrpc": '2.0'}
        logger.debug("event_emit %r %r", EventsEmmitterBase.EVENTS.keys(), notification)

        for transport in EventsEmmitterBase.EVENTS[event]:
            if hasattr(transport, "write_message"):
                try:
                    await self.write_transport(transport, notification)
                    count += 1
                except Exception as e:
                    logger.warning("Exception: %r", e)

        return count


class EventsEmmitterHub:
    EVENTS = {}

    def get_transport(self):
        # from tornado.websocket import WebSocketHandler
        # return get_caller_instance(WebSocketHandler)
        raise NotImplemented

    async def write_notifciation(self, notifciation):
        # tornado websocket
        # self.transport.write_message(notification)

        # starlette websocket
        # self.transport.send_json(notification)
        raise NotImplemented

    async def remove_transport(self):
        await EventsEmmitterHub.event_remove_transport_all(self.get_transport())

    async def rpc_on(self, *events: tuple) -> dict:
        logger.info("rpc.on: %r", events)
        transport = self.get_transport()
        for en in events:
            logger.info("rpc.on: %r %r", events, transport)
            await EventsEmmitterHub.event_add(transport, en)
        return {"event_name": "ok"}

    async def rpc_off(self, *events):
        logger.debug("rpc.off: %r", events)
        transport = self.get_transport()
        for en in events:
            await EventsEmmitterHub.event_remove(transport, en)
        return {"event_name": "ok"}

    @staticmethod
    async def event_add(transport, event: str) -> None:
        logger.info("event_add %r", EventsEmmitterBase.EVENTS)
        EventsEmmitterBase.EVENTS[event] = EventsEmmitterBase.EVENTS.get(event, set()) | set([transport])

    @staticmethod
    async def event_remove(transport, event: str) -> None:
        tps = EventsEmmitterBase.EVENTS.get(event, None)
        if tps is not None:
            tps.remove(transport)

        if not EventsEmmitterBase.EVENTS[event]:
            del EventsEmmitterBase.EVENTS[event]

    @staticmethod
    async def event_remove_transport_all(transport) -> None:
        for en, tps in EventsEmmitterBase.EVENTS.items():
            if transport in tps:
                tps.remove(transport)

        logger.info("event_remove_transport_all %r ", EventsEmmitterBase.EVENTS.keys())

    @staticmethod
    async def event_emit(event: str, params) -> int:
        if not isinstance(params, (dict, list)):
            params = list(params)
        logger.info("Emit '%s' => %r", event, params)
        pprint(EventsEmmitterBase.EVENTS)

        if event not in EventsEmmitterBase.EVENTS.keys():
            return -1

        if not EventsEmmitterBase.EVENTS[event]:
            del EventsEmmitterBase.EVENTS[event]
            return -1

        count = 0
        notification = {'notification': event, 'params': params, "jsonrpc": '2.0'}
        logger.debug("event_emit %r %r", EventsEmmitterBase.EVENTS.keys(), notification)

        for transport in EventsEmmitterBase.EVENTS[event]:
            try:
                await transport.write_notifciation(notification)
                count += 1
            except Exception as e:
                await EventsEmmitterBase.event_remove(event, transport)
                logger.warning("Exception: %r", e)

        return count


def Example2():
    from datetime import datetime

    global hub
    hub = Hub()

    async def subscriptions(id):
        task = asyncio.Task.current_task()
        print("task, id", id, task)

        sub = hub.subscribe(keys=["hola"])

        while True:
            msg = await sub.queue.get()
            print("sub --- id:%d %r" % (id,  msg))

    async def publisher(task, msg="msg base"):
        while True:
            hub.publish(["hola"], msg+str(datetime.now()))
            await asyncio.sleep(3.0)
            hub.publish(["hola"], msg+str(datetime.now()))
            await asyncio.sleep(3.0)
            hub.publish(["hola"], msg+str(datetime.now()))
            await asyncio.sleep(3.0)
            task.cancel()

    loop = asyncio.get_event_loop()

    task = loop.create_task(subscriptions(2))
    print("task 2:", task.done())
    loop.create_task(subscriptions(3))
    asyncio.shield(subscriptions(4))

    asyncio.shield(publisher(task))

    # loop.run_until_complete(publisher(task))
    loop.run_forever()


if __name__ == '__main__':
    try:
        Example2()
    except KeyboardInterrupt:
        print("exit")
        pass

    loop = asyncio.get_event_loop()
    loop.close()

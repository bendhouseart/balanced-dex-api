from fastapi import APIRouter, WebSocket
from fastapi.responses import HTMLResponse
from starlette.endpoints import WebSocketEndpoint
# from starlette.middleware.cors import CORSMiddleware
import asyncio
from typing import List
from aiokafka import AIOKafkaConsumer
from loguru import logger
import typing
from pydantic import BaseModel
from typing import Optional
import redis
from starlette.websockets import WebSocketDisconnect

router = APIRouter()
# app.add_middleware(CORSMiddleware, allow_origins=["*"])

@router.get("/")
async def get():
    return HTMLResponse(html)

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <h2>Your ID: <span id="ws-id"></span></h2>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var client_id = Date.now()
            document.querySelector("#ws-id").textContent = client_id;
            var ws = new WebSocket(`ws://localhost/api/v1/dex/ws/${client_id}`);
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


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        print("send_personal_message: " + message)
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        print("broadcast:", message)
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


# # web socket chat
@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client #{client_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} left the chat")


# # kafka topic consumption
async def consume(consumer, topicname):
    async for msg in consumer:
        print("for msg in consumer: ", msg)
        return msg.value.decode()


@router.websocket_route("/consumer/{clientid}/{topicname}")
class WebsocketConsumer(WebSocketEndpoint):
    """
    Consume messages from <topicname>
    This will start a Kafka Consumer for a topic
    And this path operation will:
    * return ConsumerResponse
    """
    KAFKA_INSTANCE = "kafka:9092"
    PROJECT_NAME = "dex-api"

    async def on_connect(self, websocket: WebSocket) -> None:
        topicname = websocket["path"].split("/")[3]  # until I figure out an alternative
        clientid = websocket["path"].split("/")[2]

        await manager.connect(websocket)
        await manager.broadcast(f"Client connected : {clientid}")

        loop = asyncio.get_event_loop()
        self.consumer = AIOKafkaConsumer(
            topicname,
            loop=loop,
            client_id=self.PROJECT_NAME,
            bootstrap_servers=self.KAFKA_INSTANCE,
            enable_auto_commit=False,
        )

        await self.consumer.start()

        self.consumer_task = asyncio.create_task(
            self.send_consumer_message(websocket=websocket, topicname=topicname)
        )

        logger.info("connected")

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        clientid = websocket["path"].split("/")[2]
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{clientid} left")

        self.consumer_task.cancel()
        await self.consumer.stop()
        logger.info(f"counter: {self.counter}")
        logger.info("disconnected")
        logger.info("consumer stopped")

    async def on_receive(self, websocket: WebSocket, data: typing.Any) -> None:
        clientid = websocket["path"].split("/")[2]
        await manager.send_personal_message(f"You wrote: {data}", websocket)
        await manager.broadcast(f"Client #{clientid} says: {data}")

    async def send_consumer_message(self, websocket: WebSocket, topicname: str) -> None:
        self.counter = 0
        while True:
            data = await consume(self.consumer, topicname)
            # response = ConsumerResponse(topic=topicname, **json.loads(data))
            logger.info(f"data : {data}")
            await manager.send_personal_message(f"{data}", websocket)
            print("websocket.send_text done")
            self.counter = self.counter + 1


# # ################ mongo db  ################

import motor.motor_asyncio
import pymongo
import urllib.parse
import json

# client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
client = motor.motor_asyncio.AsyncIOMotorClient('mongodb', 27017)


class Person(BaseModel):
    name: str
    phone: Optional[str] = None


# https://motor.readthedocs.io/en/stable/tutorial-asyncio.html
async def do_insert(person: Person):
    document = {
        "name": person.name,
        "phone": person.phone
    }
    result = await client.insight_test.person.insert_one(document)
    return "result", repr(result.inserted_id)


@router.post("/mongo/insert")
async def post(person: Person):
    return await asyncio.wait_for(do_insert(person), 3.0)


async def do_find_one(person: Person):
    document = await client.insight_test.person.find_one({"name": person.name})
    return document


@router.post("/mongo/find_one")
async def post(person: Person):
    x = await asyncio.wait_for(do_find_one(person), 3.0)
    return {"name": x["name"], "phone": x["phone"]}


@router.post("/mongo/find")
async def post(person: Person):
    return await asyncio.wait_for(do_find_one(person), 3.0)
    # x = asyncio.create_task(await do_insert(person))


# # implement other CRUD - # https://motor.readthedocs.io/en/stable/tutorial-asyncio.html
# ######################## end of mongo db ########################

# ################ redis connection ################

class RedisData(BaseModel):
    key: str
    value: Optional[str] = None


# redisClient = redis.Redis(host='default', port=6379, db=0)
redisClient = redis.Redis(host='redis', port=6379, db=0)


@router.post("/redis/set")
async def post(redis_data: RedisData):
    return redisClient.set(redis_data.key, redis_data.value)


@router.post("/redis/get")
async def post(redis_data: RedisData):
    return redisClient.get(redis_data.key)
import asyncio

import typing

from aioredis import Redis
from app.db.redis import get_redis_database
from app.services.trade_service import TradeService
from fastapi import WebSocket, Depends
from app.core.config import settings
from app.db.kafka import create_kafka_consumer
from fastapi import APIRouter
from loguru import logger
from starlette.endpoints import WebSocketEndpoint
from starlette.types import Scope, Receive, Send

router = APIRouter()


@router.websocket_route("/subscribe/market/{market}")
class WebsocketConsumer(WebSocketEndpoint):

    def __init__(self, scope: Scope, receive: Receive, send: Send):
        super().__init__(scope, receive, send)
        loop = asyncio.get_event_loop()
        bootstrap_server = settings.KAFKA_INTERNAL_HOST_PORT
        market = self._get_market(scope["path"])
        topic = f"depth-{market}"
        logger.info(f"subscribing to topic:: {topic}")
        self.kafka_consumer = create_kafka_consumer(loop, f"{topic}_consumer", bootstrap_server)
        self.kafka_consumer.subscribe([topic])

    def _get_market(self, uri_path: str):
        uri_parts = uri_path.split("/")
        market = uri_parts[len(uri_parts) - 1]
        if market == "*":
            return "all"
        return market.lower()

    async def on_connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        await self.kafka_consumer.start()
        self.consumer_task = asyncio.create_task(
            self.send_consumer_message(websocket=websocket)
        )

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        await self.kafka_consumer.stop()
        self.consumer_task.cancel()
        await websocket.close()

    async def on_receive(self, websocket: WebSocket, data: typing.Any) -> None:
        try:
            await websocket.send_text(f"on_receive: {data}")
        except:
            await websocket.close(1)

    async def send_consumer_message(self, websocket: WebSocket) -> None:
        logger.info(f"send_consumer_message for WebsocketConsumer")
        while True:
            key, value = await self.consume(self.kafka_consumer)
            logger.info(f"key, value = await self.consume(self.consumer): {key}, {value}")
            if key is None:
                logger.info(f"consumer received data :: msg is: {value}")
                await self.on_receive(websocket, f"{value}")
            else:
                logger.info(f"consumer received data :: {key}:{value}")
                await self.on_receive(websocket, f"{key}:{value}")
            print("websocket.send_text done")

    async def consume(self, consumer) -> tuple:
        async for msg in consumer:
            print("for msg in consumer: ", msg)
            if msg.key is not None:
                print(f"msg.value is not None, mag.value={msg.value}")
                return msg.key.decode(), msg.value.decode()
            else:
                print("for msg in consumer: sending blank key")
                return None, msg.value.decode()


@router.get("/market/{market}")
async def depth_market(
        market: str,
        redis_client: Redis = Depends(get_redis_database)
):
    # await TradeService.use_db(redis_client, 0)
    pattern = "depth-"
    if market == "*":
        pattern = f"{pattern}*"
    else:
        pattern = f"{pattern}{market}-*"
    pattern = pattern.lower()
    logger.info(f"/{market} - pattern: {pattern}")
    key_value_pairs = await TradeService.get_key_value_pairs(redis_client, pattern)
    return key_value_pairs

import json
import time

import asyncio
from typing import Dict

from aiokafka import AIOKafkaProducer
from app.models.eventlog import EventLog
from app.models.rwmodel import RWModel
from fastapi import APIRouter
from loguru import logger
from pydantic.main import BaseModel
from starlette.background import BackgroundTasks

# from ....models.orders import OrderCreate, Address
from ....core.config import settings

router = APIRouter()
eventer: AIOKafkaProducer = None
run: bool = False


def init():
    global eventer, run
    eventer = get_kafka_producer()
    run = False


def get_kafka_producer() -> AIOKafkaProducer:
    loop = asyncio.get_event_loop()
    producer = AIOKafkaProducer(
        loop=loop,
        client_id="eventer-01",
        bootstrap_servers=settings.KAFKA_INTERNAL_HOST_PORT,
        api_version="2.0.1"
    )
    return producer


router.add_event_handler("startup", init)


@router.get("/")
async def index():
    options = dict()
    options["/start"] = "start producing mock events"  # todo: remove"
    options["/run_once"] = "produce 1 mock event"  # todo: remove
    options["/run"] = "produce mock events at regular interval"  # todo: change to be ready "receive event to api and produce to a topic"
    options["/stop"] = "stop producing mock events"  # todo: remove


def create_eventlog() -> EventLog:
    return EventLog(
        event="OrderCreate",
        order_id=1,
        side=1,
        market="BALICD",
        price="0.0034",
        size="1.223",
        user="hxcd6f04b2a5184715ca89e523b6c823ceef2f9c3d"
    )

@router.get("/start")
async def start_eventer():
    global eventer
    await eventer.start()
    return "eventer started"


@router.get("/run_once")
async def run_once_eventer():
    global eventer, run
    o = create_eventlog()
    sent = await eventer.send(
        "orders",
        value=json.dumps(o.dict()).encode("utf-8")
    )
    result = await sent
    return result


class Item(BaseModel):
    amount: int


@router.post("/run")
async def run_eventer(
        item: Item, background_tasks: BackgroundTasks
) -> Dict[str, str]:
    background_tasks.add_task(background_async, item.amount)
    return {"message": f"producing event every {item.amount} sec"}


@router.get("/stop")
async def stop_eventer():
    global eventer, run
    run = False
    await eventer.stop()
    return "eventer stopped"


async def background_async(amount: int) -> None:
    global eventer, run
    run = True
    try:
        while run:
            o = create_eventlog()
            await eventer.send(
                "orders",
                value=json.dumps(o.dict()).encode("utf-8")
            )
            logger.info(f"EVENTER sent :: {o.schema_json()}")

            logger.debug(f"sleeping {amount}s")
            await asyncio.sleep(amount)
            logger.debug(f"slept {amount}s")
    except:
        await stop_eventer()


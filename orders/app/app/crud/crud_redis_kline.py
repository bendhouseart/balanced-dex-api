import json
from typing import Union

from aioredis import Redis
from app.crud.crud_redis_general import CrudRedisGeneral
from app.models import KLine


class CrudRedisKLine:

    # @staticmethod
    # async def get_key_value_pairs(redis_client: Redis) -> list:
    #     keys = []

    @staticmethod
    async def set_kline_intervals(redis_client, intervals: list):
        kline_interval_json = json.dumps(intervals)
        return await CrudRedisGeneral.set(redis_client, "kline-intervals", kline_interval_json)

    @staticmethod
    async def get_kline_intervals(redis_client) -> list:
        kline_intervals_bytes = await CrudRedisGeneral.get(redis_client, "kline-intervals")
        kline_intervals_str = kline_intervals_bytes.decode("utf-8")
        kline_intervals = json.loads(kline_intervals_str)
        return kline_intervals

    @staticmethod
    async def set_kline(redis_client, key: str, kline: dict):
        kline_json = json.dumps(kline)
        return await CrudRedisGeneral.set(redis_client, key, kline_json)

    @staticmethod
    async def get_kline(redis_client, key: str) -> dict:
        kline_bytes = await CrudRedisGeneral.get(redis_client, key)
        kline_str = kline_bytes.decode("utf-8")
        kline_dict = json.loads(kline_str)
        return kline_dict

    # @staticmethod
    # def create_kline_latest_key(interval_seconds: int) -> str:
    #     return f"kline-{interval_seconds}sec-latest"


    @staticmethod
    def create_kline_key(market: str, interval_seconds: int, start_time: Union[int, str]) -> str:
        if type(start_time) == int:
            return f"kline-{market}-{interval_seconds}-{start_time}"
        else:
            return f"kline-{market}-{interval_seconds}-latest"

    @staticmethod
    def get_market_from_kline_latest_key(kline_latest_key: str) -> str:
        market = ""
        key_parts = kline_latest_key.split("-")
        if len(key_parts) == 4:
            # interval_parts = key_parts[1].split("sec")
            # interval = interval_parts[0]
            market = key_parts[1]
        return market

    @staticmethod
    def get_interval_from_kline_latest_key(kline_latest_key: str) -> int:
        interval = 0
        key_parts = kline_latest_key.split("-")
        if len(key_parts) == 4:
            # interval_parts = key_parts[1].split("sec")
            # interval = interval_parts[0]
            interval = key_parts[2]
        return int(interval)

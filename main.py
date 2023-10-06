#!/usr/bin/env python3
import asyncio

from quart import Quart

from audience import Audience
from robot import create_robot
import secrets
from zoom_monitor import ZoomMonitor


SERVER_PORT = 8090


async def main():
    zoom = ZoomMonitor("https://viam.zoom.us/j/85967895337?pwd=SkQ5dFRGOVlTbnRQNVhIdkJzdmFIUT09")
    async with create_robot(secrets.creds, secrets.address) as robot:
        audience = Audience(robot)
        try:
            while True:
                count = zoom.count_hands()
                await audience.set_count(count)
                await asyncio.sleep(1)
        finally:
            zoom.teardown_method()


if __name__ == "__main__":
    asyncio.run(main())

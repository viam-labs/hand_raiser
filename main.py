#!/usr/bin/env python3
import asyncio
import sys

from audience import Audience
from robot import create_robot
import secrets
from zoom_monitor import ZoomMonitor


SERVER_PORT = 8090


async def main():
    zoom = ZoomMonitor(sys.argv[1])
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

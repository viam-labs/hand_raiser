#!/usr/bin/env python3
import asyncio
import sys

from audience import Audience
from robot import create_robot
from zoom_monitor import monitor_zoom


async def main():
    log_level = int(sys.argv[2]) if len(sys.argv) == 3 else 20
    with monitor_zoom(sys.argv[1], log_level) as zoom:
        async with create_robot(log_level) as robot:
            audience = Audience(robot, log_level)

            while True:
                count = zoom.count_hands()
                await audience.set_count(count)
                await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Shut down cleanly when someone hits control-C.

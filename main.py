#!/usr/bin/env python3
import argparse
import asyncio
import logging
import sys

from audience import Audience
from robot import create_robot
from zoom_monitor import monitor_zoom, MeetingEndedException


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="URL of Zoom meeting. Can be a Google redirect.")
    parser.add_argument("--debug", help="Turn on debugging logs", action="store_true")
    return parser.parse_args()


async def main():
    args = parse_args()
    log_level = logging.DEBUG if args.debug else logging.INFO
    with monitor_zoom(args.url, log_level) as zoom:
        async with create_robot(log_level) as robot:
            audience = Audience(robot, log_level)

            while True:
                count = zoom.count_hands()
                await audience.set_count(count)
                await asyncio.sleep(0.5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, MeetingEndedException):
        pass  # Shut down cleanly

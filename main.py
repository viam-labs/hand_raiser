#!/usr/bin/env python3
import asyncio

from quart import Quart

from audience import Audience
from robot import create_robot
import secrets


SERVER_PORT = 8090


async def main():
    async with create_robot(secrets.creds, secrets.address) as robot:
        app = Quart(__name__)
        audience = Audience(robot)

        @app.route("/count_hands/<int:count>", methods=["POST"])
        async def count_hands(total):
            await audience.set_count(total)
            return "Count has been set to {}\n".format(total)

        await app.run_task(host="0.0.0.0", port=SERVER_PORT)


if __name__ == "__main__":
    asyncio.run(main())

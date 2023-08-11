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

        @app.route("/hand_count/<int:total>", methods=["POST"])
        async def set_hand_count(total):
            await audience.set_count(total)
            return "Count has been set to {}\n".format(total)

        # Use 0.0.0.0 to accept external requests, or 127.0.0.1 to accept only
        # requests originating from within this computer.
        await app.run_task(host="0.0.0.0", port=SERVER_PORT)


if __name__ == "__main__":
    asyncio.run(main())

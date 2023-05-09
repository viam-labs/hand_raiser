#!/usr/bin/env python3
import asyncio
import contextlib
import time

from viam.robot.client import RobotClient
from viam.rpc.dial import DialOptions
from viam.components.board import Board
from viam.components.servo import Servo

import secrets


class Robot:
    UPPER_POSITION = 30
    LOWER_POSITION = 0
    WIGGLE_AMOUNT = 5

    async def connect(self):
        opts = RobotClient.Options(
            refresh_interval=0,
            dial_options=DialOptions(credentials=secrets.creds)
        )
        self.robot = await RobotClient.at_address(secrets.address, opts)
        self.servo = Servo.from_robot(self.robot, "servo")

    async def raise_hand(self):
        await self.servo.move(self.UPPER_POSITION)

    async def lower_hand(self):
        await self.servo.move(self.LOWER_POSITION)

    async def wiggle_hand(self):
        for _ in range(3):
            await self.servo.move(self.UPPER_POSITION + self.WIGGLE_AMOUNT)
            time.sleep(0.3)
            await self.servo.move(self.UPPER_POSITION)
            time.sleep(0.3)


@contextlib.asynccontextmanager
async def makeRobot():
    robot = Robot()
    await robot.connect()
    try:
        yield robot
    finally:
        await robot.robot.close()


async def main():
    async with makeRobot() as robot:
        pi = Board.from_robot(robot.robot, "pi")
        button = await pi.gpio_pin_by_name("18")
        led = await pi.gpio_pin_by_name("16")

        count = 0
        old_state = False
        while True:
            button_state = await button.get()
            if button_state != old_state:
                print("button state has changed!")
                if button_state:
                    count += 1
                    count %= 3
                    if count == 1:
                        await robot.raise_hand()
                    elif count == 2:
                        await robot.wiggle_hand()
                    else:
                        await robot.lower_hand()
            old_state = button_state
            await led.set(button_state)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
import asyncio
import contextlib
import threading
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
    INACTIVITY_PERIOD_S = 15

    async def connect(self):
        opts = RobotClient.Options(
            refresh_interval=0,
            dial_options=DialOptions(credentials=secrets.creds)
        )
        self.robot = await RobotClient.at_address(secrets.address, opts)
        self.servo = Servo.from_robot(self.robot, "servo")

        self.mutex = threading.Lock()
        self.count = 0  # Number of hands currently raised

        # We have a background thread that wiggles the hand when it's been
        # raised for a long time. This condition variable is how to shut that
        # down.
        # It would be intuitive to pass self.mutex to threading.Condition, but
        # that will result in deadlock when you have the mutex and wait for the
        # thread to shut down.
        self.cv = threading.Condition()
        self.should_shutdown_thread = True
        self.thread = None

    def _start_thread(self):
        self.should_shutdown_thread = False
        self.thread = threading.Thread(
                target=asyncio.run,
                args=(self._wiggle_on_inactivity,),
                daemon=True)
        self.thread.start()

    def _stop_thread(self(:
        self.should_shutdown_thread = True
        self.cv.notify()
        self.thread.join()

    async def raise_hand(self):
        with self.mutex:
            self.count += 1
            await self.servo.move(self.UPPER_POSITION)
            if self.count == 1:
                self._start_thread()

    async def lower_hand(self):
        with self.mutex:
            self.count -= 1
            if self.count == 0:
                await self.servo.move(self.LOWER_POSITION)
                self._stop_thread()

    async def set_count(self, new_value):
        with self.mutex:
            if self.count == 0 and new_value > 0:
                self._start_thread()
            self.count = new_value
            if self.count == 0:
                await self.servo.move(self.LOWER_POSITION)
                self._stop_thread()
            else:
                await self.servo.move(self.UPPER_POSITION)

    async def _wiggle_hand(self):
        for _ in range(3):
            await self.servo.move(self.UPPER_POSITION + self.WIGGLE_AMOUNT)
            time.sleep(0.3)
            await self.servo.move(self.UPPER_POSITION)
            time.sleep(0.3)

    async def _wiggle_on_inactivity(self):
        # This is run in a daemon thread. When the hand is raised and nothing
        # has happened for INACTIVITY_PERIOD_S seconds, we wiggle the hand.
        with self.cv:
            while not self.should_shutdown_thread:
                self.cv.wait(timeout=INACTIVITY_PERIOD_S)
                if self.should_shutdown_thread:
                    return
                await self._wiggle_hand()


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

        should_raise = False
        old_state = False
        while True:
            button_state = await button.get()
            if button_state != old_state:
                print("button state has changed!")
                if button_state:
                    should_raise = not should_raise
                    if should_raise:
                        await robot.raise_hand()
                    else:
                        await robot.lower_hand()
            old_state = button_state
            await led.set(button_state)


if __name__ == "__main__":
    asyncio.run(main())

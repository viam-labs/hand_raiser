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
        self._servo = Servo.from_robot(self.robot, "servo")

        self._mutex = threading.Lock()
        self._count = 0  # Number of hands currently raised

        # We have a background thread that wiggles the hand when it's been
        # raised for a long time. This condition variable is how to shut that
        # down.
        # It would be intuitive to pass self._mutex to threading.Condition, but
        # that will result in deadlock when you have the mutex and wait for the
        # thread to shut down.
        self._cv = threading.Condition()
        self._should_shutdown_thread = True
        self._thread = None

    def _start_thread(self):
        self._should_shutdown_thread = False
        if self._thread is not None:
            print("LOGIC BUG: starting the thread when it's already started!?")
        self._thread = threading.Thread(
                target=asyncio.run,
                args=(self._wiggle_on_inactivity(),),
                daemon=True)
        self._thread.start()

    def _stop_thread(self):
        self._should_shutdown_thread = True
        with self._cv:
            self._cv.notify()
        self._thread.join()
        self._thread = None

    async def raise_hand(self):
        with self._mutex:
            self._count += 1
            await self._servo.move(self.UPPER_POSITION)
            if self._count == 1:
                self._start_thread()

    async def lower_hand(self):
        with self._mutex:
            self._count -= 1
            if self._count == 0:
                await self._servo.move(self.LOWER_POSITION)
                self._stop_thread()

    async def set_count(self, new_value):
        with self._mutex:
            should_start_thread = self._count == 0 and new_value > 0
            self._count = new_value
            if self._count == 0:
                await self._servo.move(self.LOWER_POSITION)
                self._stop_thread()
            else:
                await self._servo.move(self.UPPER_POSITION)
                if should_start_thread:
                    self._start_thread()

    async def _wiggle_hand(self):
        for _ in range(3):
            await self._servo.move(self.UPPER_POSITION + self.WIGGLE_AMOUNT)
            time.sleep(0.3)
            await self._servo.move(self.UPPER_POSITION)
            time.sleep(0.3)

    async def _wiggle_on_inactivity(self):
        # This is run in a daemon thread. When the hand is raised and nothing
        # has happened for INACTIVITY_PERIOD_S seconds, we wiggle the hand.
        with self._cv:
            while not self._should_shutdown_thread:
                self._cv.wait(timeout=self.INACTIVITY_PERIOD_S)
                if self._should_shutdown_thread:
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

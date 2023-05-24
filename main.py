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
    INACTIVITY_PERIOD_S = 5

    async def connect(self):
        opts = RobotClient.Options(
            refresh_interval=0,
            dial_options=DialOptions(credentials=secrets.creds)
        )
        self.robot = await RobotClient.at_address(secrets.address, opts)
        self._servo = Servo.from_robot(self.robot, "servo")

        self._mutex = asyncio.Lock()
        self._count = 0  # Number of hands currently raised

        # We have a background coroutine that wiggles the hand when it's been
        # raised for a long time. This condition variable is how to shut that
        # down.
        self._shut_down_wiggler = asyncio.Event()
        self._wiggler = None

    def _start_wiggler(self):
        self._shut_down_wiggler.clear()
        if self._wiggler is not None:
            print("LOGIC BUG: starting the coroutine that's already started!?")
        self._wiggler = asyncio.create_task(self._wiggle_on_inactivity())

    async def _stop_wiggler(self):
        if self._wiggler is None:
            print("LOGIC BUG: stopping the coroutine when it's not started!?")
        self._shut_down_wiggler.set()
        await self._wiggler
        self._wiggler = None

    async def _wiggle_on_inactivity(self):
        """
        This is a background coroutine that wiggles the hand if it's been
        running for a long time. It is started when the count of raised hands
        becomes nonzero, and stopped when the count goes back to 0.
        """
        # This is run in a separate coroutine. When the hand is raised and
        # nothing has happened for INACTIVITY_PERIOD_S seconds, we wiggle the
        # hand.
        while True:
            try:
                await asyncio.wait_for(self._shut_down_wiggler.wait(),
                                       timeout=self.INACTIVITY_PERIOD_S)
                return
            except TimeoutError:
                await self._wiggle_hand()

    async def raise_hand(self):
        """
        Call this to consider 1 extra person in the audience to have raised
        their hand. If this is the first person to do so, we'll raise our
        servo, and otherwise we take no action.
        """
        async with self._mutex:
            self._count += 1
            if self._count == 1:
                await self._servo.move(self.UPPER_POSITION)
                self._start_wiggler()

    async def lower_hand(self):
        """
        Call this to consider 1 extra person in the audience to have lowered
        their hand. If this is the last person who had their hand raised, we'll
        lower our servo, and otherwise take no action.
        """
        async with self._mutex:
            self._count -= 1
            if self._count == 0:
                await self._stop_wiggler()
                await self._servo.move(self.LOWER_POSITION)

    async def set_count(self, new_value):
        """
        Call this to set the number of hands raised in the audience to a certain
        value. This is mainly used to "reset" the count of raised hands if
        someone forgets to lower their hand.
        """
        async with self._mutex:
            should_start_wiggler = self._count == 0 and new_value > 0
            self._count = new_value
            if self._count == 0:
                await self._stop_wiggler()
                await self._servo.move(self.LOWER_POSITION)
            else:
                await self._servo.move(self.UPPER_POSITION)
                if should_start_wiggler:
                    self._start_wiggler()

    async def _wiggle_hand(self):
        """
        This moves the servo to wiggle the hand, intended to be used when we've
        had the hand raised for a while.
        """
        for _ in range(3):
            async with self._mutex:
                await self._servo.move(self.UPPER_POSITION + self.WIGGLE_AMOUNT)
            time.sleep(0.3)
            async with self._mutex:
                await self._servo.move(self.UPPER_POSITION)
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

        should_raise = False
        old_state = False
        while True:
            # TODO: remove this. The mutex should be private
            async with robot._mutex:
                button_state = await button.get()
            if button_state != old_state:
                print("button state has changed to {}!".format(button_state))
                if button_state:
                    should_raise = not should_raise
                    if should_raise:
                        await robot.raise_hand()
                    else:
                        await robot.lower_hand()
            old_state = button_state
            # TODO: remove this. The mutex should be private
            async with robot._mutex:
                await led.set(button_state)


if __name__ == "__main__":
    asyncio.run(main())

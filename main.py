#!/usr/bin/env python3
import asyncio
import contextlib

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

    async def __aenter__(self):
        opts = RobotClient.Options(
            refresh_interval=0,
            dial_options=DialOptions(credentials=secrets.creds)
        )
        self._robot = await RobotClient.at_address(secrets.address, opts)
        self._servo = Servo.from_robot(self._robot, "servo")

        # This will become an asyncio.Task when the hand is raised. It will
        # wiggle the hand when it has been raised for over INACTIVITY_PERIOD_S
        # seconds.
        self._wiggler = None

        await self._servo.move(self.LOWER_POSITION)
        return self

    async def __aexit__(self, *exception_data):
        if self._wiggler is not None:
            await self.lower_hand()
        await self._robot.close()

    # TODO: remove this when we're ready
    def get_pi(self):
        return Board.from_robot(self._robot, "pi")

    async def _wiggle_on_inactivity(self):
        """
        This is a background coroutine that wiggles the hand every
        INACTIVITY_PERIOD_S seconds. It is started when the hand is raised,
        and canceled when the hand is lowered.
        """
        try:
            while True:
                await asyncio.sleep(self.INACTIVITY_PERIOD_S)
                for _ in range(3):
                    await self._servo.move(self.UPPER_POSITION + self.WIGGLE_AMOUNT)
                    await asyncio.sleep(0.3)
                    await self._servo.move(self.UPPER_POSITION)
                    await asyncio.sleep(0.3)
        except asyncio.CancelledError:
            return

    async def raise_hand(self):
        """
        Call this to move the servo to the raised position and start the task
        that wiggles the hand on inactivity.

        Note: this function is not thread safe!
        """
        if self._wiggler is not None:
            print("LOGIC BUG: trying to raise already-raised hand")
            return
        await self._servo.move(self.UPPER_POSITION)
        self._wiggler = asyncio.create_task(self._wiggle_on_inactivity())

    async def lower_hand(self):
        """
        Call this to move the servo to the lowered position and stop the
        background task that wiggles the hand once in a while.

        Note: this function is not thread safe!
        """
        if self._wiggler is None:
            print("LOGIC BUG: trying to lower already-lowered hand")
            return
        self._wiggler.cancel()
        await self._wiggler
        self._wiggler = None
        await self._servo.move(self.LOWER_POSITION)


class Audience:
    def __init__(self, robot):
        self._robot = robot
        self._mutex = asyncio.Lock()
        self._count = 0  # Number of people in the audience with their hand raised

    async def increment_count(self):
        """
        Call this to consider 1 extra person in the audience to have raised
        their hand. If this is the first person to do so, we'll raise our
        servo, and otherwise we take no action.
        """
        async with self._mutex:
            self._count += 1
            if self._count == 1:
                await self._robot.raise_hand()

    async def decrement_count(self):
        """
        Call this to consider 1 extra person in the audience to have lowered
        their hand. If this is the last person who had their hand raised, we'll
        lower our servo, and otherwise take no action.
        """
        async with self._mutex:
            self._count -= 1
            if self._count == 0:
                await self._robot.lower_hand()

    # TODO: either test this thoroughly or remove it. It's currently unused.
    async def set_count(self, new_value):
        """
        Call this to set the number of hands raised in the audience to a certain
        value. This is mainly used to reset the count of raised hands if someone
        forgets to lower their hand.
        """
        async with self._mutex:
            if self._count == 0 and new_value > 0:
                await self._robot.raise_hand()
            if self._count > 0 and new_value == 0:
                await self._robot.lower_hand()

            self._count = new_value


async def main():
    async with Robot() as robot:
        audience = Audience(robot)
        pi = robot.get_pi()
        button = await pi.gpio_pin_by_name("18")
        led = await pi.gpio_pin_by_name("16")

        should_raise = False
        old_state = False
        while True:
            button_state = await button.get()
            if button_state != old_state:
                print("button state has changed to {}!".format(button_state))
                if button_state:
                    should_raise = not should_raise
                    if should_raise:
                        await audience.increment_count()
                    else:
                        await audience.decrement_count()
            old_state = button_state
            await led.set(button_state)


if __name__ == "__main__":
    asyncio.run(main())

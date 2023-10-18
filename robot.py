import asyncio
from contextlib import asynccontextmanager

from viam.components.servo import Servo
from viam.logging import getLogger
from viam.robot.client import RobotClient
from viam.rpc.dial import DialOptions


@asynccontextmanager
async def create_robot(creds, address, log_level):
    """
    This makes a connection to the hardware, creates a Robot object, and then
    closes the connection when the context manager exits.
    """
    opts = RobotClient.Options(
        refresh_interval=0,
        dial_options=DialOptions(credentials=creds)
    )
    client = await RobotClient.at_address(address, opts)
    servo = Servo.from_robot(client, "servo")

    robot = Robot(servo, log_level)
    await robot.start()
    try:
        yield robot
    finally:
        await robot.stop()
        await client.close()


class Robot:
    UPPER_POSITION = 93
    LOWER_POSITION = 152
    WIGGLE_AMOUNT = 7  # Move this much left and right of UPPER_POSITION
    WIGGLE_DELAY_S = 0.5
    INACTIVITY_PERIOD_S = 5

    def __init__(self, servo, log_level):
        """
        This class is in charge of raising and lowering the robot's hand, and
        wiggling the hand if it has been raised for too long.

        WARNING: this class is not thread safe!
        """
        self._logger = getLogger(__name__)
        self._logger.setLevel(log_level)

        self._servo = servo

        # This will become an asyncio.Task when the hand is raised. It will
        # wiggle the hand when it has been raised for over INACTIVITY_PERIOD_S
        # seconds.
        self._wiggler = None

    async def start(self):
        """
        Ideally, this would happen in __init__, but it needs to be async.
        """
        await self._servo.move(self.LOWER_POSITION)

    async def stop(self):
        """
        Call this to ensure the hand is definitely lowered.
        """
        if self._wiggler is not None:
            await self.lower_hand()

    async def _wiggle_on_inactivity(self):
        """
        This is a background coroutine that wiggles the hand every
        INACTIVITY_PERIOD_S seconds. It is started when the hand is raised,
        and canceled when the hand is lowered.
        """
        try:
            while True:
                self._logger.debug("wiggle wiggle wiggle")
                await asyncio.sleep(self.INACTIVITY_PERIOD_S)
                for _ in range(3):
                    await self._servo.move(self.UPPER_POSITION +
                                           self.WIGGLE_AMOUNT)
                    await asyncio.sleep(self.WIGGLE_DELAY_S)
                    await self._servo.move(self.UPPER_POSITION -
                                           self.WIGGLE_AMOUNT)
                    await asyncio.sleep(self.WIGGLE_DELAY_S)
                # Now that we're done wiggle for now, put the arm back up.
                self._logger.debug("stop wiggling")
                await self._servo.move(self.UPPER_POSITION)
        except asyncio.CancelledError:
            return

    async def raise_hand(self):
        """
        Call this to move the servo to the raised position and start the task
        that wiggles the hand on inactivity.
        """
        if self._wiggler is not None:
            self._logger.warning("LOGIC BUG: trying to raise already-raised hand")
            return
        self._logger.debug("raise hand")
        await self._servo.move(self.UPPER_POSITION)
        self._wiggler = asyncio.create_task(self._wiggle_on_inactivity())

    async def lower_hand(self):
        """
        Call this to move the servo to the lowered position and stop the
        background task that wiggles the hand once in a while.
        """
        if self._wiggler is None:
            self._logger.warning("LOGIC BUG: trying to lower already-lowered hand")
            return
        self._wiggler.cancel()
        await self._wiggler
        self._wiggler = None
        self._logger.debug("lower hand")
        await self._servo.move(self.LOWER_POSITION)

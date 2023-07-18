import asyncio
from contextlib import asynccontextmanager

from viam.components.board import Board
from viam.components.servo import Servo
from viam.robot.client import RobotClient
from viam.rpc.dial import DialOptions


@asynccontextmanager
async def create_robot(creds, address):
    """
    This makes a connection to the hardware, creates a Robot object, and then
    closes the connection when the context manager exits.
    """
    opts = RobotClient.Options(
        refresh_interval=0,
        dial_options=DialOptions(credentials=creds)
    )
    client = await RobotClient.at_address(address, opts)
    robot = Robot(client)

    await robot.start()
    try:
        yield robot
    finally:
        await robot.stop()
        await client.close()


class Robot:
    UPPER_POSITION = 30
    LOWER_POSITION = 0
    WIGGLE_AMOUNT = 5
    INACTIVITY_PERIOD_S = 5

    def __init__(self, client):
        """
        This class is in charge of raising and lowering the robot's hand, and
        wiggling the hand if it has been raised for too long.

        WARNING: this class is not thread safe!

        The client passed in is a RobotClient object.
        """
        self._client = client
        self._servo = Servo.from_robot(robot._client, "servo")

        # This will become an asyncio.Task when the hand is raised. It will
        # wiggle the hand when it has been raised for over INACTIVITY_PERIOD_S
        # seconds.
        self._wiggler = None

    async def start(self):
        """
        Ideally, this would happen in __init__, but it needs to be async.
        """
        await robot._servo.move(robot.LOWER_POSITION)

    async def stop(self):
        """
        Call this to ensure the hand is lowered and then close the connection
        with the hardware.
        """
        if self._wiggler is not None:
            await self.lower_hand()

    # TODO: remove this when we're ready
    def get_board(self):
        return Board.from_robot(self._client, "pi")

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
        """
        if self._wiggler is None:
            print("LOGIC BUG: trying to lower already-lowered hand")
            return
        self._wiggler.cancel()
        await self._wiggler
        self._wiggler = None
        await self._servo.move(self.LOWER_POSITION)

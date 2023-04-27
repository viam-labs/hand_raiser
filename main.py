#!/usr/bin/env python3
import asyncio

from viam.robot.client import RobotClient
from viam.rpc.dial import Credentials, DialOptions
from viam.components.board import Board
from viam.components.servo import Servo

import secrets


async def connect():
    opts = RobotClient.Options(
        refresh_interval=0,
        dial_options=DialOptions(credentials=secrets.creds)
    )
    return await RobotClient.at_address(secrets.address, opts)

async def main():
    robot = await connect()

    print('Resources:')
    print(robot.resource_names)

    # Note that the pin supplied is a placeholder. Please change this to a valid pin you are using.
    # pi
    pi = Board.from_robot(robot, "pi")
    pi_return_value = await pi.gpio_pin_by_name("16")
    print(f"pi gpio_pin_by_name return value: {pi_return_value}")

    # Note that the pin supplied is a placeholder. Please change this to a valid pin you are using.
    # pca
    pca = Board.from_robot(robot, "pca")
    pca_return_value = await pca.gpio_pin_by_name("16")
    print(f"pca gpio_pin_by_name return value: {pca_return_value}")

    # servo
    servo = Servo.from_robot(robot, "servo")
    servo_return_value = await servo.get_position()
    print(f"servo get_position return value: {servo_return_value}")


    # Don't forget to close the robot when you're done!
    await robot.close()

if __name__ == '__main__':
    asyncio.run(main())


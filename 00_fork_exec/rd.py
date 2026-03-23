"""
Starting a new process
Goal: We want to start a new linux process using the fork & exec model
"""

import os
import traceback
from typing import List

import click


@click.group()
def cli():
    pass


def contain(command: List[str]):
    os.execv(command[0], command)


@cli.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.argument("Command", required=True, nargs=2)
def run(command: List[str]):
    pid = os.fork()

    if pid == 0:
        try:
            contain(command)
        except Exception:
            traceback.print_exc()
            os._exit(1)

    _, status = os.waitpid(pid, 0)

    print(f"{pid} exited with status {status}")


if __name__ == "__main__":
    cli()

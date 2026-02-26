from typing import List
import os
import click
import traceback


@click.group()
def cli():
    pass


def contain(command: List[str]):
    os.execv(command[0], [command[0], command[1]])


@cli.command()
@click.argument("command", required=True, nargs=2)
def run(command: List[str]):
    pid = os.fork()

    if pid == 0:
        try:
            contain(command)
        except Exception:
            traceback.print_exc()
            os._exit(1)

    waitedpid, status = os.waitpid(pid, 0)

    print(f"{waitedpid} exited with status {status}")


if __name__ == "__main__":
    cli()

"""
Chrooting into an image
Goal: Let's get some filesystem isolation with chroot
"""

from typing import List
import os
from pathlib import Path
import tarfile
import traceback
import uuid

import linux
import click


def _get_image_path(image_name, image_dir, image_suffix="tar.gz"):
    return os.path.join(image_dir, os.extsep.join([image_name, image_suffix]))


def _get_container_path(container_id, container_dir, *subdir_names):
    return os.path.join(container_id, container_dir, *subdir_names)


def create_container_root(image_name, image_dir, container_id, container_dir):
    image_path = _get_image_path(image_name, image_dir)

    container_root = _get_container_path(container_id, container_dir, "rootfs")

    assert os.path.exists(image_path), f"Unable to locate image {image_name}"

    if not os.path.exists(container_root):
        os.makedirs(container_root)

    with tarfile.open(image_path) as t:
        safe_members = []
        for m in t.getmembers():
            if m.type in (tarfile.CHRTYPE, tarfile.BLKTYPE):
                continue

            if m.issym() and m.linkname.startswith("/"):
                continue
            safe_members.append(m)

        t.extractall(container_root, members=safe_members)

    return container_root


@click.group()
def cli():
    pass


def contain(image_name, image_dir, container_id, container_dir, command: List[str]):
    new_root = create_container_root(image_name, image_dir, container_id, container_dir)
    linux.mount("proc", os.path.join(new_root, "proc"), "proc", 0, "")
    linux.mount("sys", os.path.join(new_root, "sys"), "sysfs", 0, "")
    linux.mount(
        "dev",
        os.path.join(new_root, "dev"),
        "tmpfs",
        linux.MS_NOSUID | linux.MS_STRICTATIME,
        "mode=755",
    )

    os.chroot(new_root)
    print("New root", new_root)
    print(
        f"Created a new root for our container: {container_dir}/rootfs/{container_id}"
    )

    os.chdir("/")
    os.execvp(command[0], command)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.option("--image-name", "-i", help="Image name", default="ubuntu")
@click.option(
    "--image-dir",
    help="Images directory",
    default="/home/rajan/Downloads/zips/",
)
@click.option(
    "--container-dir",
    help="Containers directory",
    default="/home/rajan/Documents/workshop/containers",
)
@click.argument("Command", required=True, nargs=-1)
def run(image_name, image_dir, container_dir, command):
    container_id = str(uuid.uuid4())
    pid = os.fork()

    if pid == 0:
        try:
            contain(image_name, image_dir, container_id, container_dir, command)
        except Exception:
            traceback.print_exc()
            os._exit(0)

    waited_pid, status = os.waitpid(pid, 0)

    print(f"{waited_pid} exited with status {status}")


if __name__ == "__main__":
    cli()

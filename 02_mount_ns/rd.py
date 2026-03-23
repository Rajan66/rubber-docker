"""
Goal: Separate our mount table from the other processes.
"""

import os
import stat
import tarfile
import traceback
import uuid

import click
import linux


def _get_image_path(image_name, image_dir, image_suffix="tar.gz"):
    return os.path.join(image_dir, os.extsep.join([image_name, image_suffix]))


def _get_container_path(container_id, container_dir, *subdir_names):
    return os.path.join(container_dir, container_id, *subdir_names)


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


def makedev(dev_path):
    for i, dev in enumerate(["stdin", "stdout", "stderr"]):
        os.symlink("/proc/self/fd/%d" % i, os.path.join(dev_path, dev))
    # for simplicity sake, would need to mount new proc
    os.symlink("/proc/self/fd", os.path.join(dev_path, "fd"))

    DEVICES = {
        "null": (stat.S_IFCHR, 1, 3),
        "zero": (stat.S_IFCHR, 1, 5),
        "random": (stat.S_IFCHR, 1, 8),
        "urandom": (stat.S_IFCHR, 1, 9),
        "console": (stat.S_IFCHR, 136, 1),
        "tty": (stat.S_IFCHR, 5, 0),
        "full": (stat.S_IFCHR, 1, 7),
    }

    for device, (dev_type, major, minor) in DEVICES.items():
        # if we don't pass dev_type, it will become a regular file
        # some programs may crash if they expect a proper character device
        os.mknod(
            os.path.join(dev_path, device),
            0o666 | dev_type,
            os.makedev(major, minor),
        )


def contain(command, image_name, image_dir, container_id, container_dir):
    linux.unshare(linux.CLONE_NEWNS)

    # (source, path, fstype, mountflags, mountoptions)
    # MS_PRIVATE -> create a private mount
    # MS_REC -> apply it recursively
    linux.mount(None, "/", None, linux.MS_PRIVATE | linux.MS_REC, None)

    new_root = create_container_root(
        image_name, image_dir, container_id, container_dir
    )
    print("Created a new root fs for our container: {}".format(new_root))

    # Create mounts (/proc, /sys, /dev) under new_root
    linux.mount("proc", os.path.join(new_root, "proc"), "proc", 0, "")
    linux.mount("sysfs", os.path.join(new_root, "sys"), "sysfs", 0, "")
    linux.mount(
        "tmpfs",
        os.path.join(new_root, "dev"),
        "tmpfs",
        linux.MS_NOSUID | linux.MS_STRICTATIME,
        "mode=755",
    )
    # Add some basic devices
    devpts_path = os.path.join(new_root, "dev", "pts")

    # devpts is a VFS that acts as a psuedoterminalslaves(PTYs)
    # enables applications such as SSH sessions, (xterm) terminal emulators, multiplexers (tmux)  # noqa
    if not os.path.exists(devpts_path):
        os.makedirs(devpts_path)
        linux.mount("devpts", devpts_path, "devpts", 0, "")

    makedev(os.path.join(new_root, "dev"))

    os.chroot(new_root)

    os.chdir("/")

    os.execvp(command[0], command)


@cli.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.option("--image-name", "-i", help="Image name", default="ubuntu")
@click.option(
    "--image-dir",
    help="Images directory",
    default="/home/rajan/Downloads/zips/os/",
)
@click.option(
    "--container-dir",
    help="Containers directory",
    default="/home/rajan/Documents/workshop/containers/",
)
@click.argument("Command", required=True, nargs=-1)
def run(image_name, image_dir, container_dir, command):
    container_id = str(uuid.uuid4())

    pid = os.fork()
    if pid == 0:
        try:
            contain(
                command, image_name, image_dir, container_id, container_dir
            )
        except Exception:
            traceback.print_exc()
            os._exit(1)

    _, status = os.waitpid(pid, 0)
    print("{} exited with status {}".format(pid, status))


if __name__ == "__main__":
    cli()

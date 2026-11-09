"""POSIX exec boundary for Invisible's fixed Juggler pipe descriptors."""

from __future__ import annotations

import os
import subprocess
import sys

# Map descriptors after Python's close-fds sweep, immediately before exec.
# Reserving target numbers in the parent is racy with unrelated I/O threads.
_EXEC = """import fcntl, os, sys
read_fd = fcntl.fcntl(int(sys.argv[1]), fcntl.F_DUPFD_CLOEXEC, 5)
write_fd = fcntl.fcntl(int(sys.argv[2]), fcntl.F_DUPFD_CLOEXEC, 5)
os.dup2(read_fd, 3, inheritable=True)
os.dup2(write_fd, 4, inheritable=True)
os.close(read_fd)
os.close(write_fd)
os.execve(sys.argv[3], sys.argv[3:], os.environ)
"""


def spawn(executable, argv, env):
    sys.audit("invisible_core.engine.launch", executable, argv)
    its_read, our_write = os.pipe()
    our_read, its_write = os.pipe()
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                _EXEC,
                str(its_read),
                str(its_write),
                executable,
                *argv,
            ],
            env=env,
            pass_fds=(its_read, its_write),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except BaseException:
        os.close(our_write)
        os.close(our_read)
        raise
    finally:
        os.close(its_read)
        os.close(its_write)
    return our_write, our_read, process

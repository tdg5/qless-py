#! /usr/bin/env python

"""Our base worker"""

import json
import os
import signal
import sys
import threading
import traceback
from code import InteractiveConsole
from contextlib import contextmanager
from types import FrameType
from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple, Union

from qless import Client, exceptions, logger
from qless.job import Job
from qless.listener import Listener
from qless.queue import Queue


class Worker:
    """Worker. For doing work"""

    def __init__(
        self,
        queues: Sequence[Union[str, Queue]],
        client: Client,
        interval: Optional[int] = None,
        resume: Optional[Union[bool, List[Job]]] = None,
        **kwargs,
    ):
        self.client: Client = client
        # This should accept either queue objects, or string queue names
        self.queues: List[Queue] = []
        for queue in queues:
            if isinstance(queue, str):
                self.queues.append(self.client.queues[queue])
            elif isinstance(queue, Queue):
                self.queues.append(queue)
            else:
                raise ValueError(f"Queue cannot be of class {type(queue)}")

        # Save our kwargs, since a common pattern to instantiate subworkers
        self.kwargs: Dict[str, Any] = {**kwargs, "interval": interval, "resume": resume}

        # Check for any jobs that we should resume. If 'resume' is the actual
        # value 'True', we should find all the resumable jobs we can. Otherwise,
        # we should interpret it as a list of jobs already
        self.resume: List[Job] = self.resumable() if resume is True else (resume or [])
        # How frequently we should poll for work
        self.interval: int = interval or 60
        # To mark whether or not we should shutdown after work is done
        self.shutdown: bool = False

    def resumable(self) -> List[Job]:
        """Find all the jobs that we'd previously been working on"""
        # First, find the jids of all the jobs registered to this client.
        # Then, get the corresponding job objects
        jids = self.client.workers[self.client.worker_name]["jobs"]
        jobs = self.client.jobs.get(*jids)

        # We'll filter out all the jobs that aren't in any of the queues
        # we're working on.
        queue_names = {queue.name for queue in self.queues}
        return [job for job in jobs if job.queue_name in queue_names]

    def jobs(self) -> Generator[Optional[Job], None, None]:
        """Generator for all the jobs"""
        # If we should resume work, then we should hand those out first,
        # assuming we can still heartbeat them
        for job in self.resume:
            try:
                if job.heartbeat():
                    yield job
            except exceptions.LostLockError:
                logger.exception("Cannot resume %s" % job.jid)
        while True:
            seen = False
            for queue in self.queues:
                job = queue.pop()
                if job:
                    seen = True
                    yield job
            if not seen:
                yield None

    @contextmanager
    def listener(self) -> Generator[None, None, None]:
        """Listen for pubsub messages relevant to this worker in a thread"""
        channels = ["ql:w:" + self.client.worker_name]
        listener = Listener(self.client.redis, channels)
        thread = threading.Thread(target=self.listen, args=(listener,))
        thread.start()
        try:
            yield
        finally:
            listener.unlisten()
            thread.join()

    def listen(self, listener: Listener) -> None:
        """Listen for events that affect our ownership of a job"""
        for message in listener.listen():
            try:
                data = json.loads(message["data"])
                if data["event"] in ("canceled", "lock_lost", "put"):
                    self.kill(data["jid"])
            except Exception:
                logger.exception("Pubsub error")

    def kill(self, jid: str) -> None:
        """Stop processing the provided jid"""
        raise NotImplementedError('Derived classes must override "kill"')

    def run(self) -> None:
        """Run this worker"""
        raise NotImplementedError('Derived classes must override "run"')

    def signals(self, signals: Tuple[str, ...] = ("QUIT", "USR1", "USR2")) -> None:
        """Register our signal handler"""
        for sig in signals:
            signal.signal(getattr(signal, "SIG" + sig), self.handler)

    def stop(self) -> None:
        """Mark this for shutdown"""
        self.shutdown = True

    def handler(
        self, signum: int, frame: Optional[FrameType]
    ) -> None:  # pragma: no cover
        """Signal handler for this process"""
        if signum == signal.SIGQUIT:
            # QUIT - Finish processing, but don't do any more work after that
            self.stop()
        elif signum == signal.SIGUSR1:
            # USR1 - Print the backtrace
            message = "".join(traceback.format_stack(frame))
            message = "Signaled traceback for %s:\n%s" % (os.getpid(), message)
            print(message, file=sys.stderr)
            logger.warn(message)
        elif signum == signal.SIGUSR2:
            # USR2 - Enter a debugger
            # Much thanks to http://stackoverflow.com/questions/132058
            data = {"_frame": frame}  # Allow access to frame object.
            if frame:
                data.update(frame.f_globals)  # Unless shadowed by global
                data.update(frame.f_locals)
                # Build up a message with a traceback
                message = "".join(traceback.format_stack(frame))
            message = "Traceback:\n%s" % message
            InteractiveConsole(data).interact(message)
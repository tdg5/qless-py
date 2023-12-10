"""Test the serial worker"""

import time
from threading import Thread
from typing import Generator, Optional

import gevent

from qless.abstract import AbstractJob, AbstractQueue
from qless.listener import Listener
from qless.workers.greenlet import GeventWorker
from qless_test.common import TestQless


class GeventJob:
    """Dummy class"""

    @staticmethod
    def foo(job: AbstractJob) -> None:
        """Dummy job"""
        job.data["sandbox"] = job.sandbox
        job.complete()


class PatchedGeventWorker(GeventWorker):
    """A worker that limits the number of jobs it runs"""

    @classmethod
    def patch(cls) -> None:
        """Don't monkey-patch anything"""
        pass

    def jobs(self) -> Generator[Optional[AbstractJob], None, None]:
        """Yield only a few jobs"""
        generator = GeventWorker.jobs(self)
        for _ in range(5):
            yield next(generator)

    def listen(self, listener: Listener) -> None:
        """Don't actually listen for pubsub events"""
        pass


class TestWorker(TestQless):
    """Test the worker"""

    def setUp(self) -> None:
        TestQless.setUp(self)
        self.worker = PatchedGeventWorker(
            ["foo"], self.client, greenlets=1, interval=0.2
        )
        self.queue: AbstractQueue = self.client.queues["foo"]
        self.thread: Optional[Thread] = None

    def tearDown(self) -> None:
        if self.thread:
            self.thread.join()
        TestQless.tearDown(self)

    def test_basic(self) -> None:
        """Can complete jobs in a basic way"""
        jids = [self.queue.put(GeventJob, {}) for _ in range(5)]
        self.worker.run()
        states = []
        for jid in jids:
            job = self.client.jobs[jid]
            assert job is not None and isinstance(job, AbstractJob)
            states.append(job.state)
        self.assertEqual(states, ["complete"] * 5)
        sandboxes = []
        for jid in jids:
            job = self.client.jobs[jid]
            assert job is not None
            sandboxes.append(job.data["sandbox"])
        for sandbox in sandboxes:
            self.assertIn("qless-py-workers/greenlet-0", sandbox)

    def test_sleeps(self) -> None:
        """Make sure the client sleeps if there aren't jobs to be had"""
        for _ in range(4):
            self.queue.put(GeventJob, {})
        before = time.time()
        self.worker.run()
        self.assertGreater(time.time() - before, 0.2)

    def test_kill(self) -> None:
        """Can kill greenlets when it loses its lock"""
        worker = PatchedGeventWorker(["foo"], self.client)
        greenlet = gevent.spawn(gevent.sleep, 1)
        worker.greenlets["foo"] = greenlet
        worker.kill("foo")
        greenlet.join()
        self.assertIsInstance(greenlet.value, gevent.GreenletExit)

    def test_kill_dead(self) -> None:
        """Does not panic if the greenlet handling a job is no longer around"""
        # This test succeeds if it finishes without an exception
        self.worker.kill("foo")

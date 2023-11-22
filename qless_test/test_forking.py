"""Test the forking worker"""

import os
import signal
import threading
import time

from qless.workers.forking import ForkingWorker
from qless.workers.worker import Worker
from qless_test.common import TestQless


class Foo:
    """Dummy class"""

    @staticmethod
    def foo(job):
        """Fall on your sword!"""
        os.kill(os.getpid(), signal.SIGKILL)


class CWD:
    """Completes with our current working directory"""

    @staticmethod
    def foo(job):
        """Puts your current working directory in the job data"""
        job.data["cwd"] = os.getcwd()
        job.complete()
        os.kill(os.getpid(), signal.SIGKILL)


class PatchedForkingWorker(ForkingWorker):
    """A forking worker that doesn't register signal handlers"""

    def signals(self, signals=()):
        """Do not actually register signal handlers"""
        pass


class TestWorker(TestQless):
    """Test the worker"""

    def setUp(self):
        TestQless.setUp(self)
        self.client.worker_name = "worker"
        self.worker = PatchedForkingWorker(["foo"], self.client, workers=1, interval=1)
        self.queue = self.client.queues["foo"]
        self.thread = None

    def tearDown(self):
        if self.thread:
            self.thread.join()
        TestQless.tearDown(self)

    def test_respawn(self):
        """It respawns workers as needed"""
        self.thread = threading.Thread(target=self.worker.run)
        self.thread.start()
        time.sleep(0.1)
        self.worker.shutdown = True
        self.queue.put(Foo, {})
        self.thread.join(1)
        self.assertFalse(self.thread.is_alive())

    def test_cwd(self):
        """Should set the child's cwd appropriately"""
        self.thread = threading.Thread(target=self.worker.run)
        self.thread.start()
        time.sleep(0.1)
        self.worker.shutdown = True
        jid = self.queue.put(CWD, {})
        self.thread.join(1)
        self.assertFalse(self.thread.is_alive())
        expected = os.path.join(os.getcwd(), "qless-py-workers/sandbox-0")
        self.assertEqual(self.client.jobs[jid]["cwd"], expected)

    def test_spawn_klass_string(self):
        """Should be able to import by class string"""
        worker = PatchedForkingWorker(["foo"], self.client)
        worker.klass = "qless.workers.serial.SerialWorker"
        self.assertIsInstance(worker.spawn(), Worker)

    def test_spawn(self):
        """It gives us back a worker instance"""
        self.assertIsInstance(self.worker.spawn(), Worker)

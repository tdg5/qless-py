"""A Gevent-based worker"""

import os

import gevent
import gevent.pool
from six import next

from qless import logger
from qless.workers.worker import Worker


class GeventWorker(Worker):
    """A Gevent-based worker"""

    def __init__(self, *args, **kwargs):
        Worker.__init__(self, *args, **kwargs)
        # Should we shut down after this?
        self.shutdown = False
        # A mapping of jids to the greenlets handling them
        self.greenlets = {}
        count = kwargs.pop("greenlets", 10)
        self.pool = gevent.pool.Pool(count)
        # A list of the sandboxes that we'll use
        sandbox = kwargs.pop("sandbox", os.path.join(os.getcwd(), "qless-py-workers"))
        self.sandboxes = [
            os.path.join(sandbox, "greenlet-%i" % i) for i in range(count)
        ]

    def process(self, job):
        """Process a job"""
        sandbox = self.sandboxes.pop(0)
        try:
            with self.sandbox(sandbox):
                job.sandbox = sandbox
                job.process()
        finally:
            # Delete its entry from our greenlets mapping
            self.greenlets.pop(job.jid, None)
            self.sandboxes.append(sandbox)

    def kill(self, jid):
        """Stop the greenlet processing the provided jid"""
        greenlet = self.greenlets.get(jid)
        if greenlet is not None:
            logger.warn("Lost ownership of %s" % jid)
            greenlet.kill()

    def run(self):
        """Work on jobs"""
        # Register signal handlers
        self.signals()

        # Start listening
        with self.listener():
            try:
                generator = self.jobs()
                while not self.shutdown:
                    self.pool.wait_available()
                    job = next(generator)
                    if job:
                        # For whatever reason, doing imports within a greenlet
                        # (there's one implicitly invoked in job.process), was
                        # throwing exceptions. The simplest way to get around
                        # this is to force the import to happen before the
                        # greenlet is spawned.
                        job.klass
                        greenlet = gevent.Greenlet(self.process, job)
                        self.greenlets[job.jid] = greenlet
                        self.pool.start(greenlet)
                    else:
                        logger.debug("Sleeping for %fs" % self.interval)
                        gevent.sleep(self.interval)
            except StopIteration:
                logger.info("Exhausted jobs")
            finally:
                logger.info("Waiting for greenlets to finish")
                self.pool.join()

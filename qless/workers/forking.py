'''A worker that forks child processes'''

import os
import multiprocessing
import signal

from six import string_types

from qless import logger, util
from qless.workers.serial import SerialWorker
from qless.workers.worker import Worker

try:
    NUM_CPUS = multiprocessing.cpu_count()
except NotImplementedError:
    NUM_CPUS = 1


class ForkingWorker(Worker):
    '''A worker that forks child processes'''
    def __init__(self, *args, **kwargs):
        Worker.__init__(self, *args, **kwargs)
        # Worker class to use
        self.klass = self.kwargs.pop('klass', SerialWorker)
        # How many children to launch
        self.count = self.kwargs.pop('workers', 0) or NUM_CPUS
        # A dictionary of child pids to information about them
        self.sandboxes = {}
        # Whether or not we're supposed to shutdown
        self.shutdown = False

    def stop(self, sig=signal.SIGINT):
        '''Stop all the workers, and then wait for them'''
        for cpid in self.sandboxes:
            logger.warn('Stopping %i...' % cpid)
            try:
                os.kill(cpid, sig)
            except OSError:  # pragma: no cover
                logger.exception('Error stopping %s...' % cpid)

        # While we still have children running, wait for them
        # We edit the dictionary during the loop, so we need to copy its keys
        for cpid in list(self.sandboxes):
            try:
                logger.info('Waiting for %i...' % cpid)
                pid, status = os.waitpid(cpid, 0)
                logger.warn('%i stopped with status %i' % (pid, status >> 8))
            except OSError:  # pragma: no cover
                logger.exception('Error waiting for %i...' % cpid)
            finally:
                self.sandboxes.pop(cpid, None)

    def spawn(self, **kwargs):
        '''Return a new worker for a child process'''
        copy = dict(self.kwargs)
        copy.update(kwargs)
        # Apparently there's an issue with importing gevent in the parent
        # process and then using it int he child. This is meant to relieve that
        # problem by allowing `klass` to be specified as a string.
        if isinstance(self.klass, string_types):
            self.klass = util.import_class(self.klass)
        return self.klass(self.queues, self.client, **copy)

    def run(self):
        '''Run this worker'''
        self.signals(('TERM', 'INT', 'QUIT'))
        # Divide up the jobs that we have to divy up between the workers. This
        # produces evenly-sized groups of jobs
        resume = self.divide(self.resume, self.count)
        for index in range(self.count):
            # The sandbox for the child worker
            sandbox = os.path.join(
                os.getcwd(), 'qless-py-workers', 'sandbox-%s' % index)
            cpid = os.fork()
            if cpid:
                logger.info('Spawned worker %i' % cpid)
                self.sandboxes[cpid] = sandbox
            else:  # pragma: no cover
                # Move to the sandbox as the current working directory
                with Worker.sandbox(sandbox):
                    os.chdir(sandbox)
                    try:
                        self.spawn(resume=resume[index], sandbox=sandbox).run()
                    except:
                        logger.exception('Exception in spawned worker')
                    finally:
                        os._exit(0)

        try:
            while not self.shutdown:
                pid, status = os.wait()
                logger.warn('Worker %i died with status %i from signal %i' % (
                    pid, status >> 8, status & 0xff))
                sandbox = self.sandboxes.pop(pid)
                cpid = os.fork()
                if cpid:
                    logger.info('Spawned replacement worker %i' % cpid)
                    self.sandboxes[cpid] = sandbox
                else:  # pragma: no cover
                    with Worker.sandbox(sandbox):
                        os.chdir(sandbox)
                        try:
                            self.spawn(sandbox=sandbox).run()
                        except:
                            logger.exception('Exception in spawned worker')
                        finally:
                            os._exit(0)
        finally:
            self.stop(signal.SIGKILL)

    def handler(self, signum, frame):  # pragma: no cover
        '''Signal handler for this process'''
        if signum in (signal.SIGTERM, signal.SIGINT, signal.SIGQUIT):
            self.stop(signum)
            os._exit(0)

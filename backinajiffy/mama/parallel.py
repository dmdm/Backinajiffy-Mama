import asyncio
import concurrent.futures
import logging
import multiprocessing
import socket

import asyncssh

from . import remote as mama_remote
from .const import PROJECT_LOGGER_NAME


def module_logger():
    return logging.getLogger(PROJECT_LOGGER_NAME + '.' + __name__)


async def spawn_processes(inputs, task_func, processes=multiprocessing.cpu_count(), max_tasks=1):
    mgr = multiprocessing.Manager()
    queue = mgr.Queue()
    for inp in inputs:
        queue.put(inp)
    if queue.qsize() < processes:
        processes = queue.qsize()
    executor = concurrent.futures.ProcessPoolExecutor(max_workers=processes)
    loop = asyncio.get_event_loop()
    blocking_tasks = [
        loop.run_in_executor(executor, run_process, process_num, queue, max_tasks, task_func)
        for process_num in range(processes)
    ]
    completed, pending = await asyncio.wait(blocking_tasks)
    # TODO handle pending, i.e. those that timed-out
    results = [t.result() for t in completed]
    return results


def run_process(process_num, queue, max_tasks, task_func):
    lgg = module_logger()
    lgg.info('Starting process ' + str(process_num))
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(spawn_tasks(queue, task_func, max_tasks))


async def spawn_tasks(queue, task_func, max_tasks):
    lgg = module_logger()
    counter = 0
    tasks = []
    results = []
    while not queue.empty():
        remote = queue.get()
        counter += 1
        # TODO Refactor to allow running tasks locally
        tasks.append(asyncio.create_task(run_task_on_remote(remote, task_func)))
        if len(tasks) >= max_tasks:
            results += await asyncio.gather(*tasks)
            tasks = []
        await asyncio.sleep(0)
    if tasks:
        results += await asyncio.gather(*tasks)
    return results


async def run_task_on_remote(remote, task_func):
    lgg = module_logger()
    lgg.debug('Processing ' + str(remote['end_host']['host']))

    connections = []
    try:
        connections = await mama_remote.connect(remote)
        conn = connections[-1]
        return await task_func(remote, conn)
    except asyncio.TimeoutError as e:
        lgg.error('Failed task: Timed out', extra={'data': {'error': repr(e), 'task_func': task_func, 'remote': remote}})
    except (asyncssh.Error, socket.error, ConnectionError) as e:
        lgg.error('Failed task', extra={'data': {'error': e, 'task_func': task_func, 'remote': remote}})
    finally:
        for c in reversed(connections):
            try:
                c.close()
            except ConnectionError as e:
                lgg.error('Failed to close connection', extra={'data': {'error': str(e), 'task_func': task_func, 'connection': c}})

    lgg.debug('Finished ' + str(remote['end_host']['host']))

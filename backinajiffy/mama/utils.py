import asyncio
import time



class Delay:
    DELAYS = [0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

    def __init__(self, max_: int | None = None):
        self._max = max_ if max_ else self.__class__.DELAYS[-1]
        self._cnt = -1

    def reset(self):
        self._cnt = -1

    def delay(self):
        self._cnt += 1
        if self._cnt >= len(self.__class__.DELAYS):
            self._cnt = len(self.__class__.DELAYS) - 1
        return min(self.__class__.DELAYS[self._cnt], self._max)

    async def wait(self):
        await asyncio.sleep(self.delay())


class Singleton(object):
    """
    Baseclass for Singletons.

    See https://www.python.org/download/releases/2.2.3/descrintro/#__new__
    """

    def __new__(cls, *args, **kwargs):
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = object.__new__(cls)
        it.init(*args, **kwargs)
        return it

    def init(self, *args, **kwargs):
        pass


class Stopwatch(Singleton):

    _times = {}

    def start(self, name: str):
        if name in self.__class__._times:
            raise KeyError(f"Stopwatch failed to start '{name}': already present")
        self.__class__._times[name] = {
            'start': time.time()
        }

    def stop(self, name: str):
        if name not in self.__class__._times:
            raise KeyError(f"Stopwatch failed to stop '{name}': unknown")
        self.__class__._times[name]['stop'] = time.time()
        self.__class__._times[name]['total'] = \
            self.__class__._times[name]['stop'] - self.__class__._times[name]['start']

    @property
    def taken(self):
        return {k: v['total'] for k, v in self.__class__._times.items()}

    @property
    def times(self):
        return self.__class__._times

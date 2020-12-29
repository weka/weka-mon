
#
# circular_list module - implement a circular list
#

# author: Vince Fleming, vince@weka.io

from threading import Lock
from logging import debug, info, warning, error, critical, getLogger, DEBUG, StreamHandler
import logging

log = getLogger(__name__)

class circular_list():
    def __init__(self, list):
        # note: list is a [] kind of list
        self._lock = Lock() # make it re-entrant (thread-safe)
        self.list = list
        self.current = 0
        log.debug("circular list created")

    # return next item in the list
    def next(self):
        log.debug(f"in next()")
        with self._lock:
            log.debug(f"before: {self._str()}")
            if len(self.list) == 0:
                return None # nothing in the list
            item = self.list[self.current]
            self.current += 1
            if self.current >= len(self.list):    # cycle back to beginning
                self.current = 0
            log.debug(f"after: {self._str()}")
            return item

    # reset the list to something new
    def reset(self, newlist):
        with self._lock:
            self.list = newlist
            if self.current >= len(self.list):  # ensure sanity
                self.current = 0

    def remove(self, item):
        log.debug(f"in remove()")
        with self._lock:
            log.debug(f"removing {item}; before: {self._str()}")
            try:
                self.list.remove(item)    # it's really a list [], so use the [].remove() method.
            except ValueError:
                log.debug(f"item {item} not in list")
            if self.current >= len(self.list):    # did we remove the last one in the list?
                self.current = 0
            log.debug(f"after: {self._str()}")

    def insert(self, item):
        log.debug(f"in insert()")
        with self._lock:
            log.debug(f"inserting {item}; before: {self._str()}")
            self.list.append(item)
            log.debug(f"after: {self._str()}")

    def _str(self):
        return "list=" + str(self.list) + ", current=" + str(self.current)

    def __str__(self):
        with self._lock:
            return self._str()

    def __len__(self):
        with self._lock:
            return len(self.list)

    def __contains__(self, other):
        with self._lock:
            return other in self.list



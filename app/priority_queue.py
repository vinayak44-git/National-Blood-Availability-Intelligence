import heapq
import threading
from itertools import count


class PriorityRequestQueue:

    def __init__(self):
        self._heap = []
        self._counter = count()
        self._lock = threading.Lock()

    def push(self, request, priority):
        with self._lock:
            sequence = next(self._counter)

            heapq.heappush(
                self._heap,
                (
                    priority,
                    sequence,
                    request
                )
            )

    def peek(self):
        with self._lock:
            if not self._heap:
                return None

            return self._heap[0][2]

    def pop(self):
        with self._lock:
            if not self._heap:
                return None

            _, _, request = heapq.heappop(self._heap)

            return request

    def size(self):
        with self._lock:
            return len(self._heap)

    def clear(self):
        with self._lock:
            self._heap.clear()
            self._counter = count()

    def get_all(self):
        with self._lock:
            return [
                item[2]
                for item in sorted(self._heap)
            ]


priority_queue = PriorityRequestQueue()
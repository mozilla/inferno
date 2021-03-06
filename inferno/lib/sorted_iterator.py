from inferno.lib.peekable import peekable
from heapq import heappush, heappop


class SortedIterator(object):

    def enheap(self, i):
        try:
            item = next(i)
            heappush(self.collection, (item, i))
        except StopIteration:
            return

    def __init__(self, inputs):
        self.collection = []
        for i in inputs:
            self.enheap(iter(i))

    def __iter__(self):
        return self

    def next(self):
        if not self.collection:
            raise StopIteration

        item, i = heappop(self.collection)
        self.enheap(i)
        return item


class AltSortedIterator(object):

    def __init__(self, inputs):
        self.collection = [peekable(input) for input in inputs]
        self.collection = sorted(self.collection, key=self._key)

    def __iter__(self):
        return self

    def next(self):
        removes = []
        reinsert = None
        rval = None
        for stream in self.collection:
            try:
                rval = stream.next()
                reinsert = stream
                break
            except StopIteration:
                removes.append(stream)

        if rval:
            for remove in removes:
                self.collection.remove(remove)
            if reinsert:
                self.collection.remove(reinsert)
                try:
                    reinsert.peek()
                except:
                    pass
                else:
                    removes = []
                    reinsert_index = 0
                    for stream in self.collection:
                        try:
                            stream.peek()
                            if self._key(reinsert) < self._key(stream):
                                break
                        except:
                            removes.append(stream)
                        reinsert_index += 1
                    self.collection.insert(reinsert_index, reinsert)
                    for remove in removes:
                        self.collection.remove(remove)
            return rval
        raise StopIteration

    def _key(self, stream):
        try:
            key, value = stream.peek()
            return tuple(key)
        except StopIteration:
            return tuple()

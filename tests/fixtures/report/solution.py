"""Existing coursework fixture: static half-open range sums."""
import json


class PrefixSum:
    def __init__(self, values):
        self.prefix = [0]
        for value in values:
            self.prefix.append(self.prefix[-1] + value)

    def query(self, left, right):
        if not 0 <= left <= right < len(self.prefix):
            raise ValueError("Require 0 <= left <= right <= n")
        return self.prefix[right] - self.prefix[left]


if __name__ == "__main__":
    values = [2, 4, 6, 8]
    queries = [[0, 4], [1, 3], [2, 2]]
    model = PrefixSum(values)
    print(json.dumps({"values": values, "prefix": model.prefix, "queries": queries,
                      "answers": [model.query(*query) for query in queries]}))

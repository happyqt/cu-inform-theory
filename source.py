import json
import math
import random
from collections import deque
from fractions import Fraction


def distribution(data):
    if not isinstance(data, dict) or not data:
        raise ValueError("распределение должно быть непустым объектом")
    result = {}
    for name, value in data.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("имена и вероятности должны быть строками")
        try:
            result[name] = Fraction(value.replace("∕", "/"))
        except (ValueError, ZeroDivisionError):
            raise ValueError(f"некорректная вероятность: {value}") from None
    if any(p < 0 for p in result.values()) or sum(result.values()) != 1:
        raise ValueError("вероятности должны быть неотрицательны и давать сумму 1")
    return result


def sampler(probabilities):
    denominator = math.lcm(*(p.denominator for p in probabilities))
    total = 0
    bounds = []
    for p in probabilities:
        total += p.numerator * (denominator // p.denominator)
        bounds.append(total)
    return bounds


class Source:
    def __init__(self, data):
        if not isinstance(data, dict):
            raise ValueError("описание источника должно быть объектом")
        models = {name: distribution(row) for name, row in data["models"].items()}
        if not models:
            raise ValueError("нет моделей")
        self.alphabet = sorted(set().union(*(row.keys() for row in models.values())))
        self.period = data["source"]
        if not isinstance(self.period, list) or not self.period:
            raise ValueError("source должен быть непустым списком")
        if "initial" in data or "transitions" in data:
            initial = distribution(data["initial"])
            transitions = data["transitions"]
            self.states = sorted(transitions)
            if not self.states or set(initial) - set(self.states):
                raise ValueError("неизвестное начальное состояние")
            for row in transitions.values():
                if set(row) != set(self.alphabet):
                    raise ValueError("нужен переход по каждому символу")
                if any(state not in transitions for state in row.values()):
                    raise ValueError("переход в неизвестное состояние")
        else:
            self.states = [""]
            initial = {"": Fraction(1)}
            transitions = {"": {a: "" for a in self.alphabet}}

        switches = {}
        for name, value in data["switches"].items():
            if "by_state" in value:
                rows = value["by_state"]
                if set(rows) != set(self.states):
                    raise ValueError("переключатель должен описывать все состояния")
                rows = {state: distribution(row) for state, row in rows.items()}
            else:
                row = distribution(value)
                rows = {state: row for state in self.states}
            for row in rows.values():
                if set(row) - set(models):
                    raise ValueError("переключатель ссылается на неизвестную модель")
            switches[name] = [
                tuple(sum((weight * models[m].get(a, 0)
                           for m, weight in rows[state].items()), Fraction())
                      for a in self.alphabet)
                for state in self.states
            ]
        if any(not isinstance(name, str) or name not in switches for name in self.period):
            raise ValueError("source ссылается на неизвестный переключатель")

        phases = [switches[name] for name in self.period]
        # одинаковые фазы не увеличивают пространство состояний
        for length in range(1, len(phases) + 1):
            if len(phases) % length == 0 and all(
                phases[i] == phases[i % length] for i in range(len(phases))
            ):
                phases = phases[:length]
                break
        size = len(self.states)
        indices = {state: i for i, state in enumerate(self.states)}
        self.start = tuple(initial.get(state, Fraction()) for state in self.states)
        self.start += (Fraction(),) * (size * (len(phases) - 1))
        self.edges = [[] for _ in self.alphabet]
        self.bounds = []
        for phase, rows in enumerate(phases):
            for state, probabilities in zip(self.states, rows):
                self.bounds.append(sampler(probabilities))
                for a, p, edges in zip(self.alphabet, probabilities, self.edges):
                    target = ((phase + 1) % len(phases)) * size
                    target += indices[transitions[state][a]]
                    edges.append((target, p))

    def step(self, vector, symbol=None):
        result = [Fraction()] * len(vector)
        edges = self.edges if symbol is None else [self.edges[symbol]]
        for row in edges:
            for weight, (target, p) in zip(vector, row):
                if weight and p:
                    result[target] += weight * p
        return tuple(result)

    def probability(self, word, offset=0):
        vector = self.start
        for _ in range(offset):
            vector = self.step(vector)
        for a in word:
            if a not in self.alphabet:
                return Fraction()
            vector = self.step(vector, self.alphabet.index(a))
        return sum(vector)

    def generate(self, seed):
        rng = random.Random(seed)
        bounds = sampler(self.start)
        draw = rng.randrange(bounds[-1])
        state = next(i for i, bound in enumerate(bounds) if draw < bound)
        while True:
            bounds = self.bounds[state]
            draw = rng.randrange(bounds[-1])
            symbol = next(i for i, bound in enumerate(bounds) if draw < bound)
            state = self.edges[symbol][state][0]
            yield self.alphabet[symbol]

    def check(self, start, probabilities=None):
        # линейный базис заменяет проверку бесконечного числа слов
        basis = {}
        queue = deque([start])
        while queue:
            vector = list(queue.popleft())
            for pivot in sorted(basis):
                factor = vector[pivot]
                if factor:
                    vector = [x - factor * y for x, y in zip(vector, basis[pivot])]
            pivot = next((i for i, x in enumerate(vector) if x), None)
            if pivot is None:
                continue
            divisor = vector[pivot]
            vector = tuple(x / divisor for x in vector)
            basis[pivot] = vector
            mass = sum(vector)
            if probabilities is None and mass:
                return False
            for i in range(len(self.alphabet)):
                following = self.step(vector, i)
                if probabilities is not None and sum(following) != probabilities[i] * mass:
                    return False
                queue.append(following)
        return True

    def iid(self):
        shifted = self.step(self.start)
        if not self.check(tuple(x - y for x, y in zip(self.start, shifted))):
            raise ValueError("источник нестационарен")
        probabilities = tuple(self.probability([a]) for a in self.alphabet)
        if not self.check(self.start, probabilities):
            raise ValueError("источник имеет память")
        return probabilities


def load_source(path):
    with open(path, encoding="utf-8") as stream:
        return Source(json.load(stream))

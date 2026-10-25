import math
from decimal import Decimal, localcontext
from fractions import Fraction


def entropy(probabilities):
    return math.fsum(-float(p) * (math.log2(p.numerator) - math.log2(p.denominator))
                     for p in probabilities if p)


def types(n, weights):
    powers = [[w ** i for i in range(n + 1)] for w in weights]
    combinations = [[math.comb(i, j) for j in range(i + 1)] for i in range(n + 1)]
    stack = [(0, n, 1, 1, ())]
    while stack:
        i, remaining, probability, count, prefix = stack.pop()
        if i == len(weights) - 1:
            yield probability * powers[i][remaining], prefix + (remaining,), count
        else:
            for amount in range(remaining + 1):
                stack.append((i + 1, remaining - amount,
                              probability * powers[i][amount],
                              count * combinations[remaining][amount], prefix + (amount,)))


def calculate(probabilities, rate, q, nmax, epsilon):
    probabilities = tuple(p for p in probabilities if p)
    denominator = math.lcm(*(p.denominator for p in probabilities))
    weights = [p.numerator * (denominator // p.denominator) for p in probabilities]
    rate = Fraction(rate)
    epsilon = Fraction(epsilon)
    if rate < 0 or q < 2 or nmax < 1 or not 0 < epsilon < 1:
        raise ValueError("нужны R >= 0, q >= 2, nmax >= 1 и 0 < epsilon < 1")

    with localcontext() as context:
        context.prec = 60
        rate_decimal = Decimal(rate.numerator) / Decimal(rate.denominator)
        logq = Decimal(q).ln() / Decimal(2).ln()
        h = sum(-(Decimal(p.numerator) / Decimal(p.denominator)) *
                (Decimal(p.numerator).ln() - Decimal(p.denominator).ln()) / Decimal(2).ln()
                for p in probabilities)
        # для двоично-рациональных вероятностей энтропия считается точно
        if all(p.numerator == 1 and p.denominator & (p.denominator - 1) == 0
               for p in probabilities):
            exact_h = sum(p * (p.denominator.bit_length() - 1) for p in probabilities)
            h = Decimal(exact_h.numerator) / Decimal(exact_h.denominator)
        lengths = [int(Decimal(n) * rate_decimal / logq) for n in range(1, nmax + 1)]
        if q & (q - 1) == 0:
            lengths = [int(n * rate // (q.bit_length() - 1)) for n in range(1, nmax + 1)]

        if rate_decimal > h:
            asymptotic = "да: R > H, вероятность ошибки стремится к 0"
        elif rate_decimal < h:
            asymptotic = "нет: R < H, вероятность ошибки стремится к 1"
        elif len(probabilities) == 1:
            asymptotic = "да: H = R = 0, единственный блок кодируется без ошибки"
        elif len(set(probabilities)) > 1:
            answer = "да" if epsilon >= Fraction(1, 2) else "нет"
            asymptotic = f"{answer}: R = H, для неравномерного P ошибка стремится к 1/2"
            if epsilon == Fraction(1, 2):
                asymptotic += "; при достаточно больших n она меньше 1/2"
        else:
            # при равномерном источнике вся ошибка определяется округлением длины
            k = len(probabilities)
            power, order = k, 1
            while power % q == 0:
                power //= q
            if power == 1:
                upper = 0.0
                admissible = True
            else:
                upper = 1 - 1 / q
                admissible = epsilon >= Fraction(q - 1, q)
                for order in range(2, q.bit_length() + 1):
                    power = k ** order
                    while power % q == 0:
                        power //= q
                    if power == 1:
                        upper = 1 - q ** (-(order - 1) / order)
                        admissible = (1 - epsilon) ** order * q ** (order - 1) <= 1
                        break
            answer = "да" if admissible else "нет"
            asymptotic = f"{answer}: R = H, верхняя грань ошибки округления {upper:.12g}"

    rows = []
    descriptions = []
    for n, length in enumerate(lengths, 1):
        capacity = min(q ** length, len(weights) ** n)
        remaining = capacity
        success = 0
        last = None
        if capacity == len(weights) ** n:
            error = Fraction()
        else:
            for numerator, counts, count in sorted(types(n, weights), reverse=True):
                take = min(remaining, count)
                success += take * numerator
                remaining -= take
                if remaining == 0:
                    last = {"counts": counts, "taken": take,
                            "probability_numerator": str(numerator)}
                    break
            error = Fraction(denominator ** n - success, denominator ** n)
        rows.append((n, length, error))
        descriptions.append({"n": n, "length": length, "blocks": str(capacity), "last_type": last})
    return rows, descriptions, asymptotic

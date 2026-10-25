import argparse
import json
import sys
import time
from collections import deque
from fractions import Fraction
from pathlib import Path

from huffman import compress, decompress
from source import load_source
from uniform import calculate, entropy


parser = argparse.ArgumentParser(description="кодирование источников, вариант 8")
parser.add_argument("--variant", action="store_true")
commands = parser.add_subparsers(dest="command")
generate = commands.add_parser("generate", help="реализация источника")
generate.add_argument("source")
generate.add_argument("--n", default="None")
generate.add_argument("--seed", type=int, default=8)
generate.add_argument("--output")
analyze = commands.add_parser("analyze", help="вероятность блока и частоты")
analyze.add_argument("source")
analyze.add_argument("--word", nargs="+", required=True)
analyze.add_argument("--n", type=int, default=1000000)
analyze.add_argument("--seed", type=int, default=8)
check = commands.add_parser("entropy", help="проверка источника и энтропия")
check.add_argument("source")
uniform = commands.add_parser("uniform", help="оптимальное равномерное кодирование")
uniform.add_argument("source")
uniform.add_argument("--rate", required=True)
uniform.add_argument("--epsilon", default="0.0001")
uniform.add_argument("--q", type=int, default=2)
uniform.add_argument("--nmax", type=int, default=50)
uniform.add_argument("--output", required=True)
pack = commands.add_parser("compress", help="сжатие методом Хаффмана")
pack.add_argument("file")
pack.add_argument("--output")
pack.add_argument("--stats", action="store_true")
unpack = commands.add_parser("decompress", help="восстановление zmh")
unpack.add_argument("file")
unpack.add_argument("--output")
args = parser.parse_args()

try:
    if args.variant:
        print("s=8, k=3, M=4, L=6, d=3, q=2, epsilon=0.0001")
    elif args.command == "generate":
        source = load_source(args.source)
        n = None if args.n == "None" else int(args.n)
        stream = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
        try:
            for i, symbol in enumerate(source.generate(args.seed), 1):
                stream.write(symbol + "\n")
                if n is not None and n > 0 and i >= n:
                    break
        finally:
            if args.output:
                stream.close()
    elif args.command == "analyze":
        source = load_source(args.source)
        r = len(args.word)
        if args.n < r:
            raise ValueError("N должен быть не меньше длины блока")
        first = source.probability(args.word)
        average = sum(source.probability(args.word, j) for j in range(len(source.period)))
        average /= len(source.period)
        print(f"P первого блока: {first} = {float(first):.12g}")
        print(f"P в среднем по {len(source.period)} позициям: {average} = {float(average):.12g}")
        checkpoints = sorted(set([args.n] + [10 ** i for i in range(2, 7)]))
        window = deque(maxlen=r)
        count = 0
        values = {}
        for n, symbol in enumerate(source.generate(args.seed), 1):
            window.append(symbol)
            if list(window) == args.word:
                count += 1
            if n in checkpoints:
                values[n] = Fraction(count, n - r + 1) if n >= r else None
            if n == checkpoints[-1]:
                break
        print(f"Частота при N={args.n}: {float(values[args.n]):.12g}")
        print("N\tчастота\t|частота-P первого|\t|частота-P среднего|")
        for n, value in values.items():
            if value is None:
                print(f"{n}\tнет окон длины {r}")
            else:
                print(f"{n}\t{float(value):.9f}\t{float(abs(value-first)):.9f}\t"
                      f"{float(abs(value-average)):.9f}")
    elif args.command == "entropy":
        source = load_source(args.source)
        probabilities = source.iid()
        print("Источник стационарен и не имеет памяти")
        print("P: " + ", ".join(f"{a}={p}" for a, p in zip(source.alphabet, probabilities)))
        print(f"H = {entropy(probabilities):.12f} бит/символ")
    elif args.command == "uniform":
        started = time.perf_counter()
        source = load_source(args.source)
        probabilities = source.iid()
        rows, descriptions, asymptotic = calculate(
            probabilities, args.rate, args.q, args.nmax, args.epsilon)
        minimum = next((n for n, _, error in rows if error <= Fraction(args.epsilon)), None)
        data = {"alphabet": [a for a, p in zip(source.alphabet, probabilities) if p],
                "probabilities": [str(p) for p in probabilities if p], "q": args.q,
                "rate": args.rate, "epsilon": args.epsilon,
                "order": "types: (probability, counts) descending; words: lexicographic",
                "assignment": "rank from 0, written in base q with leading zeros to length",
                "codes": descriptions}
        Path(args.output).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"H = {entropy(probabilities):.12f} бит/символ")
        print("n\tдлина\tP_e")
        for n, length, error in rows:
            print(f"{n}\t{length}\t{float(error):.12g}")
        print(f"Минимальное n: {minimum}" if minimum else f"Подходящего n нет на [1, {args.nmax}]")
        print("Для всех достаточно больших n: " + asymptotic)
        print(f"Описание кода: {args.output}")
        print(f"Время: {time.perf_counter() - started:.6f} с")
    elif args.command == "compress":
        stats = compress(args.file, args.output)
        print(f"Архив: {stats['output']}")
        if args.stats:
            print(f"Исходный размер: {stats['input']} байт")
            print(f"H: {stats['entropy']:.9f} бит/байт")
            print(f"Средняя длина: {stats['mean_length']:.9f} бит/байт")
            print(f"Заголовок: {stats['header']} байт")
            print(f"Данные: {stats['data']} байт")
            print(f"Архив: {stats['archive']} байт")
            print(f"Коэффициент (исходный/архив): {stats['ratio']:.9f}")
    elif args.command == "decompress":
        print(f"Восстановлен: {decompress(args.file, args.output)}; контрольная сумма совпадает")
    else:
        parser.print_help()
except KeyboardInterrupt:
    print("\nОперация прервана", file=sys.stderr)
except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError,
        ArithmeticError, RecursionError) as error:
    print(f"Ошибка: {error}", file=sys.stderr)
    sys.exit(1)

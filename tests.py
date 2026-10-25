# начало кода, сгенерированного openai codex
import itertools
import json
import math
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

from huffman import HEADER, compress, decompress, make_codes
from source import Source, load_source
from uniform import calculate


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "tests" / "data"


def run(*arguments, error=None):
    result = subprocess.run([sys.executable, str(ROOT / "main.py"), *map(str, arguments)],
                            cwd=ROOT, text=True, capture_output=True)
    if error is None:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0 and error in result.stderr, result.stderr
        assert "Traceback" not in result.stderr
    return result.stdout


base = json.loads((ROOT / "examples" / "iid.json").read_text())
assert "s=8, k=3, M=4, L=6, d=3, q=2" in run("--variant")
assert "0.884183719779" in run("entropy", "examples/iid.json")
source = Source(base)
assert source.probability(["0", "1"]) == Fraction(3, 25)
assert run("generate", "examples/iid.json", "--n", 100, "--seed", 8) == run(
    "generate", "examples/iid.json", "--n", 100, "--seed", 8)
print("ok: вариант, точные вероятности, энтропия, воспроизводимость seed")

for name, message in [
    ("negative", "неотрицательны"),
    ("not_normalized", "сумму 1"),
    ("missing_model", "неизвестную модель"),
    ("missing_switch", "неизвестный переключатель"),
    ("empty_source", "непустым списком"),
]:
    run("entropy", DATA / f"{name}.json", error=message)
run("analyze", "examples/iid.json", "--word", "0", "1", "--n", 1, error="длины блока")
run("uniform", "examples/iid.json", "--rate", "-1", "--output", "unused.json", error="R >= 0")
print("ok: ненормированные и отрицательные вероятности, ссылки, пустой период, N и R")

periodic = load_source(ROOT / "examples/periodic.json")
assert periodic.probability(["0", "1"]) == Fraction(16, 25)
assert sum(periodic.probability(["0", "1"], j) for j in range(6)) / 6 == Fraction(1181, 7200)
run("entropy", "examples/periodic.json", error="нестационарен")
run("entropy", "examples/markov.json", error="память")
run("entropy", "examples/mixture.json", error="память")
markov = load_source(ROOT / "examples/markov.json")
assert markov.probability(["0"]) == Fraction(1, 3)
assert markov.probability(["0", "1", "2"]) == Fraction(1, 27)
assert markov.probability(["0", "1", "2", "0"]) == Fraction(4, 135)
mixture = load_source(ROOT / "examples/mixture.json")
assert mixture.probability(["0", "0"]) == Fraction(257, 800)
hidden_iid = json.loads((ROOT / "examples/mixture.json").read_text())
hidden_iid["switches"]["s"]["by_state"]["b"] = {"m0": "1"}
assert Source(hidden_iid).iid() == source.iid()
for name in ["markov", "mixture"]:
    assert len(run("generate", f"examples/{name}.json", "--n", 10).splitlines()) == 10
    output = run("analyze", f"examples/{name}.json", "--word", "0", "--n", 100)
    assert "1000000" in output
print("ok: периодический источник, память глубины 3, смесь, скрытое iid, все режимы расширения")

# полный перебор используется только как независимая проверка коротких блоков
for probabilities in [(Fraction(4, 5), Fraction(1, 5)),
                      (Fraction(1, 2), Fraction(1, 3), Fraction(1, 6)),
                      (Fraction(1), Fraction(0))]:
    for q in [2, 3]:
        rows, _, _ = calculate(probabilities, "0.9", q, 6, "0.0001")
        for n, length, error in rows:
            values = sorted((math.prod(word) for word in itertools.product(probabilities, repeat=n)),
                            reverse=True)
            assert error == 1 - sum(values[:q ** length])
rows, _, _ = calculate((Fraction(4, 5), Fraction(1, 5)), "2/3", 2, 3, "0.0001")
assert rows[-1][2] == Fraction(13, 125)
assert calculate((Fraction(1, 2), Fraction(1, 2)), "1", 2, 5, "0.0001")[0][-1][2] == 0
assert calculate((Fraction(1, 2), Fraction(1, 4), Fraction(1, 4)), "1.5", 2, 2, "0.0001")[2].startswith("нет")
assert calculate((Fraction(1, 2), Fraction(1, 2)), "1", 3, 2, "2/3")[2].startswith("да")
assert calculate((Fraction(99999, 100000), Fraction(1, 100000)), "0", 2, 3, "0.0001")[0][0][2] <= Fraction(1, 10000)
print("ok: равномерный код совпадает с полным перебором, частичный тип, нулевые вероятности, R=H и R<H")

with tempfile.TemporaryDirectory() as directory:
    temporary = Path(directory)
    for name in ["russian.txt", "english.txt", "empty.bin", "repeated.bin", "all_bytes.bin",
                 "partial.bin", "image.png", "source8.bin"]:
        original = DATA / name
        archive = temporary / (name + ".zmh")
        restored = temporary / name
        stats = compress(original, archive)
        decompress(archive, restored)
        assert original.read_bytes() == restored.read_bytes()
        if name == "repeated.bin":
            assert stats["data"] == 0 and stats["mean_length"] == 0
        if name == "partial.bin":
            assert stats["data"] == 1
    assert sum(count * make_codes({0: 4, 1: 3, 2: 2, 3: 1})[a][1]
               for a, count in {0: 4, 1: 3, 2: 2, 3: 1}.items()) == 19
    run("compress", DATA / "partial.bin", "--output", temporary / "cli.zmh", "--stats")
    run("decompress", temporary / "cli.zmh", "--output", temporary / "cli.bin")
    assert (temporary / "cli.bin").read_bytes() == b"ababa"
    original = (temporary / "cli.zmh").read_bytes()
    run("decompress", DATA / "foreign.zmh", "--output", temporary / "bad.bin", error="чужой формат")
    for name, contents, message in [
        ("truncated.zmh", original[:-1], "обрезанный zmh"),
        ("damaged.zmh", original[:-1] + bytes([original[-1] ^ 128]), "повреждённый zmh"),
        ("bad_header.zmh", original[:HEADER.size - 2] + b"\xff\xff" + original[HEADER.size:], "повреждённый zmh"),
    ]:
        file = DATA / name
        file.write_bytes(contents)
        output = temporary / "bad.bin"
        run("decompress", file, "--output", output, error=message)
        assert not output.exists() and not Path(str(output) + ".part").exists()
    result = run("uniform", "examples/iid.json", "--rate", "1.4", "--output", temporary / "code.json")
    description = json.loads((temporary / "code.json").read_text())
    assert len(description["codes"]) == 50 and "Для всех достаточно больших n: да" in result
print("ok: Хаффман, пустой файл, один байт, все байты, дополнение, контрольная сумма и диагностика")

print("Все проверки пройдены")
# конец кода, сгенерированного openai codex

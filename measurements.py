import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)
log = ["# Результаты\n", "Команды выполнены из каталога проекта. Seed: 8.\n"]


def run(arguments, expected=0):
    result = subprocess.run([sys.executable, *arguments], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == expected, result.stderr
    log.append("```text\n$ python3 " + " ".join(arguments) + "\n" + result.stdout + result.stderr +
               f"код возврата: {result.returncode}\n```\n")
    return result.stdout


run(["tests.py"])
run(["main.py", "--variant"])
run(["main.py", "generate", "examples/iid.json", "--n", "12", "--seed", "8"])
run(["main.py", "entropy", "examples/iid.json"])
for name, word in [("iid", ["0", "1"]), ("periodic", ["0", "1"]),
                   ("markov", ["0", "1", "2", "0"]), ("mixture", ["0"])]:
    run(["main.py", "analyze", f"examples/{name}.json", "--word", *word,
         "--n", "1000000", "--seed", "8"])
    if name != "iid":
        run(["main.py", "entropy", f"examples/{name}.json"], expected=1)

run(["main.py", "uniform", "examples/iid.json", "--rate", "1.4",
     "--output", "results/iid-code.json"])
run(["main.py", "uniform", "examples/iid.json", "--rate", "0.7",
     "--output", "results/low-rate-code.json"])
output = run(["main.py", "uniform", "tests/data/stress.json", "--rate", "2.3",
              "--output", "results/stress-code.json"])
for line in output.splitlines():
    if line.startswith("Время: "):
        assert float(line.split()[1]) < 10, "превышено ограничение 10 секунд"

for name in ["russian.txt", "english.txt", "image.png", "repeated.bin", "empty.bin", "source8.bin"]:
    run(["main.py", "compress", f"tests/data/{name}",
         "--output", f"results/{name}.zmh", "--stats"])
    run(["main.py", "decompress", f"results/{name}.zmh", "--output", f"results/{name}.restored"])
    assert (ROOT / f"tests/data/{name}").read_bytes() == (RESULTS / f"{name}.restored").read_bytes()
    (RESULTS / f"{name}.restored").unlink()
    (RESULTS / f"{name}.zmh").unlink()
    log.append(f"Побайтовое сравнение {name}: совпадает.\n")

for name in ["foreign.zmh", "truncated.zmh", "damaged.zmh", "bad_header.zmh"]:
    run(["main.py", "decompress", f"tests/data/{name}", "--output", "results/invalid.bin"], expected=1)
for name in ["negative", "not_normalized", "missing_model", "missing_switch", "empty_source"]:
    run(["main.py", "entropy", f"tests/data/{name}.json"], expected=1)

(ROOT / "RESULTS.md").write_text("\n".join(log), encoding="utf-8")
print("Сохранены RESULTS.md и описания кодов в results/")

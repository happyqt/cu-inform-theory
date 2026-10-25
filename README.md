# ДЗ 1. Кодирование источников

Вариант 8. Python 3.11+, только стандартная библиотека. Устанавливать пакеты не нужно.
Все команды ниже выполняются из каталога проекта.

## Запуск

```sh
python3 main.py --variant
python3 main.py generate examples/iid.json --n 20 --seed 8
python3 main.py generate examples/markov.json --n 100 --seed 8 --output sequence.txt
python3 main.py analyze examples/periodic.json --word 0 1 --n 1000000 --seed 8
python3 main.py entropy examples/iid.json
python3 main.py uniform examples/iid.json --rate 1.4 --q 2 --epsilon 0.0001 --nmax 50 --output code.json
python3 main.py compress tests/data/russian.txt --stats
python3 main.py decompress tests/data/russian.txt.zmh --output restored.txt
```

`generate` выводит по одному символу на строку. При `--n None`, нуле или отрицательном N генерация продолжается до Ctrl+C. По умолчанию N=None, seed=8.

`analyze` принимает блок как отдельные аргументы после `--word`. N должен быть не меньше длины блока. Кроме оценки для N всегда вычисляются оценки на 100, 1000, …, 1000000 символах одной реализации. Знаменатель — N−r+1, окна перекрываются. Для N<r в дополнительной таблице выводится отсутствие окон.

`entropy` сначала проверяет стационарность, затем отсутствие памяти. Несоблюдение условия даёт сообщение и ненулевой код возврата.

`uniform` принимает R и ε. У нулевых вероятностей нет вклада в ошибку, поэтому соответствующие символы исключаются из кодируемого алфавита. В JSON сохраняется описание кода для каждого n. Порог ε и q по умолчанию соответствуют варианту.

`compress` делает два прохода по файлу. По умолчанию архив называется `исходное_имя.zmh`; `decompress` удаляет последний суффикс `.zmh`. Ключ `--output` задаёт другой путь. Существующий выходной файл заменяется. При ошибке проверки восстановленный файл не сохраняется.

## Проверки и документы

```sh
python3 tests.py
python3 measurements.py
```

`tests.py` использует готовые входы из `tests/data/`; повреждённые архивы создаются из нового корректного архива. `measurements.py` сохраняет вывод в RESULTS.md и описания кодов в `results/`. Архивы после измерения удаляются. REPORT.md редактируется вручную.

Ручная проверка непрерывной генерации: запустить `python3 main.py generate examples/iid.json --n None`, затем нажать Ctrl+C. Повторить с `--n 0`.

- `REPORT.md` — решения, объяснения и таблицы измерений.
- `FORMAT.md` — расширение JSON источников, примеры.
- `RESULTS.md` — команды и фактический вывод, включая ошибки.
- `SOURCES.md` — внешние источники.
- `main.py` — аргументы и режимы запуска.
- `source.py`, `uniform.py`, `huffman.py` — три части задания.

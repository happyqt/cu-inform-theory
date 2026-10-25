import hashlib
import heapq
import math
import os
import struct
from collections import Counter
from pathlib import Path


MAGIC = b"ZMH1"
HEADER = struct.Struct(">4sQQ32sH")


def make_codes(frequencies):
    heap = [(count, symbol, symbol) for symbol, count in sorted(frequencies.items()) if count]
    heapq.heapify(heap)
    serial = 256
    while len(heap) > 1:
        left_weight, _, left = heapq.heappop(heap)
        right_weight, _, right = heapq.heappop(heap)
        heapq.heappush(heap, (left_weight + right_weight, serial, (left, right)))
        serial += 1
    codes = {}
    if heap:
        stack = [(heap[0][2], 0, 0)]
        while stack:
            node, code, length = stack.pop()
            if isinstance(node, int):
                codes[node] = (code, length)
            else:
                stack.append((node[1], code * 2 + 1, length + 1))
                stack.append((node[0], code * 2, length + 1))
    return codes


def canonical(lengths):
    codes = {}
    code = 0
    previous = 0
    for symbol, length in sorted(lengths.items(), key=lambda item: (item[1], item[0])):
        code <<= length - previous
        if code >= 1 << length:
            raise ValueError("повреждённый zmh: недопустимые длины кодов")
        codes[symbol] = (code, length)
        code += 1
        previous = length
    return codes


def compress(path, output=None):
    path = Path(path)
    output = Path(output) if output else Path(str(path) + ".zmh")
    if path.resolve() == output.resolve():
        raise ValueError("входной и выходной файлы совпадают")
    frequencies = Counter()
    checksum = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(65536):
            frequencies.update(block)
            checksum.update(block)
            size += len(block)
    codes = make_codes(frequencies)
    lengths = {symbol: length for symbol, (_, length) in codes.items()}
    codes = canonical(lengths)
    bits = sum(frequencies[symbol] * length for symbol, (_, length) in codes.items())
    model = bytes(value for symbol, length in sorted(lengths.items()) for value in (symbol, length))
    header = HEADER.pack(MAGIC, size, bits, checksum.digest(), len(codes)) + model
    with output.open("wb") as target, path.open("rb") as stream:
        target.write(header)
        buffer = bytearray()
        value = 0
        available = 0
        while block := stream.read(65536):
            for symbol in block:
                code, length = codes[symbol]
                value = (value << length) | code
                available += length
                while available >= 8:
                    available -= 8
                    buffer.append((value >> available) & 255)
                value &= (1 << available) - 1
            target.write(buffer)
            buffer.clear()
        if available:
            target.write(bytes([value << (8 - available)]))
    h = math.fsum(-(count / size) * math.log2(count / size) for count in frequencies.values())
    return {"input": size, "entropy": h, "mean_length": bits / size if size else 0,
            "header": len(header), "data": (bits + 7) // 8,
            "archive": len(header) + (bits + 7) // 8,
            "ratio": size / (len(header) + (bits + 7) // 8), "output": str(output)}


def decompress(path, output=None):
    path = Path(path)
    output = Path(output) if output else path.with_suffix("")
    if path.resolve() == output.resolve():
        raise ValueError("укажите выходной файл, отличный от входного")
    # временный файл не оставляет частично восстановленные данные при ошибке
    temporary = Path(str(output) + ".part")
    if temporary.exists():
        raise ValueError("временный файл уже существует")
    try:
        with path.open("rb") as stream:
            raw = stream.read(HEADER.size)
            if raw[:4] != MAGIC:
                if raw and MAGIC.startswith(raw):
                    raise ValueError("обрезанный zmh: неполная сигнатура")
                raise ValueError("чужой формат: нет сигнатуры ZMH1")
            if len(raw) != HEADER.size:
                raise ValueError("обрезанный zmh: неполный заголовок")
            _, size, bits, digest, count = HEADER.unpack(raw)
            if count > 256:
                raise ValueError("повреждённый zmh: слишком много символов")
            model = stream.read(2 * count)
            if len(model) != 2 * count:
                raise ValueError("обрезанный zmh: неполная модель")
            lengths = dict(zip(model[::2], model[1::2]))
            if len(lengths) != count or (size == 0) != (count == 0):
                raise ValueError("повреждённый zmh: неверная модель")
            if (count <= 1 and bits != 0) or (count == 1 and next(iter(lengths.values())) != 0):
                raise ValueError("повреждённый zmh: неверная длина потока")
            if count > 1 and (0 in lengths.values() or not size <= bits <= size * 255):
                raise ValueError("повреждённый zmh: неверные длины кодов")
            expected = HEADER.size + 2 * count + (bits + 7) // 8
            actual = path.stat().st_size
            if actual < expected:
                raise ValueError("обрезанный zmh: недостаточно данных")
            if actual > expected:
                raise ValueError("повреждённый zmh: лишние данные")
            codes = canonical(lengths)
            tree = {}
            for symbol, (code, length) in codes.items():
                node = tree
                for shift in range(length - 1, -1, -1):
                    node = node.setdefault((code >> shift) & 1, {})
                node["symbol"] = symbol
            checksum = hashlib.sha256()
            written = 0
            with temporary.open("xb") as target:
                if count == 1:
                    symbol = next(iter(lengths))
                    while written < size:
                        block = bytes([symbol]) * min(65536, size - written)
                        target.write(block)
                        checksum.update(block)
                        written += len(block)
                else:
                    node = tree
                    remaining = bits
                    buffer = bytearray()
                    while block := stream.read(65536):
                        for byte in block:
                            used = min(8, remaining)
                            if used < 8 and byte & ((1 << (8 - used)) - 1):
                                raise ValueError("повреждённый zmh: ненулевое дополнение")
                            for shift in range(7, 7 - used, -1):
                                node = node.get((byte >> shift) & 1)
                                if node is None:
                                    raise ValueError("повреждённый zmh: неизвестное кодовое слово")
                                if "symbol" in node:
                                    buffer.append(node["symbol"])
                                    written += 1
                                    node = tree
                            remaining -= used
                        if written > size:
                            raise ValueError("повреждённый zmh: неверный размер результата")
                        target.write(buffer)
                        checksum.update(buffer)
                        buffer.clear()
                    if node is not tree or written != size:
                        raise ValueError("повреждённый zmh: незавершённый поток кодов")
                if checksum.digest() != digest:
                    raise ValueError("повреждённый zmh: контрольная сумма не совпадает")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return output

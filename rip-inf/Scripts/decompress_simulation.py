# scripts/decompress_simulation.py
import gzip
import shutil
import os

source = "../data/simulation.csv.gz"
target = "../data/simulation.csv"

if not os.path.exists(source):
    print(f"Compressed file not found: {source}")
else:
    with gzip.open(source, 'rb') as f_in, open(target, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    print(f"Decompressed: {target}")

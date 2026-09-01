import os
import zipfile
from multiprocessing import Pool

ZIP = "/mnt/2T_HDD/PlanT2.0/PlanT2_Dataset/data/PlanT2_Dataset/PlanT2_DS.zip"
OUT = "/home/jiangchengxuan/data/PlanT2_SSD"
PREFIX = "PlanT_2_dataset/data/"
WORKERS = 24


def init(inf):
    global _zf
    _zf = zipfile.ZipFile(inf)


def extract_one(name):
    zinfo = _zf.getinfo(name)
    target = os.path.join(OUT, name)
    if name.endswith("/"):
        os.makedirs(target, exist_ok=True)
        return 0
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with _zf.open(name) as src, open(target, "wb") as dst:
        dst.write(src.read())
    return 1


def _extract_chunk(names):
    fcount = 0
    for n in names:
        fcount += extract_one(n)
    return (names, fcount)


def main():
    zf = zipfile.ZipFile(ZIP)
    names = [n for n in zf.namelist() if n.startswith(PREFIX)]
    total = len(names)
    print(f"Entries under {PREFIX}: {total}", flush=True)
    chunk = max(1, total // (WORKERS * 8))
    tasks = [names[i:i + chunk] for i in range(0, total, chunk)]

    done = 0
    files = 0
    with Pool(WORKERS, initializer=init, initargs=(ZIP,)) as pool:
        for res in pool.imap_unordered(_extract_chunk, tasks, chunksize=1):
            done += len(res[0])
            files += res[1]
            if done % 200000 < chunk:
                print(f"progress: {done}/{total} dirs/files done, {files} files written", flush=True)
    print(f"DONE. processed {done}/{total}, files written {files}", flush=True)


if __name__ == "__main__":
    main()

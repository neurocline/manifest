# manifest.py

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='+', help='paths to scan')
    args = parser.parse_args()
    print(f"paths: {args.paths}")

    import time
    start_time = time.time()
    for path in args.paths:
        walk(path)
    end_time = time.time()
    delta_secs = end_time - start_time
    print(f"Elapsed time: {delta_secs:.3f} seconds")

def walk(base_path):
    import os
    for root, dirs, files in os.walk(base_path):
        for f in files:
            item_path = os.path.join(root, f)
            # print(item_path)
            get_hash(item_path)

def get_hash(file_path):
    import hashlib
    blocksize = 65536
    sha1 = hashlib.sha1()
    with open(file_path, 'rb') as f:
        for data in iter(lambda: f.read(blocksize), b''):
            sha1.update(data)
    print(f"{sha1.hexdigest()} {file_path}")

if __name__ == '__main__':
    main()

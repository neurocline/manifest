# manifest.py

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='*', help='paths to scan')
    parser.add_argument('--manifest', '-m', help='manifest file to use')
    parser.add_argument('--find-dups', action='store_true', help='find files with the same hash')
    parser.add_argument('--scan', help='compute hashes for the given paths')
    args = parser.parse_args()
    print(f"paths: {args.paths}")

    if args.scan:
        scan_paths(args.paths)
    if args.find_dups:
        find_dups(args.manifest)

def scan_paths(paths):
    import time
    start_time = time.time()
    for path in paths:
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
    null_digest = "0" * 40
    sha1 = hashlib.sha1()
    try:
        with open(file_path, 'rb') as f:
            for data in iter(lambda: f.read(blocksize), b''):
                sha1.update(data)
        print(f"{sha1.hexdigest()} {file_path}")
    except:
        print(f"{null_digest} {file_path}")

def find_dups(manifest_path):
    # get existing manifest
    manifest = read_manifest(manifest_path)

    # turn it into a map of hashes to paths
    hashes = dict()
    for entry in manifest:
        hash, path = entry[0], entry[1]
        if hash not in hashes:
            hashes[hash] = []
        hashes[hash].append(path)

    # show hashes with multiple paths
    for hash, paths in hashes.items():
        if len(paths) > 1:
            print(f"{hash}: {len(paths)} duplicates")
            for path in paths:
                print(f"    {path}")

def read_manifest(manifest_path):
    import os.path
    manifest = None
    if manifest_path and os.path.exists(manifest_path):
        print(f"Reading manifest from {manifest_path}")
        manifest = []
        with open(manifest_path, 'r', encoding='cp437') as f:
            linenum = 1
            try:
                for line in f:
                    manifest.append([line[:40], line[41:].rstrip()])
                    linenum += 1
            except Exception as e:
                print(f"Error in line {linenum}: {line}")
                raise e
    print(f"Manifest has {len(manifest)} entries")
    return manifest

if __name__ == '__main__':
    main()

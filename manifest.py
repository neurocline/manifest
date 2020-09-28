# manifest
# - generate disk manifests and run simple operations on them

from collections import namedtuple
entry_tuple = namedtuple('entry', ['hash', 'path', 'size'], defaults=[None])
start_time = 0.0


def main():
    import time
    global start_time
    start_time = time.time()

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='*', help='paths to scan')
    parser.add_argument('--manifest', '-m', help='manifest file to use')
    parser.add_argument('--find-dups', action='store_true', help='find files with the same hash')
    parser.add_argument('--scan', action='store_true', help='compute hashes for the given paths')
    parser.add_argument('--report', help='path to write report to')
    args = parser.parse_args()
    print(f"paths: {args.paths}")

    if args.scan:
        scan_paths(args.paths, args.manifest)
    if args.find_dups:
        find_dups(args.manifest, args.report)


def scan_paths(paths, manifest_path):
    import time
    start_time = time.time()

    # If we have an existing manifest, read it and set up a dict so we can mine it for
    # content hashes. This will grow to be a full merge of new data into existing data
    manifest = read_manifest(manifest_path)
    path_hashes = dict()
    if manifest is not None:
        for entry in manifest:
            path_hashes[entry.path] = entry.hash
    print(f"Got {len(path_hashes)} existing hashes from manifest")

    # Build up a full manifest
    manifest = []
    for path in paths:
        walk(path, path_hashes, manifest)
    end_time = time.time()
    delta_secs = end_time - start_time

    # Save manifest
    write_manifest(manifest, manifest_path)
    console_status("")
    print(f"Elapsed time: {delta_secs:.3f} seconds")


def walk(base_path, path_hashes, manifest):
    import os
    sized_files = 0
    hashed_files = 0
    for root, _, files in os.walk(base_path):
        for f in files:
            item_path = os.path.join(root, f)
            item_hash = None
            if item_path in path_hashes:
                item_hash = path_hashes[item_path]
            else:
                item_hash = get_hash(item_path)
                hashed_files += 1
            try:
                item_size = os.path.getsize(item_path)
                sized_files += 1
            except Exception:
                item_size = None
            entry = entry_tuple(hash=item_hash, path=item_path, size=item_size)
            manifest.append(entry)
            progress(
                num_files=len(manifest), hashed_files=hashed_files,
                sized_files=sized_files, path=item_path)


def get_hash(file_path):
    import hashlib
    blocksize = 65536
    null_digest = "0" * 40
    sha1 = hashlib.sha1()
    try:
        with open(file_path, 'rb') as f:
            for data in iter(lambda: f.read(blocksize), b''):
                sha1.update(data)
                progress(path=file_path)
        # print(f"{sha1.hexdigest()} {file_path}")
        return sha1.hexdigest()
    except Exception:
        # print(f"{null_digest} {file_path}")
        return null_digest


def find_dups(manifest_path, report_path):
    # get existing manifest
    manifest = read_manifest(manifest_path)

    print(f"Finding duplicates")
    import time
    start_time = time.time()

    # turn it into a map of hashes to paths
    hashes = dict()
    for entry in manifest:
        hash, path = entry[0], entry[1]
        if hash not in hashes:
            hashes[hash] = []
        hashes[hash].append(path)

    # show hashes with multiple paths
    import sys
    report_out = sys.stdout
    if report_path:
        report_out = open(report_path, 'w', encoding='utf-8')
    num_dups = 0
    dup_files = 0
    ignore_hashes = [
        'da39a3ee5e6b4b0d3255bfef95601890afd80709',
        '0000000000000000000000000000000000000000'
    ]

    sorted_hashes = sorted(list(hashes), key=lambda e: len(hashes[e]), reverse=True)
    for hash in sorted_hashes:
        paths = hashes[hash]
        if len(paths) < 2:
            continue
        if hash in ignore_hashes:
            continue
        num_dups += 1
        print(f"{hash}: {len(paths)} duplicates", file=report_out)
        for path in paths:
            print(f"    {path}", file=report_out)
            dup_files += 1
    print(f"{len(hashes)} unique files out of {len(manifest)} total files", file=report_out)
    print(
        f"{num_dups} duplicated hashes found, {dup_files} duplicated files found",
        file=report_out)

    if report_out != sys.stdout:
        report_out.close()

    elapsed_time = time.time() - start_time
    print(f"find_dups: elapsed time={elapsed_time:.3f}")


def read_manifest(manifest_path):
    import os.path
    if not(manifest_path and os.path.exists(manifest_path)):
        return None

    import time
    start_time = time.time()
    console_status("")
    print(f"Reading manifest from {manifest_path}")
    manifest = []
    with open(manifest_path, 'r', encoding='cp437') as f:
        linenum = 1
        try:
            for line in f:
                entry = entry_tuple(hash=line[:40], path=line[41:].rstrip())
                manifest.append(entry)
                linenum += 1
        except Exception as e:
            print(f"Error in line {linenum}: {line}")
            raise e

    elapsed_time = time.time() - start_time
    print(f"read_manifest: {len(manifest)} entries, elapsed time={elapsed_time:.3f}")
    return manifest


def write_manifest(manifest, manifest_path):
    # The current manifest version
    manifest_version = 1

    import os.path
    import time
    start_time = time.time()
    if manifest_path is None or not os.path.exists(manifest_path):
        return

    console_status("")
    print(f"Writing manifest to {manifest_path}")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        print(f"version {manifest_version}", file=f)
        for entry in manifest:
            print(f"{entry.hash} {entry.size} {entry.path}", file=f)

    elapsed_time = time.time() - start_time
    print(f"write_manifest: elapsed time={elapsed_time:.3f}")


last_progress_time = 0.0
last_num_files = 0
last_path = ""
last_hashed_files = 0
last_sized_files = 0


def progress(num_files=None, hashed_files=None, sized_files=None, path=None):
    """Shows progress every 0.1 seconds"""
    import time
    global last_progress_time
    global last_num_files
    global last_path
    global last_hashed_files
    global last_sized_files
    if num_files is None:
        num_files = last_num_files
    if path is None:
        path = last_path
    if sized_files is None:
        sized_files = last_sized_files
    if hashed_files is None:
        hashed_files = last_hashed_files
    last_num_files = num_files
    last_path = path
    last_sized_files = sized_files
    last_hashed_files = hashed_files

    now = time.time()
    if now - last_progress_time < 0.1:
        return
    elapsed_time = now - start_time
    msg = f"T+{elapsed_time:.1f} Hashed={hashed_files} Sized={sized_files} Total={num_files} {path}"
    console_status(msg)
    last_progress_time = now


def console_status(msg):
    """Writes a full non-advancing line to the console"""
    import os
    term_size = os.get_terminal_size()

    max_col = term_size.columns - 1

    # Shorten long line so it won't cause scrolling when we output it
    if len(msg) > max_col:
        half = int(max_col/2) - 3
        msg = msg[0:half] + "..." + msg[-half:]

    # Print to erase and position cursor at end of indicated string. This writes
    # twice but it shouldn't flicker, because we don't erase the part of the string
    # that is visible. If we could trust we had a real terminal, we would just move
    # the cursor back to where it needs to be.
    import sys
    pad = " " * (max_col - len(msg))
    sys.stderr.write("\r" + msg + pad)
    sys.stderr.write("\r" + msg)  # so cursor is a natural place


if __name__ == '__main__':
    main()

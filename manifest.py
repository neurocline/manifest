# manifest.py

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='+', help='paths to scan')
    args = parser.parse_args()
    print(f"paths: {args.paths}")

    # for path in args.paths:
    #    walk(path)
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
        # print(f"root: {root}")
        # print(f"dirs: {dirs}")
        # print(f"files: {files}")
        for f in files:
            item_path = os.path.join(root, f)
            print(item_path)

if __name__ == '__main__':
    main()

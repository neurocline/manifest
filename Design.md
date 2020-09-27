# Design notes

Python. Start with the basic shell of a Python command-line program

```
import argparse

def main():
    pass

if __name__ == '__main__':
    main()
```

The simplest command-line parser using argparse

```
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='+', help='paths to scan')
    args = parser.parse_args()
    print(f"paths: {args.paths}"")
```

Run.

I should have kept every iteration, because I had several trivial errors while putting this
together, and that's instructive.

Simple os.walk usage

```
def walk(base_path):
    import os
    for root, dirs, files in os.walk(base_path):
        print(f"root: {root}")
        print(f"dirs: {dirs}")
        print(f"files: {files}")
```

Or, print out every path as a full path

```
def walk(base_path):
    import os
    for root, dirs, files in os.walk(base_path):
        for f in files:
            item_path = os.path.join(root, f)
            print(item_path)
```

Time it.

```
    import time
    start_time = time.time()
    for path in args.paths:
        walk(path)
    end_time = time.time()
    delta_secs = end_time - start_time
    print(f"Elapsed time: {delta_secs:.3f} seconds")
```

That was surprisingly fast. Run on three SSDs and one spinning disk, with just under
4 million files on it, it took just over 247 seconds.

files: 3922937
time: 247.009 seconds

Should it be faster? This is just under 16,000 files per second.

Of course, no metadata was fetched. And the next step is to generate a digest
for every single file.

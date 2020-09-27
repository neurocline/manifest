# Design notes

## Initial shell

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

## Generate file hashes

Instead of just printing the file name, calculate a file hash. Since we might have huge files,
read files a chunk at a time

```
import hashlib

sha1 = hashlib.shal1()
blocksize = 65536
with open(file_path, 'rb') as f:
    data = f.read(blocksize)
    while len(data) > 0:
        sha1.update(data)
        data = f.read(blocksize)
print(sha1.hex_digest())
```

The fancier Pythonic version is

```
with open(file_path, 'rb') as f:
    for data in iter(lambda: f.read(blocksize), b''):
        sha1.update(data)
```

Interestingly, this runs at 86% of disk speed. On my 4 Ghz Intel i7-6700K, it's using less then one
full core's worth of CPU, so this is probably the fact that Python, being single-threaded, is
reading the data, blocking to update the hash, then reading more data. A multiprocessing version
might be able to read data on one process and calculate hashes on another, but that would only
be a small speedup. Or maybe the new async system could do async reads at the OS level. Something
to play with, but not an issue for a tool you run every once in a while.

Reading a 1 TB drive at 450 MB/sec will take about 2200 seconds, or 37 min. Doing this for
about 4 TB of data will take 2 hours. Not great, not horrible.

## Handling read errors

Of course, just because we can get a path name doesn't mean we can open the file.
But we can wrap the open in a try/except

```
null_digest = "0" * 40
try:
    with open(file_path, 'rb') as f:
    ...
except:
    print(f"{null_digest} {file_path}")
```

For now, we don't show any explicit error, and the 0000.. hash is a good stand-in for
"failed to read", because any specific SHA-1 hash is very unlikely, to the point where we can
expect to never see it. This will handle both "can't open" as well as I/O errors in read.
A more robust version of this would show the errors in a side channel.

Of course, it did not take 2 hours to do hashes for 4 TB worth of 4 million files, it
took 8 hours. This is because opening and reading a small file is far less efficient
in terms of disk bandwidth, and not due to the hashing itself - the Sha-1 hashing on the
computer I'm using appears to be performing at about 4.5 GByte/second. Depending on the disk
sub-system, issuing parallel requests can speed things up, because the underlying operating
system can reorder and even coalesce read requests. But we're going to set that aside
for now.

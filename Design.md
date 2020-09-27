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

Of course, it did not take 2 hours to do hashes for 4 TB worth of 4 million files, it took almost 8
hours (Elapsed time: 28133.037 seconds) for this test. This is because opening and reading a small
file is far less efficient in terms of disk bandwidth, and not due to the hashing itself - the Sha-1
hashing on the computer I'm using appears to be performing at about 4.5 GByte/second. Depending on
the disk sub-system, issuing parallel requests can speed things up, because the underlying operating
system can reorder and even coalesce read requests. But we're going to set that aside for now.

## Duplicate files and changed files

Now that we have hashes for every single file, we can do a few things. We can look for
duplicate files - two or more files on disk that contain the same content. Note that without
doing a lot of work, we can't tell on Windows if these are hard links, whereas on a Unix-style
system, we could simply see if the two files have the same inodes.

But we can also look for files with the same leaf name that have different contents. If we
assume that the leaf names are relatively unique (and they often are), this can show us files
copied to different locations in the file system that have changed, for one reason or another.

First, because we ran our 8-hour hash operation by redirecting output, we have a manifests
file to read. Let's read it. We need a command-line option to get its name and an option to
say what we're doing; the latter should be a verb, but for now we'll make it an option. And
we'll also add an option for our original behavior

```
    parser.add_argument('--manifest', '-m', help='manifest file to use')
    parser.add_argument('--find-dups', action='store_true', help='find files with the same hash')
    parser.add_argument('--scan', help='compute hashes for the given paths')
```

and we need to read the manifest file; the file is a fixed-format at this point, so we can
break it into its pieces easily enough. For now, we'll just read it into an array of arrrays,
but if we get more complicated, we'll introduce a data structure.

```
manifest = None
if args.manifest:
    manifest = []
    with open(args.manifest, 'r') as f:
        for line in f:
            manifest.append([line[:40], line[41:].rstrip()])
```

Once we have a manifest, we can find dups. We do this by creating a hash table (dict in Python)
where the keys are the hashes and the values are the files containing those hashes.

```
hashes = dict()
for entry in manifest:
    hash, path = entry[0], entry[1]
    if hash not in hashes:
        hashes[hash] = []
    hashes[hash].append(path)
```

Once we have the `hashes` dict, we can just iterate through it, looking for hashes with
multiple files

```
for hash, paths in hashes.items():
    if len(paths) > 1:
        print(f"{hash}: {len(paths)} duplicates")
        for path in paths:
            print(f"    {path}")
```

## Side bar on character encodings

Running this code on my Windows system gives me a nasty and familiar error

```
  File "C:\projects\github\neurocline\manifest\manifest.py", line 81, in <module>
    main()
  File "C:\projects\github\neurocline\manifest\manifest.py", line 17, in main
    find_dups(args.manifest)
  File "C:\projects\github\neurocline\manifest\manifest.py", line 51, in find_dups
    manifest = read_manifest(manifest_path)
  File "C:\projects\github\neurocline\manifest\manifest.py", line 75, in read_manifest
    for line in f:
  File "C:\Python37-64\lib\encodings\cp1252.py", line 23, in decode
    return codecs.charmap_decode(input,self.errors,decoding_table)[0]
UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f in position 7079: character maps to <undefined>
```

This is because we originally created the file by redirecting Windows output, which
almost certainly wrote a CP-1252 encoded file. This is a sad legacy of Windows that
lives on to this day, and we're not going to deal with it here, just yet. We're going
to paper over it by opening the file as cp-1252

```
    with open(args.manifest, 'r', encoding='cp1252') as f:
```

The real fix is to update the --scan code to write the manifest file out, instead of
using redirected I/O, and at that point we have to decide how we are representing paths,
because even there, we might not be able to translate the path on disk to a Unicode path
(our preferred representation for strings). We will deal with this later.

Of course, it's not that easy, we still get an exception. Since we don't know what line
it failed on, let's instrument:

```
    with open(manifest_path, 'r', encoding='cp1252') as f:
        linenum = 1
        try:
            for line in f:
                manifest.append([line[:40], line[41:].rstrip()])
                linenum += 1
        except Exception as e:
            print(f"Error in line {linenum}")
            raise e
```

And we find out where

```
Reading manifest from cdef_digests.txt
Error in line 2612141
```

But, also, since I ran from the Windows console and redirected output, what is my console
set to?

```
C:\projects\github\neurocline\manifest>chcp
Active code page: 437
```

This is not actually code page 1252, the Windows default code page; the console defaults
to the code page for the original IBM PC, also now called DOS Latin US.

For curiosity, what path was this? This is interesting, the path looks fine

```
D:\projects\unrealwiki\WikiPages\Unreal Engine Wiki\github.com\6gt50o\Unreal.js\commits\master.atom
```

(this is a path from the archived Unreal wiki that I had grabbed, before someone else put it up again)

Even though the path looks fine, when we re-run using cp437, we can read the file properly. The error
claims that we should see a Å in the file name. I don't see that, and neither cp1252 or cp437 are
multi-byte character sets, so I'm not sure what is happening here.

When we run this, we have a surprising number of duplicates.

## Analyzing duplicates

When I run this on my system, I had a lot of duplicates. The duplicates file has 3 million
entries in it. Now, given that a pair of files with the same hash will write three lines in
the file, that means something like 1 million duplicate files. But out of 4 million, that's a
surprising amount.

Some of it is due to two special cases.

The hash value `0000000000000000000000000000000000000000` is synthetic. We reported that when we had
some kind of error preventing us from completely reading a file. In our case, it's very likely that
none of these files could be opened, either from permissions, or that it was already opened in
an exclusive mode (the various pagefiles). I had 735 of these, and most of them are indeed system
files of one sort or another.

The hash value `da39a3ee5e6b4b0d3255bfef95601890afd80709` is more interesting. This is the SHA-1
has of zero bytes, e.g. an empty file.  I had 29417 of these scattered across my drives. These
aren't duplicate files, of course, it's just that all empty files look the same.

I had so many duplicate files for another reason - most of my drives at this moment are filled with
Unreal builds of one sort or another, and evidently the number of repeated artifacts was much bigger
than I had realized.

So to make it easier to see, let's sort the output by number of occurences, in reverse

```
sorted_hashes = sorted(list(hashes), key=lambda e: len(hashes[e]), reverse=True)
for hash in sorted_hashes:
    ... print
```

Also, let's ignore empty files and the error files for now.

Interestingly, I have a lot of files with the hash `a7d8d04b47f8f7a1decedd3d5a4ecf072a3e92e5`; 9971
of them. And more interesting, these are relatively big, at 486 bytes. These are all Unreal build
artifacts whos leaf name starts with `PHYSX_`. So presumably there is something going on here where
lots of assets are referencing exactly the same data, but for some reason it's stored in unique files
instead of all pointing to the same file. And while maybe the Unreal cook process converts all of these
to the same blob, or maybe these aren't used, this could mean 4.3 MB of pointless data in a build.
And this is one of the reasons why you look for duplicates; waste.

There's a more traditionally interesting dup: 7984 copies of `acbaef275e46a7f14c1ef456fff2c8bbe8c84724`.
This is because evidently I have that many Git repos on my system, because this is `.git\HEAD`, which
is very often the string `ref: refs/heads/master`, because most repos are checked-out to the `master`
branch (which will be the `main` branch from this point on, looks like).

And there's more duplication on my drive related to Unreal. Unreal uses ICU, and there are 5511 duplicates
of localized resources. More PhysX duplicate resources. Some generated files from Unreal that have no
body, just the common header saying "this is a generated file". Apparently MathJax ships with 1456
duplicate files, some empty-looking PNG. All in all, there's over 100,000 files on my system that aren't
really duplicate files in a traditional sense, but files that have the same content for a variety of
reasons.

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

## Adding file metadata

In all of this, we have only been looking at two things - the file path (which includes the file leaf name,
also often referred to as the base name), and the sha-1 hash of the file contents. We want at least
file size as well, because often for duplicates we care about the larger duplicates more than the
smaller ones.

We spent 8 hours getting file hashes for all our files, and while it's now a little out of date (because
we have been editing files in that very hierarchy), it's still a useful set of data. So we want to
annotate it with file sizes, and not re-compute hashes.

We can do this by reading the existing manifest, then running a scan on it to add filesize metadata,
and then writing it back out. We're also going to do a one-time transition from cp437 to utf-8.

Read the manifest in, but this time read it into a type, not just an array. And when we
write it out, we're going to write a file version, so we can update the data down the road.

```
from collections import namedtuple
entry_tuple = namedtuple('entry', ['hash', 'path', 'size'], defaults=[None])

def read_manifest(manifest_path):
    import os.path
    if not(manifest_path and os.path.exists(manifest_path)):
        return None

    manifest = None
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

    print(f"Manifest has {len(manifest)} entries")
    return manifest

manifest_version = 1
def write_manifest(manifest, manifest_path):
    with open(manifest_path, 'w', encoding='utf-8') as f:
        print(f"version {manifest_version}", file=f)
        for entry in manifest:
            print(f"{entry.hash} {entry.size} {entry.path}")
```

Of course, when we test this, we're going to make a copy of our expensively-gotten original
manifest, so we don't accidentally wipe it out with a bug.

Now, for scan, we need to read the existing manifest and then use values from it when
we do our new scan; for this initial repair, we are going to get the sizes of files.
Going forward, doing a scan will remove files that no longer exist, and calculate hashes
for files that have changed (size or mod date being a clue that it changed).

```
    if args.scan:
        scan_paths(args.paths, args.manifest)
```

## Showing status for long-running operations

One common technique in command-line apps is to write a progress line of some sort
to stderr, without advancing it. This can be done by printing \r (\x0D, CR) to return
the cursor to the beginning of the line, then printing a string that's less than
the terminal width and at least as long as the previous line that was printed.

In Python, we can get the size of the current terminal with an `os` library function

```
import os
term_size = os.get_terminal_size()
print(f"line length = {term_size.columns}")
```

At least on Windows, and with the old cmd.exe terminal, there is no moving the cursor
around on the screen, so the most you can do with status is re-use the current line
of output over and over again.

Let's make a progress function

```
def console_status(msg):
    max_col = term_size.columns - 1

    # shorten long line
    if len(str) > max_col:
        half = max_col/2 - 3
        str = str[0:half] + "..." + str[-half:]

    # print to erase and position cursor at end of indicated string
    pad = " " * (max_col - len(str))
    sys.stderr.write("\r" + str + pad)
    sys.stderr.write("\r" + str) # so cursor is a natural place
```

There are probably better ways to do this, but this won't flicker. And then the
progress function just generates an appropriate progress string and calls the console_status
function every once in a while

```
last_elapsed = 0.0

def progress(num_files, path):
    now = time.time()
    if now - last_elapsed < 0.1:
        return
    msg = f"T: {elapsed_time:.2f} sec Files: {num_files} {path}"
    console_status(msg)
    last_elapsed = now
```

and then this prints progress every once in a while so we know what's going on.

## Strange file names

Above, I mentioned that dealing with operating system file paths can be touchy. There's
no single standard. And if you want to deal with every possible file path, you can't
roundtrip paths into a different encoding.

After showing progress, I found out that there are files with very strange paths.
In this case, they are apparently Chinese file names, and this broke the simple
progress code I'd written - a single Unicode character can be quite wide, and when
echoed to a terminal that can only handle cp437, too long to fit in the given space.
These wrapped lines, which is why I noticed them

```
T: 425.51 sec Files: 2612937 D:\projects\unrealwiki\WikiPag...adong\fucking-algorithm\blob\master\动态规划系列\动态规划之正则
T: 425.51 sec Files: 2612937 D:\projects\unrealwiki\WikiPag...adong\fucking-algorithm\blob\master\动态规划系列\动态规划之正则
T: 425.61 sec Files: 2612937 D:\projects\unrealwiki\WikiPag...abuladong\fucking-algorithm\blob\master\数据结构系列\实现计算器
T: 425.61 sec Files: 2612937 D:\projects\unrealwiki\WikiPag...abuladong\fucking-algorithm\blob\master\数据结构系列\实现计算器
T: 425.71 sec Files: 2612937 D:\projects\unrealwiki\WikiPag...buladong\fucking-algorithm\blob\master\算法思维系列\算法学习之 
T: 425.71 sec Files: 2612937 D:\projects\unrealwiki\WikiPag...buladong\fucking-algorithm\blob\master\算法思维系列\算法学习之 
```

This may be tough to fix. NTFS paths are stored in Unicode (specifically, UTF-16 LE, which
is the old name for UCS-2 LE). I think modern Python now uses the wide functions to access
the file system; if not, I wouldn't see Chinese characters above. When printed to the console,
the Chinese characters are shown as boxes, and I think it's one box per byte that can't be
represented, not one box per character. At least, these are being truncated to the proper number
of characters, and so if it's wrapping, that must be printing off the end of the terminal.

## try/except and ctrl-c

If you use try/except to ignore exceptions, you'll also be ignoring the exception injected
by ctrl-C. Python follows the Unix model and raises a KeyboardInterrupt exception when ctrl-C
is pressed. If you have a catch-all try/except that is not actually halting on exception, then
you will swallow this up.

A better approach is to specifically catch the exceptions you want to handle or ignore.

Or, use ctrl-break, as that cannot be ignored, and will always terminate the Python process.

## os.walk and file system speed

It only took 248 seconds to have os.walk iterate through four file systems of a cumulative
4 million files. But calling os.getfilesize on each file is taking considerably longer.
It took 688 seconds to walk roughly the same filesystem and get file sizes. That's still
not horrible, but it's starting to get into "meaningful amounts of time".

At this point, we now have a v1 manifest, with hashes and file sizes. It's also showing the
limits of using a text-based file format, since it takes a significant amount of time to
read this manifest. Everything is stored as text, so it's 658 MB in size. It would be less
than half that size if we stored hashes and sizes as binary, and even smaller if we stored
paths as directory+leaf instead of as full paths.

## Cleaning up the mess

Small programs can be written quickly and don't need much structure. At the 10-line mark, it's
just a complicated command. At the 50-line mark, it's getting bigger but still very easy
to keep in mind. At the 100-line mark, it starts to get a little messy, and by the 200-line
mark, care needs to be exerted.

We are now at the point where we will probably double the lines of code without adding much
functionality, but we need to make it possible for the code to get more complex without being
so fragile that it breaks all the time, or so intertwined that full understanding is hard.
This revolves around several aspects:

- passing state around
- handling errors

The size of any individual file isn't all that important. You can have 6000 line files that are
still very understandable and easy to work with. In fact, problems happen when you split code
into multiple files just because you think they are too big. Individual files should be individual
bits of functionality, and none of our functionality is so complex that it needs to be in separate
files yet. Another reason to put code into individual files is to share it, but we haven't produced
anything worth sharing yet.

First, we need to get rid of as many globals as possible. It's not that globals are forbidden or
bad, but that globals allow for sharing in a way that we can't control or manage. Anything can get
at a global.

Second, we should only cache things that need caching. The terminal width, for example, can
change during a run, so we should get it each time we want to print. There will be artifacts
because the Windows console doesn't preserve text as lines that can reflow, but as lines
written permanently to the console with breaks in them.

Python is one of the languages where importing modules is cheap, and so we should do it as close
to the point of use as possible.

Follow existing conventions instead of inventing your own, unless you have a truly gigantic project.

Use linters and other style enforcement tools. For Python, we'll use Flake8, since it bundles
together a number of style tools. That said, these tools can be touchy to use, especially on
existing code for the first time. The clang-tidy tool is unusual in that it uses the full
Clang parser, but many other tools use custom parsers that, although they will find errors,
may not report them properly.

For an example of a linter going awry, this line

```
print(f"read_manifest: {len(manifest)} entries, elapsed time={elapsed_time%.3f}")
```

does have an error in it that a linter should catch (the inner format item should have been `elapsed_time:.3f`).
But in this case, the error was erroneously reported as being in the first line of code

```
C:\projects\github\neurocline\manifest>flake8 new-manifest.py
new-manifest.py:1:17: E999 SyntaxError: invalid syntax
```

This sort of thing is rare, but does happen, and requires something like a binary search to figure
it out.

It's especialy important to run linters and checkers on dynamic languages like Python, because many errors
will not be noticed until runtime. Even in this simple program, I found multiple errors once I ran Flake8
on the code.

## More on path names

Even with reading and writing the manifest as UTF-8, we are failing to find files with unusual characters
in them. It's not just Chinese characters, it's other non-ASCII characters like `…` or `é` or `—` (which
is an em-dash). The paths are in the manifest and they match files on disk, unless the paths in the file
are really still in cp437?

And it turns out that the new manifest-reading code was still reading the entire file in cp437, even though
it was supposed to be reading it in utf-8. This is where we need unit tests to catch mistakes like this.
But on the other hand, once this is fixed, the unit test is rather pointless, because only if the manifest
reading/writing code is touched will we have the possibility of such an error.

## Adding some classes

One natural way to structure Python code and pass state around is to put code into classes, create objects,
and then methods have access to the object state.

# GuideOS Wikipedia Library (Node)

This tool lets an ordinary computer acting as a Node keep a verified local
copy of current English Wikipedia article text. The Deck does not need to hold
the whole archive. It can ask the Node for articles and keep selected pages for
offline reading.

The default library is Wikimedia's `pages-articles-multistream` dump plus its
index. It includes current article revisions and supporting wiki pages, but not
the entire edit history and not image or video files.

On Windows, double-click `START_WIKIPEDIA_LIBRARY.cmd` for a small guided menu.
The command-line form below provides the same functions on Windows or Linux.

## Before downloading

Ask the tool for a plan. This contacts Wikimedia, reports the exact current
size and available disk space, and downloads nothing:

```text
python guide_wikipedia_dump.py plan G:\Guide-Library\Wikipedia
```

To begin or resume the download:

```text
python guide_wikipedia_dump.py download G:\Guide-Library\Wikipedia
```

To check every stored byte against Wikimedia's published checksum:

```text
python guide_wikipedia_dump.py verify G:\Guide-Library\Wikipedia
```

`status` reports completed and partial files without reading every byte again.

Interrupted downloads remain as `.partial` files and resume on the next run.
A completed file is not accepted until its size and checksum match.

## Command dictionary

- `python`: runs the small GuideOS tool.
- `plan`: shows what would be stored; it changes nothing.
- `download`: starts or safely resumes the transfer.
- `status`: reports what is present without performing a full checksum scan.
- `verify`: checks that the stored copy is complete and unchanged.
- The final path is the folder where the library will live; it can be changed.

## How reading works

`guide_wikipedia_dump_reader.py` follows the supplied MediaWiki export 0.10
schema and processes one `<page>` at a time, so it does not load the enormous
XML document into memory. `guide_wikitext_reader.py` then converts common wiki
markup into restrained readable text without executing remote HTML or wiki
templates.

The lightweight renderer deliberately marks complex tables and omits template
machinery. A later indexing stage will build fast local title search and can
add richer rendering while preserving the verified original dump as the
source of truth.

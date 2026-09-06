# Guide Cartridge Format 1

Guide Cartridge Format 1 defines the first authorable `.guide` package. A
`.guide` file is an ordinary ZIP archive with a different extension, so its
contents can be inspected with common tools. The format is intended for
portable media, data, Guide Recipes, applications, and hardware adapters.

Format 1 defines packaging and verification only. It does **not** give a
package permission to run, install itself, access devices, or modify a Deck.
Those operations require a later GuideOS runtime, an explicit user decision,
and a capability broker enforced outside the package.

## Layout

```text
example.guide
|-- GUIDE/
|   `-- manifest.json
`-- CONTENT/
    `-- ...ordinary package files...
```

`GUIDE/manifest.json` is UTF-8 JSON. It records:

- `format`: exactly `GUIDE-CARTRIDGE-1`;
- `id`: a stable, lowercase package identifier;
- `name`: the human-facing name;
- `version`: a semantic version such as `1.0.0`;
- `kind`: `data`, `media`, `recipe`, `application`, or `adapter`;
- `summary`: a brief plain-language description;
- `capabilities`: requested powers, empty by default;
- `installAction`: a narrowly defined operation understood by GuideOS, or
  `null`; arbitrary installer commands are forbidden;
- `entrypoint`: reserved for the future runtime and `null` by default;
- `files`: every content path, byte count, and SHA-256 digest.

All payload paths begin with `CONTENT/`. Paths are relative, use `/`, and may
not contain `..`, control characters, absolute roots, symbolic links, or other
filesystem indirection. ZIP entries not declared by the manifest are invalid.

## Capability rule

A capability is a narrow requested power such as `audio.play` or
`display.draw`. Declaring one is not consent and does not grant it. A future
Deck must explain each request, let the user refuse it, and enforce the result
outside the package. Format 1 cartridges should normally request no
capabilities because the runtime contract is not yet frozen.

## Integrity and identity

Every content file is protected by a SHA-256 digest. The authoring tool also
writes a SHA-256 sidecar beside the completed `.guide` file. Hashes detect
accidental change; they do not identify an author. Author signatures and
trust/revocation policy belong to a later format revision and independent
security review.

The package `id` names software; it is not a person or network identity. The
same `id` and version should always describe the same package contents.

## Card convention

Cartridge files may be copied to:

```text
GUIDE/CARTRIDGES/<id>-<version>.guide
GUIDE/CARTRIDGES/<id>-<version>.gde
```

The small `.gde` companion is a bounded, plain-text card index containing the
display metadata, archive filename, byte count, SHA-256, requested
capabilities, and installation action. It lets a small Deck browse without
loading a ZIP parser. The Deck verifies the complete `.guide` file against the
index before offering any action. Because the index and archive can both be
altered by an attacker, this proves internal consistency—not authorship—and
the browser labels Format 1 packages unsigned.

The card installer verifies the package before copying and uses temporary
names followed by atomic renames. It does not format the card or erase other
files.

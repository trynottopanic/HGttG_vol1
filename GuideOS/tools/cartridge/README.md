# Cartridge Workshop

These tools turn an ordinary folder into a verified `.guide` cartridge. They
run in Windows PowerShell and do not need administrator access.

## Easiest method

Double-click `GuideOS\MAKE_CARTRIDGE.cmd` at the top of the GuideOS folder.
The Cartridge Workshop asks where your files are, what people should call the
cartridge, what it contains, and where to save it. Pressing Enter accepts each
displayed default. The original files are never changed.

## Make a cartridge

Put the files you want to share in one folder, then run:

```powershell
.\New-GuideCartridge.ps1 `
  -Source C:\MyGuideProject `
  -Id danny.hello-card `
  -Name "Hello Card" `
  -Kind data `
  -Summary "My first Guide cartridge" `
  -Output C:\MyCartridges\hello-card.guide
```

The tool checks every source path, rejects filesystem links, hashes every
file, creates the package, verifies it from scratch, and writes both the
`.guide` file and a `.sha256` checksum file. It will not overwrite a package
unless `-Force` is supplied.

## Check a cartridge

```powershell
.\Test-GuideCartridge.ps1 -Path C:\MyCartridges\hello-card.guide
```

This checks the container, manifest, paths, sizes, and every content hash.

## Copy one to a mounted card

```powershell
.\Install-GuideCartridge.ps1 `
  -Cartridge C:\MyCartridges\hello-card.guide `
  -CardRoot I:\
```

The installer verifies before and after copying. It writes to
`GUIDE\CARTRIDGES`, never formats the card, and does not erase unrelated files.

## Tiny command dictionary

- `-Source`: the folder whose contents go into the cartridge.
- `-Id`: a permanent lowercase name computers use to distinguish the package.
- `-Name`: the friendly name people see.
- `-Version`: the release number; defaults to `1.0.0`.
- `-Kind`: what the cartridge contains.
- `-Summary`: one short explanation of its purpose.
- `-Capability`: a future permission the package will request; omit for now.
- `-InstallAction`: one exact installation operation already implemented by
  GuideOS; it cannot contain arbitrary commands.
- `-Output`: where to create the `.guide` file.
- `-CardRoot`: the mounted card drive or folder, such as `I:\`.
- `-Force`: deliberately replace an existing file with the same identity.

## Terms in ordinary language

- **Package id**: the permanent machine-readable name that distinguishes this
  project from similarly named projects. `local.my-project` is fine for early
  personal work.
- **Version**: a release number. In `1.2.0`, the first number marks major
  compatibility changes, the second marks new features, and the third marks
  fixes.
- **Manifest**: the small index card inside the cartridge describing what it
  is and listing what it contains.
- **SHA-256**: a compact fingerprint. A different fingerprint means some bit
  of the file changed; it does not prove who made the file.
- **Atomic rename**: the final card filename appears only after the complete
  copy has been checked, avoiding a half-written cartridge that looks ready.

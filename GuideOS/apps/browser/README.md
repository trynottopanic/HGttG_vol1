# Guide Web 0.1

Guide Web is the first general-purpose web browser interface in GuideOS. It
uses the same small, controller-aware NetSurf runtime as the rich Wikipedia
reader, but it is deliberately a separate application: Wikipedia passes
remote material through a strict local sanitizer, while Guide Web displays
ordinary public HTTP and HTTPS pages.

## First-iteration interaction

- Stick or D-pad moves the pointer.
- A selects links, controls, and text fields.
- Selecting the address field opens the on-screen keyboard.
- B exits the browser and returns control to GuideOS.
- L1 and R1 move by pages.
- The start page links to lightweight search and Wikipedia.

The first iteration is meant for public reading and exploration. It explicitly
warns users not to enter passwords yet; password storage, site permissions,
downloads, certificate explanations, privacy controls, and per-site capability
rules belong to later security-reviewed iterations.

## Guide-owned visual schema

The start, status, and error surfaces use the established restrained Guide
language without a paper tone: a dark neutral field, blue structural accents,
gold focus/action accents, white primary text, and muted blue-gray explanatory
text. Websites retain their own presentation. The browser does not rewrite a
site to impersonate a Guide-owned screen.

## Trust boundary

The browser starts from a loopback-only page at `127.0.0.1`. The X button is a
privileged Guide action only inside the separate loopback Wikipedia reader;
ordinary websites cannot use it to initiate Semiotic Engine work.

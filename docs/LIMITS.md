# MacWAP: limits and design rules

What a Nokia 7110 can be given over this gateway, how much, how fast, and
how to build decks that feel quick. Written 14 November 2026, before the
GSM HAT had a SIM, so the radio side is not yet measured.

Every figure carries one of three labels:

- **Doc**: from a published source (Nokia's *Service Developer's Guide for
  the Nokia 7110*, issue 3, November 1999; the 7110 User's Guide; the GSM
  and WAP specifications; the wap-over-sms source code).
- **Measured**: observed on this gateway.
- **Estimate**: reasoned, not yet tested. Section 11 lists the tests that
  will replace these with measurements.

## 1. Summary

| Question | Answer | Label |
|---|---|---|
| Largest single fetch | About 1,400 bytes compiled (often quoted as 1,397); stay under 1,300 to be safe | Doc (hobbyist sources) |
| Texts per request | 1, if the address is short | Estimate |
| Texts per reply | 1 per 110 bytes: 3 for the present home deck, 12 for a full-size deck | Doc (code) + Measured (sizes) |
| Time per page | Roughly 20 to 45 seconds for a typical page, 1 to 2 minutes for a full-size deck | Estimate |
| Effective speed | Roughly 150 to 300 bits per second | Estimate |
| Direction | Two-way: the phone can send typed text, numbers and menu choices | Doc |
| Content | Text, links, menus, input fields, small 1-bit pictures | Doc |
| Text styling | None: one font, one size; bold, italic, underline, big, small are all ignored | Doc |
| Screen | 96 x 65 pixels; a title line, 4 lines of text, and the soft-key line | Doc |
| Number of decks and cards | No fixed limit on either; only the bytes-per-fetch limit | Doc |

The link is slow and counted in messages, so the governing rule is:
**fetch rarely, fetch small, and put several cards in each fetch.**

## 2. The chain and its three size limits

    phone --SMS--> HAT -> Kannel smsbox -> wap-over-sms -> Kannel wapbox -> wapserver.py
    phone <--SMS-- HAT <- Kannel smsbox <- wap-over-sms <- Kannel wapbox <- (WML compiled here)

1. **The phone's deck limit.** One compiled deck (WMLC) must be at most
   about 1,400 bytes. A larger deck is refused outright; it is not
   truncated. The limit is on the compiled form, not the WML source.
2. **The text message.** One message carries 140 bytes (1,120 bits) of
   binary data. A header of 7 bytes (single message) or 12 bytes (one part
   of several) tells the phone which program the data is for and how the
   parts join up. That leaves 133 or 128 bytes.
3. **The gateway's part size.** wap-over-sms cuts replies into parts of
   **110 bytes** (880 bits), below the 128 possible. It is a constant in
   its source (`maxBytesPerMessage`).

## 3. What one request costs

The phone sends a WSP "GET" as one datagram:

| Field | Bytes |
|---|---|
| Transaction number | 1 |
| Type (GET) | 1 |
| Address length | 1 |
| Address | as written, e.g. `http://pi/w` is 11 |
| The phone's headers (what it accepts, its name) | unknown, estimated 30 to 60 |

- A single message holds 133 bytes, so a short address should always fit
  in **one text**. (Estimate; the phone's header size must be measured.)
- Addresses over about 100 bytes are reported not to work over the SMS
  bearer. Keep them far shorter anyway.
- `map-url` in `kannel.conf` already turns `http://pi/...` into the page
  server's address, so decks can use 10-character addresses.

## 4. What one reply costs

The reply datagram is:

| Field | Bytes | Note |
|---|---|---|
| Transaction number, type, status, header length | 4 | fixed |
| Reply headers | 9 | Measured |
| The compiled deck | varies | |

Kannel passes every header from the page server on to the phone. Until
14 November the page server sent about 50 bytes of them, 30 just naming
its software (`Server: SimpleHTTP/0.6 Python/3.13.5`), plus Date and
Last-Modified. `wapserver.py` now leaves those out, and 9 bytes remain:
content type 1, Cache-Control 2, Content-Length 4, encoding version 2.

Texts per reply = (deck + 13) / 110, rounded up.

| Compiled deck | Reply datagram | Texts |
|---|---|---|
| up to 97 bytes | up to 110 | 1 |
| 150 | 163 | 2 |
| 317 (present home deck) | 330 | 3 |
| 400 | 413 | 4 |
| 500 | 513 | 5 |
| 750 | 763 | 7 |
| 1,000 | 1,013 | 10 |
| 1,300 | 1,313 | 12 |

Largest deck for a given number of texts: 2 texts 207 bytes; 3 texts 317;
4 texts 427; 5 texts 537; 6 texts 647; 8 texts 867; 10 texts 1,087;
12 texts 1,307.

## 5. How much content fits in the bytes

Compiling replaces each tag and attribute name with one byte. Text is
**not** compressed: one character is one byte, plus 2 bytes around each
run of text. The present home deck compiles from 718 to 317 bytes (44%),
because it is mostly markup; a text-heavy deck compiles to nearer 70 to
80% of its source. (Measured for the home deck; the rest is Estimate.)

Rules of thumb (Estimate):

- Each card costs 10 to 20 bytes of overhead plus its title.
- Each link costs about 6 bytes plus its address and its label.
- A full-size deck holds about 1,100 to 1,200 characters of text.
- A 4-text reply holds about 300 to 350 characters, which is 4 to 5
  screens.

**Decks and cards.** There is no limit on the number of decks on the Pi,
and no fixed limit on cards per deck: 3 long cards or 20 short ones, as
long as the deck compiles under the limit. Moving between cards of a deck
already fetched costs no texts and is instant.

## 6. Speed

All Estimate until tested.

- **Channel.** A text travels on GSM's signalling channel at about
  0.8 kbit/s, and crosses it twice (sender to message centre, message
  centre to receiver), with set-up time on each hop.
- **Per message.** Expect 3 to 8 seconds per text end to end. Parts of a
  multi-part reply are sent one after another by the HAT.
- **Per page.** Request 5 to 10 seconds, then 3 to 8 seconds per reply
  text. The phone shows nothing until the last part arrives.

| Page | Texts (out + in) | Expected time |
|---|---|---|
| Tiny confirmation | 1 + 1 | 10 to 20 s |
| Typical page (300 characters) | 1 + 4 | 20 to 45 s |
| Full-size deck | 1 + 12 | 1 to 2 min |

- **Effective rate.** 110 bytes every 3 to 6 seconds is 150 to 300 bits
  per second.
- **Data call, for comparison.** 9,600 bits per second (14,400 if the
  network allows): a full-size deck in under 2 seconds, after 15 to 30
  seconds of call set-up. Whether the network and the HAT support data
  calls is unknown, and data calls may be charged outside a calls bundle.

**Three timing traps**

1. **The 3-second rule (Doc, code).** wap-over-sms waits only 3 seconds
   for Kannel to hand back the reply, then gives up silently. Kannel must
   fetch and compile the page inside that. A page that looks something up
   on the internet at request time will often miss it. Pages with outside
   data must be prepared in advance (section 9).
2. **One at a time (Doc, code).** The relay handles one request at a time
   and reuses one message reference number. Fine for one phone.
3. **No retries.** With connection type "Temporary" (connectionless),
   nothing is re-sent. If one part is lost, the phone eventually reports
   an error and the request must be made again. How long the 7110 waits
   is not known.

Connection type "Continuous" adds acknowledgement messages and a session
set-up exchange: several extra texts per page for no benefit here.

## 7. Two-way data

It is a request-and-reply system: the phone always asks first.

**Phone to Pi (Doc):**

- Text fields (`<input>`): a full text editor with multi-tap entry, a
  number-only editor, and a password editor (shows asterisks). The
  `format` attribute chooses the editor.
- Selection lists (`<select>`): single choice and multiple choice.
- Values are sent in the address (`?q=...`), which must stay short, or as
  posted fields. Posted fields make the request bigger, possibly two
  texts; whether two-part requests survive the chain is untested.
- "Use number": the phone offers to dial any phone number shown on a card.

**On the phone, no texts used:**

- Variables carry values between cards.
- WMLScript (WAP 1.1) can calculate and check input locally. Each script
  file is its own fetch. Supported by the standard; untested here.
- Timers (`<timer>`) can move to another card after a delay. Never use
  one to re-fetch automatically: each refresh costs texts.

**Pi to phone, unprompted:**

- WAP "push" does not exist on the 7110 (it came with WAP 1.2).
- The Pi can, however, send an **ordinary text message** at any time: an
  alert that says "new mail" or "frost tonight". The reader then decides
  whether to open the WAP page.
- Ordinary texts also work in the other direction as one-line commands
  (send `WX`, get one text back): 1 + 1 texts and no WAP at all. Worth
  considering for single facts. It would need the SMS routing in
  `sms.conf` to tell commands from WAP data.

## 8. What the screen can show

All Doc unless marked.

**Layout.** 96 x 65 pixels. From the top: one header line (the card's
`title`), four lines of main text, then the soft-key line ("Options" on
the left, "Back" on the right when the card provides it). A text line is
11 pixels high.

**Fonts.** Two, both 8 pixels high and proportional: normal for the header
and bold for main text and soft keys. There is no choice of font or size.

**Styling.** `<b>`, `<i>`, `<u>`, `<em>`, `<strong>`, `<big>` and
`<small>` are accepted and **ignored**. Emphasis has to come from words,
capitals, or layout.

**Characters per line.** Proportional, so it varies: narrow letters fit
many more than wide ones. Expect 15 to 20 characters per line (Estimate),
so 60 to 80 per screen.

**Wrapping.** Whole words only; no hyphenation. Long words leave ragged
lines.

**Length.** Nokia recommends at most 4 to 5 screens (16 to 20 lines) per
card. The roller scrolls one line at a time.

**Links.** Each link takes a line of its own, so a menu shows four choices
per screen. The roller moves between links and pressing it follows one.

**Options menu.** `<do>` elements appear in the Options list, between the
phone's own entries (Home, Bookmarks, Use number, Empty cache, Exit).
`<do type="prev">` becomes the right soft key, "Back". Without it there is
no Back key, so every card needs one.

**Tables.** Shown as one long row of cells. Do not use them.

**Pictures.**

- WBMP only: 1 bit per pixel, black or white, no greys, no compression.
- Largest shown: 96 x 44 pixels. Wider pictures are cut off on the right.
- A picture always starts a new line; text cannot sit beside it. A picture
  up to 11 pixels high leaves three text lines, 22 leaves two, 33 leaves
  one.
- A picture cannot be a link (its `alt` text is used instead).
- **Cost over texts:** a picture is a separate fetch. Width/8 x height
  bytes plus about 4: a full 96 x 44 picture is 532 bytes, so 1 text out
  and 5 back, on top of the deck. A 32 x 16 logo is 68 bytes: 1 out, 1
  back.

**Characters.** Plain Latin letters, digits and common punctuation are
safe, including the pound sign. Avoid curly quotes, long dashes and emoji.
A literal dollar sign must be written `$$`, because `$` introduces a
variable.

**Not supported:** tab alignment and `<fieldset>` grouping, cookies (the
7110 has none; Estimate), and anything from WAP 1.2 or later.

## 9. Making it quick

In order of effect.

1. **Bundle cards.** The fixed cost of any fetch is one text out and a
   wait of 10 seconds or more. Put everything the reader is likely to
   want next into the same deck, as extra cards, up to the size you are
   willing to wait for. A service is one deck, not one deck per screen.
2. **Pick a size budget per deck.** Suggested: 4 texts (427 bytes
   compiled) for things read often, 8 texts (867 bytes) for things read
   occasionally. Avoid the full 12.
3. **Prepare outside data in advance.** A timer job on the Pi fetches
   weather, mail subjects and so on every few minutes and writes finished
   WML files. The page server then only hands over a file, well inside
   the 3-second rule, and the page still works if the internet is slow.
   Show the time of the data on the card.
4. **Trim reply headers.** Done on 14 November: `wapserver.py` no
   longer sends the server name, Date or Last-Modified. That saved 42
   bytes per reply and took the home deck from 4 texts to 3. Any header
   added later costs bytes on every page.
5. **Try 128-byte parts.** Raising wap-over-sms from 110 to 128 bytes per
   part would cut one text in every eight. Its author chose 110, perhaps
   for a reason; test before relying on it.
6. **Let the phone cache what does not change.** The home menu and other
   fixed decks should be cacheable, so returning to them costs nothing.
   At present the page server marks everything "no-cache"; that should
   apply to changing pages only. The 7110's cache handling is reported to
   be unreliable: if it shows stale pages, give changing pages a
   different address each time.
7. **Write tightly.** Text is the one thing that does not compress:
   - short titles (the header is one line and is cut if longer);
   - short card names and addresses (`http://pi/w`, card `a`);
   - abbreviations a reader will accept ("Sat 14 Nov", "12C", "NW 15mph");
   - no decoration, no repeated headings, no "Welcome to";
   - one `<template>` per deck for the Back key instead of repeating it
     on every card.
8. **No pictures over texts**, or one very small one on a cached page.
9. **Menus of at most four links** fit one screen without scrolling.
10. **Check sizes before publishing.** `tools/wapget.py` already reports
    the compiled size. A small checker that runs every deck through
    Kannel and prints bytes and texts would catch oversize decks before
    the phone does. Not yet written.

## 10. Allowances and risks

- **Message allowance.** Requests use the phone's SIM; replies use the
  Pi's SIM, at 3 to 12 texts per page. Twenty typical pages a day is about
  100 texts a day, 3,000 a month, from the Pi's SIM. "Unlimited" plans
  have a fair-use policy; the figure should be checked.
- **Sending pattern.** Bursts of binary texts from one SIM to one number
  could look like automated traffic to the network.
- **Binary messages may be blocked** by the network altogether. This is
  the first thing to test.
- **Privacy.** Texts are protected only by GSM's own encryption, and the
  gateway will identify the phone by its number alone. Do not put
  passwords or full message bodies on pages.
- **Power.** The HAT draws short bursts of up to about 2 A when sending.

## 11. Measurements to take first

When the HAT is working, one session with the Kannel logs open will turn
most of the Estimates above into facts:

1. Does a binary text from the phone reach the Pi, and one from the Pi
   reach the phone?
2. Size of the phone's request for `http://pi/` (gives the header size).
3. Seconds from pressing "Go" to the page appearing, for the 3-text home
   deck.
4. The same for decks of 8 and 12 texts; note any failures.
5. How long the phone waits before giving up.
6. The largest deck the phone accepts (try 1,300, 1,390, 1,400, 1,450).
7. Characters per line for typical text.
8. Whether the phone re-fetches a "no-cache" page and reuses a cacheable
   one.
9. Whether a 128-byte part size works.
10. Whether a two-part request (a long posted field) arrives intact.

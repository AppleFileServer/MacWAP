# MacTrack calorie feed

This is the contract between **MacWAP** (which writes the file) and
**MacTrack** (which reads it). MacWAP owns the writing half; the reading
half is MacTrack's to build to this spec. Keep the two in step: a change
here is a change both sides must agree.

## What it is

Every calorie entry logged through the gateway — by a text to the Pi, or
(later) over WAP — is kept in an **append-only** log on the Pi. Whenever
it changes, the Pi mirrors the whole log to a file on the shared drive so
MacTrack can pull it in and merge it with whatever the user has typed
into MacTrack directly.

Append-only means an entry is never edited or deleted in place: an
"undo" is recorded as a separate *void* line that cancels an earlier one.
So every entry keeps a **stable id** for its whole life, and MacTrack can
re-read the file as often as it likes without ever duplicating.

## Where and how it is served

- **File:** `calories.txt` in the feed folder, usually
  `/srv/macshare/MacTrack Link/` (set by `install.sh enable-mactrack`).
- **Transport:** the shared drive — FTP today (user `macplus`), AppleTalk
  later (when TashTalk USB arrives). Same folder either way.
- **Encoding:** Mac Roman (so `£` and the like are right on the Plus).
- **Line endings:** CR (`\r`, 0x0D) — classic Mac, so it opens in
  TeachText too. Netatalk maps `.txt` to type `TEXT`/creator `ttxt`.
- The Pi writes it atomically (temp file, then rename), so a reader never
  sees a half-written file.

## Format

A header line, then one line per log event. Fields are **tab-separated**.

```
#MacTrack calories v1	id	when	op	value	label
1	2026-11-14 20:00:00	A	500	Dinner
2	2026-11-15 08:42:03	A	654	Bites
3	2026-11-15 09:10:11	A	250	Pigs in blankets
4	2026-11-15 09:12:40	V	3	
```

| Field   | Meaning |
|---------|---------|
| `id`    | A whole number, assigned by the Pi, **unique and never reused**. Entries appear in ascending id order. |
| `when`  | Local time (Europe/London) the entry was logged, `YYYY-MM-DD HH:MM:SS`. |
| `op`    | `A` = add, `V` = void. |
| `value` | For `A`, the calories (1–9999). For `V`, the **id being cancelled**. |
| `label` | For `A`, the free-text note (food), up to 40 chars, possibly empty. Empty for `V`. |

- The first line starts with `#` — a header/version marker. MacTrack must
  **skip any line beginning with `#`.** The version (`v1`) changes only if
  this format changes incompatibly.
- A label may contain spaces (tabs are stripped out before writing, so a
  tab always means a new field).
- Ids may look non-contiguous over time; that is fine. (Rows carried over
  from the old two-column log take the low ids.)

## What MacTrack must do on import

Read the whole file each time (it is small) and reconcile:

1. Skip the header and any blank lines.
2. For each `A` line whose `id` MacTrack has not already stored, add a
   calorie entry tagged as coming from this feed, keyed by that `id`.
3. For each `V` line, remove (or mark void) the feed entry whose `id`
   equals the `value`, if present.
4. Store the `id` against each imported entry, so the next import adds
   only genuinely new ones. Re-importing the same file must change
   nothing.

Entries the user typed into MacTrack by hand are a **separate source**:
the reconcile above must never touch them. Only rows that came from this
feed (matched by feed id) are added, voided or skipped.

That is all that is needed for repeated, on-demand imports to stay
correct, including an undo made on the phone after MacTrack already
pulled the entry in.

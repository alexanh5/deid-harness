# Labeling Guidelines: Enron Email Bodies

Version 0.1 (November 1, 2026). Update this file whenever an edge case is decided, and record the change in the changelog at the bottom. Labels are only as good as the rules behind them.

## Purpose

These labels are the ground truth for the deid-harness. Every engine (Tonic Textual, Presidio, others) is scored against them. The labels describe what a careful reviewer would remove before sharing the text. They do not describe what any particular engine is able to find.

## Scope

- **Labeled:** the normalized message body produced by `deid sample`, including quoted replies, forwarded content, and signature blocks.
- **Not labeled:** the RFC 822 headers (From, To, Cc, Subject, Date). Headers are structured fields and are handled by column rules, not text detection.
- **Text source:** label only the normalized body stored in `data/labeling/`. Never label a copy opened elsewhere; offsets must match the text sent to each engine byte for byte.

## Entity schema

Ten types. Each one is engine-neutral; the adapters map engine types onto these.

| Type | What it covers | Examples |
|---|---|---|
| `PERSON` | A name that refers to a specific individual: full, first only, last only, nickname, or initials used as a name | `Phillip K. Allen`, `Phillip`, `Mr. Allen` (label `Allen` only), `PKA` in a signature |
| `ORGANIZATION` | A named company, agency, institution, or business unit | `Enron North America Corp.`, `El Paso` (when it means the company), `FERC`, `EES` |
| `EMAIL_ADDRESS` | A complete email address | `pallen@enron.com` |
| `PHONE_NUMBER` | Telephone and fax numbers, including country code and extension | `(713) 853-7041`, `713.853.7041 x3`, `+44 20 7783 0000` |
| `ADDRESS` | A street or mailing address, labeled as one span from street number through postal code | `1400 Smith St., Houston, TX 77002` |
| `LOCATION` | A named place that is not part of a street address: city, state, country, region, building, or trading point | `Houston`, `California`, `Henry Hub`, `Enron Center South` |
| `DATE_TIME` | An explicit calendar date or clock time, full or partial | `10/25/2000`, `Oct. 25`, `3:15 PM`, `10/25/2000 03:15 PM` |
| `MONEY` | A monetary amount with a currency symbol or word | `$30k`, `$1.2 million`, `500 dollars`, `$3.50` |
| `URL` | A web address, with or without protocol | `http://www.enron.com/`, `www.caiso.com` |
| `IDENTIFIER` | A string that identifies or unlocks a specific account, person, or record: account, deal, contract, employee, or Social Security numbers; usernames; passwords | `Deal #458721`, `acct 0012-3345`, `password: blue42` (label `blue42`) |

If you find sensitive text that fits none of these types, do not invent a new label mid-batch. Mark the message **Needs review**, describe it in the notes field, and decide it in the edge-case log before continuing.

## General rules

1. **Label every occurrence.** Repeats, quoted replies, forwarded blocks, and signatures all count. Leaks hide in the parts people skim.
2. **Label public figures too.** `Ken Lay` and `Jeff Skilling` are labeled `PERSON`. The task is detection; deciding who is sensitive happens later, in policy.
3. **Smallest complete span.** Include the whole entity and nothing else:
   - No leading or trailing spaces, punctuation, quotes, or brackets.
   - Exclude titles and honorifics (`Mr.`, `Dr.`, `Ms.`) and suffix-style roles (`VP`).
   - Exclude possessive `'s` (`Allen's` → `Allen`).
   - Keep internal punctuation (`Phillip K. Allen`, `Enron Corp.`, `(713) 853-7041`).
   - Exclude labels and qualifiers (`Tel:`, `approximately`, `or more`, `mailto:`).
4. **No overlapping spans.** When one entity sits inside another, label the outer entity only:
   - `pallen@enron.com` is `EMAIL_ADDRESS`, not `PERSON` plus `ORGANIZATION`.
   - `http://www.enron.com/` is `URL`, not `ORGANIZATION`.
   - `Houston` inside a full address is part of `ADDRESS`.
5. **Adjacent parts of one entity are one span.** `10/25/2000 03:15 PM` is a single `DATE_TIME`. `Phillip K. Allen` is a single `PERSON`.
6. **Context decides the type.** `El Paso` is `ORGANIZATION` when it means El Paso Natural Gas and `LOCATION` when it means the city. `John Deere` is `ORGANIZATION`.
7. **When unsure, label it and log it.** If you would want it removed before sharing, label it with the best type, mark the message **Needs review**, and add the case to the log.

## Type-specific rules

**PERSON**
- Label first-name-only references (`Phillip, call me`) and sign-offs (`Thanks, Phil`).
- Label initials when they stand in for a person (`-PKA`), not when they are an abbreviation for something else.
- Generic references (`the trader`, `my boss`) are not labeled.

**ORGANIZATION**
- Include legal suffixes (`Inc.`, `Corp.`, `LLC`).
- Enron business-unit abbreviations (`ECT`, `EES`, `EOL`, `ENA`) are labeled when they appear as words in the text.
- Generic references (`the utility`, `the pipeline`) are not labeled.

**DATE_TIME**
- Label explicit dates and times, including partial dates (`Oct. 25`, `10/25`).
- Do not label relative expressions (`tomorrow`, `next week`), standalone weekdays (`Monday`), standalone years (`2001`), or durations (`two weeks`).
- Record any engine predictions on these excluded forms as false positives; do not change the labels to match an engine.

**MONEY**
- Label the amount with its currency marker only: `$3.50/MMBtu` → `$3.50`.
- An amount needs a currency symbol or currency word to be `MONEY`: `25 cents` is labeled; `50,000 MMBtu` is a volume and is not.

**ADDRESS and LOCATION**
- A street address is one `ADDRESS` span, even when it crosses a line break. Do not split it into street, city, state, and zip.
- Standalone place names are `LOCATION`. Trading points and pipeline delivery points that name a place (`Henry Hub`, `SoCal Border`) are `LOCATION`.

**IDENTIFIER**
- Label the value, not its label: `Deal #458721` → `458721`.
- Phone and fax numbers are `PHONE_NUMBER`, not `IDENTIFIER`.
- Counts, volumes, prices, and percentages are not identifiers.

## Enron-specific patterns

| Pattern | How to label |
|---|---|
| Lotus Notes routing name: `Phillip K Allen/HOU/ECT@ECT` | `Phillip K Allen` → `PERSON`. Leave the routing tag `/HOU/ECT@ECT` unlabeled; it is internal routing, not a name or address. |
| Forward banner: `---- Forwarded by Phillip K Allen/HOU/ECT on 10/25/2000 03:15 PM ----` | `Phillip K Allen` → `PERSON`; `10/25/2000 03:15 PM` → one `DATE_TIME` |
| Quoted header block inside the body (`From:`, `To:`, `Sent:` lines) | Label the values on those lines like any other body text. |
| Same email repeated through a forwarded chain | Label every copy. |

## Mapping engine types to this schema

Adapters convert engine output to these types before scoring. Engine types with no mapping are ignored for type-aware scoring but still count for the leak test.

**Tonic Textual (built-in types)**

| Schema type | Textual types | Adapter note |
|---|---|---|
| `PERSON` | `NAME_GIVEN`, `NAME_FAMILY` | Merge adjacent given and family spans separated only by spaces, periods, or a middle initial. |
| `ORGANIZATION` | `ORGANIZATION` | |
| `EMAIL_ADDRESS` | `EMAIL_ADDRESS` | |
| `PHONE_NUMBER` | `PHONE_NUMBER` | |
| `ADDRESS` | `LOCATION_ADDRESS`, `LOCATION_COMPLETE_ADDRESS` | Merge a `LOCATION_ADDRESS` span with following `LOCATION_CITY`, `LOCATION_STATE`, and `LOCATION_ZIP` spans separated only by commas, spaces, or line breaks. `LOCATION_COMPLETE_ADDRESS` is ignored by default in Textual datasets; record whether it is on. |
| `LOCATION` | `LOCATION`, `LOCATION_CITY`, `LOCATION_STATE`, `LOCATION_ZIP`, `LOCATION_COUNTRY` | Only when not merged into an `ADDRESS`. |
| `DATE_TIME` | `DATE_TIME`, `DOB` | |
| `MONEY` | `MONEY` | |
| `URL` | `URL` | |
| `IDENTIFIER` | `ACCOUNT_NUMBER`, `NUMERIC_PII`, `US_SSN`, `US_BANK_NUMBER`, `US_ROUTING_TRANSIT_NUMBER`, `CREDIT_CARD`, `DRIVERS_LICENSE_NUMBER`, `US_PASSPORT`, `US_ITIN`, `USERNAME`, `PASSWORD` | |
| (not scored) | `NUMERIC_VALUE`, `OCCUPATION`, `PRODUCT`, `EVENT`, `LAW`, `LANGUAGE`, `NRP`, `GENDER_IDENTIFIER`, `PERSON_AGE`, `IP_ADDRESS`, and other types | Ignored for type-aware scores. A labeled span covered only by one of these still counts as covered in the leak test. |

Source: Tonic Textual built-in entity types, docs.tonic.ai (checked November 1, 2026). Re-check when Textual updates its model.

## How each metric uses the labels

- **Strict:** same type and exact start and end offsets.
- **Overlap (headline):** same type and any character overlap.
- **Leak test:** type ignored. A labeled span leaks if no predicted span of any type covers any of its characters. Example: Textual tagging `John Deere` as `NAME_GIVEN` and `NAME_FAMILY` is a type error (one `PERSON` false positive, one `ORGANIZATION` miss) but not a leak.

## Quality check

After about a week, re-label 10 messages blind (without viewing the earlier labels) and score them against the originals with the same scorer. An overlap F1 at or above 0.9 means the labels are consistent. Each disagreement points to a rule that needs to be written down here.

## Edge-case log

Add a row for every case decided during labeling. Cite the message ID so the decision can be re-checked.

| Date | Message ID | Text | Decision | Rule updated |
|---|---|---|---|---|
| 2026-11-01 | (playground) | `John Deere` | `ORGANIZATION` | General rule 6 |
| 2026-11-01 | (playground) | `$30k or more` | `MONEY` on `$30k` only | General rule 3 |

## Changelog

- **0.1 (2026-11-01):** Initial schema (10 types), general and type-specific rules, Enron patterns, Textual mapping, metric definitions.

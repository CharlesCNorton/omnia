# Bookplate Template

Every formalization in OMNIA opens with a bookplate: a fixed-width comment block identifying the work, its scope, and its author.

## Template

```coq
(******************************************************************************)
(*                                                                            *)
(*                         [TITLE OF FORMALIZATION]                           *)
(*                                                                            *)
(*     [One to three lines describing the formalization's scope, key          *)
(*     theorems, and relationship to prior work. Keep lines under 76 chars.]  *)
(*                                                                            *)
(*     "[Epigraph: a quote reflecting the spirit of the work.]"               *)
(*     - [Attribution, Year]                                                  *)
(*                                                                            *)
(*     Author: Charles C. Norton                                              *)
(*     Date: [Month Day, Year]                                                *)
(*     License: [License Name]                                                *)
(*                                                                            *)
(******************************************************************************)
```

## Rules

1. **Width**: 80 characters exactly, including the outer parentheses.
2. **Border**: `(*` and `*)` with 76 asterisks on top and bottom lines.
3. **Padding**: Each content line starts with `(*` + 5 spaces and ends with spaces + `*)`.
4. **Title**: Centered, capitalized or title case.
5. **Description**: Left-aligned within the padding. Summarize what is formalized, key results, and any extensions or limitations.
6. **Epigraph**: A relevant quote in double quotes, followed by attribution on the next line with en-dash.
7. **Author/Date/License**: Left-aligned. Use full month name for date.

## Example

```coq
(******************************************************************************)
(*                                                                            *)
(*       Origami Constructibility: Cubic Extensions of Euclidean Geometry     *)
(*                                                                            *)
(*     Huzita-Hatori axioms (O1-O7) with existence proofs. Single-fold        *)
(*     origami strictly extends compass-straightedge; the heptagon is         *)
(*     constructible; the hendecagon requires 2-fold.                         *)
(*                                                                            *)
(*     "Out of nothing I have created a strange new universe."                *)
(*     - Janos Bolyai, 1823                                                   *)
(*                                                                            *)
(*     Author: Charles C. Norton                                              *)
(*     Date: November 28, 2025                                                *)
(*     License: MIT                                                           *)
(*                                                                            *)
(******************************************************************************)
```

## Repository Naming

Repositories follow the pattern `[name]-verified` where `[name]` is:
- Lowercase alphanumeric with hyphens
- Descriptive of the domain, not the proof technique
- Short (one to three words)

Examples:
- `gcs-verified` (Glasgow Coma Scale)
- `rap-verified` (Rule Against Perpetuities)
- `morse-verified` (Morse code)

Avoid:
- Generic names (`proof-verified`, `theorem-verified`)
- Version numbers or dates
- Abbreviations without clear meaning

## Repository Description

Descriptions follow the pattern: **"Formalizing [4-5 words]."**

Examples:
- "Formalizing Glasgow Coma Scale scoring."
- "Formalizing Rule Against Perpetuities."
- "Formalizing Babylonian base-60 arithmetic."

The description appears in GitHub search and repo listings. Keep it terse.

## Repository Tags

Every repository has exactly three tags:
1. `proof` (always first)
2. Domain category (e.g., `medicine`, `law`, `history`, `chemistry`)
3. Subdomain (e.g., `neurology`, `property`, `feudalism`, `nomenclature`)

Examples:
- `proof`, `medicine`, `cardiology`
- `proof`, `law`, `commerce`
- `proof`, `mathematics`, `notation`

Tags enable discovery. Choose the most specific accurate subdomain.

## Selecting an Epigraph

Choose a quote that:
- Reflects the intellectual spirit of the domain (not the proof itself).
- Comes from a historical figure connected to the subject, or a mathematician/scientist whose work inspired it.
- Is brief (one to two lines maximum).

Avoid:
- Generic motivational quotes.
- Jokes or memes.
- Anything requiring explanation.

## Contract Clause (Alternative)

For AI-oriented tooling, the epigraph slot may contain a contract specification — preconditions, postconditions, and guarantees — in place of a traditional quote.

## Workflow

1. Select candidate from `toadd.md`
2. Prepare for review: bookplate, repo name, description, tags
3. On approval:
   - Create repo on GitHub with description and tags
   - Add `.v` file containing only the bookplate
   - Commit to repo: `Initial bookplate`
4. Update `INDEX.md` (insert alphabetically)
5. Remove entry from `toadd.md`
6. Commit to omnia: `Add [name]-verified`

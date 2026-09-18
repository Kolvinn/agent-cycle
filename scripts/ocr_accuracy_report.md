# C#-to-PNG OCR Accuracy Experiment

**Subject file:** `scripts/CrmDbContext.cs` (247 lines, 1602 words, 15,624 bytes, 1038 lexer tokens, 5,2xx minified chars)
**Renderer:** `scripts/test2.py` (token-safe wrap — line breaks only ever fall between lexer tokens, never mid-identifier), Pygments `CSharpLexer` + `ImageFormatter`, `monokai` style, `DejaVu Sans Mono`, 1000×1000px page budget.
**Method:** for each variant, an isolated fresh agent was given *only* the resulting PNG page(s) (no source file access) and asked the same 8 precise structural questions about the DbContext (namespace/constructor, all 32 `DbSet<T>` properties in order, the pre-`ApplyConfiguration` setup calls, all 32 `ApplyConfiguration` calls in order, `ConfigureNpgsql` body, `ConfigureConventions` body, `SaveChangesAsync` logic, and the second `SaveChangesAsync` overload). A separate agent with *only* the `.cs` file established ground truth (verified 100% correct against the file by direct diff).

## Bug found mid-experiment

The first pass at font sizes 20/24/28 (multi-page) came back with agents reporting pages 2+ as "corrupted / double-exposed / overlapping text." Verified by direct visual inspection — real corruption, not an OCR failure. Root cause: `pygments.formatters.img.ImageFormatter` accumulates every drawn glyph into `self.drawables` and **never clears it** between `.format()` calls (confirmed in library source: initialized once in `__init__`, only ever appended to). Both `test.py` and `test2.py` were reusing one `ImageFormatter` instance across all pages of a multi-page render, so page 2 got page 1's text ghosted underneath it, page 3 would get pages 1+2, etc. This had been silently corrupting every page after the first since pagination was added in this session — only pixel *dimensions* had been checked before, not page content past page 1.

**Fix:** both scripts now build a fresh `ImageFormatter` per page (see `make_formatter()` in each). Re-verified visually: no ghosting in any regenerated page. All results below are post-fix.

## Variables tested

Font size was the only independent variable (12, 16, 20, 24, 28pt). Everything else — wrap strategy (token-safe), style, page pixel budget (1000×1000), source file — was held constant.

| Font size | Char width (px) | Chars/line | Lines/page | Pages | Total chars rendered | Page pixel dimensions |
|---|---|---|---|---|---|---|
| 12 | 7 | 142 | 83 | 1 | 5,238 | 997×468 |
| 16 | 10 | 100 | 62 | 1 | 5,236 | 1000×840 |
| 20 | 12 | 83 | 50 | 2 | 5,223 | 998×950, 996×361 |
| 24 | 14 | 71 | 41 | 3 | 5,214 | 994×943, 996×943, 812×46 |
| 28 | 17 | 58 | 35 | 3 | 5,230 | 986×910, 986×910, 986×806 |

(Total rendered chars is roughly constant across variants — same source, same minification — small deltas come from where wrap forces a line break relative to whitespace.)

## Results

Ground truth = 32/32 `DbSet<T>` properties, 32/32 `ApplyConfiguration` calls, exact `ConfigureNpgsql` (2 statements), exact `ConfigureConventions` (3 statements), exact `SaveChangesAsync` body (`ChangeTracker.Entries<Person>()`, `PersonName.Compose(entry.Entity)`, `base.SaveChangesAsync(...)`), exact second overload.

| Font size | Pages | DbSets correct | ApplyConfig correct | ConfigureNpgsql | ConfigureConventions | SaveChangesAsync | 2nd overload | Overall |
|---|---|---|---|---|---|---|---|---|
| 12 | 1 | ~27/32 (order swaps, 2 fabricated names: `ProviderAdviser`/`EntityPair` singularized, `Workspace`+`WorkspaceAssignment` merged, `CardValue`/`FieldValues` garbled) | ~29/32 (missing `WorkspaceConfiguration`, misnamed `IdempotencyConfiguration`→`IdempotencyRecordConfiguration`, fabricated `CardValueConfiguration`) | **Wrong** (`"EfMigrationsHistory"` vs actual `"__EFMigrationsHistory"`) | Missing 1/3 (dropped `WolverineSchemaExcludedFromMigrationsConvention`) | Correct | Correct | **Fail — several concrete errors** |
| 16 | 1 | 32/32 | 32/32 | Correct | 3/3 correct | Correct | Correct | **Pass — perfect** |
| 20 | 2 | 32/32 | 32/32 | Correct | 3/3 correct | Correct | Correct | **Pass — perfect** |
| 24 | 3 | 32/32 | 32/32 | Correct | 3/3 correct | Correct | Correct | **Pass — perfect** |
| 28 | 3 | 32/32 | 32/32 | Correct | 3/3 correct | Correct | Correct | **Pass — perfect** |

## Conclusion

There is a sharp accuracy cliff between font size 12 and 16 for this renderer/model combination, not a gradual falloff:

- **12pt (7px char width) is too dense** — the model mis-reads specific tokens (fabricates plausible-sounding but nonexistent class/property names, drops list entries, misreads literal strings) even though it self-reports fairly high confidence. This happened consistently across *every* 12pt variant tested in this session (three separate runs, two different wrap strategies), so it's a reproducible density threshold, not one bad OCR pass.
- **16pt and above (10px+ char width) is fully reliable** for this file — 4/4 independent agents at 16/20/24/28pt scored a perfect 8/8 against ground truth, including exact literal strings (`"__EFMigrationsHistory"`, `"harness_number_seq"`) and exact generic-type ordering across page boundaries.
- Splitting into more pages (font 20/24/28) costs more images/agent calls but **does not hurt accuracy** — token-safe wrap plus a properly-isolated formatter per page means content boundaries between pages never caused a misread, even when a statement's tokens were split across two page images.
- The practical recommendation for this renderer: **use font_size ≥ 16**, never 12, regardless of how many pages that requires. 12pt only wins on page count/token cost, and only by trading away correctness.

## Caveat

This is a single-file, single-model, single-run-per-cell experiment (n=1 per font size, except 12pt at n≈3 across sessions). Treat the 12→16 cliff as a strong signal for *this* font/style/model combination, not a universal constant — a different font, style, or image resolution downscaling behavior could shift the threshold.

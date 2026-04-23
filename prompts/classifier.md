# Classifier prompt - qualifies an article or rejects it

Decide if a CBP article qualifies for Hebrew translation.

## Qualifies if the article describes a CBP seizure of ONE OR MORE of:
   - Drugs (cocaine, meth, fentanyl, heroin, marijuana, pills, tablets, etc.)
   - Firearms or weapons (guns, ammunition, explosives)
   - Animals, wildlife, or any living creatures (live animals, insects, birds, fish, wildlife parts such as ivory, hides, feathers, shells)
   - Plants (narcotic plants, agricultural contraband, restricted seeds, prohibited vegetation)

The article must describe an actual seizure event with quantities, weights, or specific details — not just a general policy or statistics report.

## Does NOT qualify

- Personnel announcements, awards, retirements.
- Policy or rule updates.
- Currency-only seizures (no drugs/weapons/animals/plants).
- Statistics or year-in-review reports with no specific seizure described.
- General enforcement updates with no specific seized items.

## Response format

Respond with exactly one line:
- `YES` if qualifies.
- `NO:<short reason>` if not.

Examples:
- `YES`
- `NO: currency seizure only`
- `NO: personnel announcement`
- `NO: statistics report, no specific seizure`
- `NO: policy update`

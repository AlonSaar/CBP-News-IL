# Classifier prompt - qualifies an article or rejects it

Decide if a CBP article qualifies for Hebrew translation.

## Qualifies if the article describes a CBP seizure or interdiction of ONE OR MORE of:
   - Drugs (cocaine, meth, fentanyl, heroin, marijuana, pills, tablets, etc.)
   - Firearms or weapons (guns, ammunition, explosives)
   - Animals, wildlife, or any living creatures (live animals, insects, birds, fish, wildlife parts such as ivory, hides, feathers, shells)
   - Plants (narcotic plants, agricultural contraband, restricted seeds, prohibited vegetation)
   - Food or agricultural products (prohibited meat, produce, smuggled food items, agricultural contraband)
   - Migrants or persons CONCEALED inside a vehicle, truck, trailer, compartment, car trunk, or cargo — i.e. physical smuggling using a vehicle or structure to hide people while crossing a port of entry.

The article must describe an actual seizure or interdiction event with specific details — not just a general policy or statistics report.

## Does NOT qualify

- Articles with no photo (if "Has image URL: False" — reject immediately).
- Personnel announcements, awards, retirements.
- Policy or rule updates.
- Currency-only seizures (no drugs/weapons/animals/plants/persons).
- Statistics or year-in-review reports with no specific seizure described.
- General enforcement updates with no specific seized items.
- Migrants or persons apprehended while walking / crossing on foot — even between ports of entry. Only qualify if they were physically hidden inside a vehicle or structure.

## Response format

Respond with exactly one line:
- `YES` if qualifies.
- `NO:<short reason>` if not.

Examples:
- `YES`
- `NO: currency seizure only`
- `NO: personnel announcement`
- `NO: statistics report, no specific seizure`
- `NO: migrants on foot, not concealed in vehicle`

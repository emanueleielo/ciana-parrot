---
name: google-places
description: "Search for places, restaurants, businesses via Google Places API. Use when user asks about nearby locations. Requires GOOGLE_PLACES_API_KEY."
requires_env:
  - GOOGLE_PLACES_API_KEY
---

# Google Places

Search for places, restaurants, shops, and businesses.

## When to Use

- "Find a restaurant near [location]"
- "Where's the nearest pharmacy?"
- "Best coffee shops in [city]"
- "Opening hours of [place]"

## Text Search

```bash
curl -s -X POST "https://places.googleapis.com/v1/places:searchText" \
  -H "Content-Type: application/json" \
  -H "X-Goog-Api-Key: $GOOGLE_PLACES_API_KEY" \
  -H "X-Goog-FieldMask: places.displayName,places.formattedAddress,places.rating,places.userRatingCount" \
  -d '{"textQuery": "pizza restaurants in Rome"}'
```

## Place Details

```bash
curl -s "https://places.googleapis.com/v1/places/PLACE_ID" \
  -H "X-Goog-Api-Key: $GOOGLE_PLACES_API_KEY" \
  -H "X-Goog-FieldMask: displayName,formattedAddress,rating,currentOpeningHours,websiteUri,nationalPhoneNumber"
```

## Nearby Search

```bash
curl -s -X POST "https://places.googleapis.com/v1/places:searchNearby" \
  -H "Content-Type: application/json" \
  -H "X-Goog-Api-Key: $GOOGLE_PLACES_API_KEY" \
  -H "X-Goog-FieldMask: places.displayName,places.formattedAddress,places.rating" \
  -d '{
    "includedTypes": ["restaurant"],
    "maxResultCount": 10,
    "locationRestriction": {
      "circle": {
        "center": {"latitude": 41.9028, "longitude": 12.4964},
        "radius": 1000.0
      }
    }
  }'
```

## Field Masks

Control which fields are returned (and billed):
- Basic: `displayName,formattedAddress,location`
- Contact: `nationalPhoneNumber,websiteUri`
- Atmosphere: `rating,userRatingCount,reviews,currentOpeningHours`

## Notes

- Uses Places API (New) — pay per request
- FieldMask controls cost: request only needed fields
- Results language matches the query language

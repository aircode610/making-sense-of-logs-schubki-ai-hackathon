---
title: Geospatial Search
sidebar_position: 28
split: page
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

# Geospatial Search

"Near me" is a search too. The [inverted index](../../sql/indexes/inverted/index.md) keeps geometry next to text, so a distance filter runs on the same index that answers your keyword queries and you can mix the two in one `WHERE`. Here you find shops within a radius, inside a distance band and near a location that also matches a name, then bucket every point into a heatmap grid.

The shops are a coffee chain scattered across the Bay Area. `geo` is a `GEOMETRY` column indexed with an `encode_geojson` dictionary using `s2point` coding, coordinates run `longitude latitude` and every distance is geodesic metres.

<details>
<summary>Schema and sample data</summary>

```sql
CREATE TEXT SEARCH DICTIONARY geo_s2 AS encode_geojson(coding := 's2point');

CREATE TABLE shops (id INTEGER PRIMARY KEY, name VARCHAR, geo GEOMETRY('OGC:CRS84'));

CREATE INDEX shops_idx ON shops USING inverted (id, name, geo geo_s2);

INSERT INTO shops VALUES
(1, 'Blue Bottle',    'POINT(-122.4010 37.7905)'::GEOMETRY('OGC:CRS84')),
(2, 'Ritual',         'POINT(-122.4050 37.7920)'::GEOMETRY('OGC:CRS84')),
(3, 'Sightglass',     'POINT(-122.3990 37.7885)'::GEOMETRY('OGC:CRS84')),
(4, 'Philz',          'POINT(-122.4500 37.7600)'::GEOMETRY('OGC:CRS84')),
(5, 'Peets',          'POINT(-122.3000 37.8500)'::GEOMETRY('OGC:CRS84')),
(6, 'Red Bay',        'POINT(-122.2700 37.8100)'::GEOMETRY('OGC:CRS84')),
(7, 'Bicycle Coffee', 'POINT(-122.2500 37.8800)'::GEOMETRY('OGC:CRS84')),
(8, 'Highwire',       'POINT(-122.2700 37.9200)'::GEOMETRY('OGC:CRS84')),
(9, 'Timeless',       'POINT(-122.2500 37.9500)'::GEOMETRY('OGC:CRS84'));

VACUUM (REFRESH_TABLE) shops;
```

</details>

## Within a radius

[`ST_Distance_Centroid`](../../sql/functions/search/geo.md) returns the metres from the indexed point to your location. Compare it to a radius and you have "walkable from the office".

```sql
SELECT id, name
FROM shops_idx
WHERE ST_Distance_Centroid(geo, 'POINT(-122.4000 37.7900)'::GEOMETRY('OGC:CRS84')) < 1000
ORDER BY id;
-- result:
id	name
1	Blue Bottle
2	Ritual
3	Sightglass
```

## Inside a distance band

[`ST_Distance_Between`](../../sql/functions/search/geo.md) takes a min and a max, so it carves out a ring. Here is the "too far to walk but worth a drive" band from one to ten kilometres.

```sql
SELECT id, name
FROM shops_idx
WHERE ST_Distance_Between(geo, 'POINT(-122.4000 37.7900)'::GEOMETRY('OGC:CRS84'), 1000, 10000)
ORDER BY id;
-- result:
id	name
4	Philz
```

## Near and named

Because geometry and text share the index, a location filter and a name match combine into one query with no join. This finds the shop near the office whose name starts with "Sight".

```sql
SELECT id, name
FROM shops_idx
WHERE ST_Distance_Centroid(geo, 'POINT(-122.4000 37.7900)'::GEOMETRY('OGC:CRS84')) < 1000
  AND name @@ ts_like('Sight%')
ORDER BY id;
-- result:
id	name
3	Sightglass
```

## Bucket points into a heatmap grid

A heatmap wants points rolled up into cells: snap every location onto a grid and count what lands in each square. There is no `geohash_grid` aggregation here, so the grid is hand-rolled: read each point's coordinates with [`ST_X`](../../sql/functions/geometry.md#st_x-function) and `ST_Y`, truncate them to a fixed step and group on the result. That is a full scan rather than an index lookup, but the counts are exact and you pick the cell size.

### Count points per cell

Truncating each coordinate to a tenth of a degree snaps every point to the south-west corner of a roughly ten kilometre cell. Group on the two truncated values and `count(*)` is the cell density, hottest cell first.

```sql
WITH pts AS (
  SELECT ST_X(geo) AS lon, ST_Y(geo) AS lat
  FROM shops
)
SELECT
  CAST(floor(lon * 10) / 10 AS DECIMAL(6,1)) AS cell_lon,
  CAST(floor(lat * 10) / 10 AS DECIMAL(6,1)) AS cell_lat,
  count(*) AS shops
FROM pts
GROUP BY cell_lon, cell_lat
ORDER BY shops DESC, cell_lon, cell_lat;
-- result:
cell_lon	cell_lat	shops
-122.5	37.7	3
-122.3	37.8	3
-122.3	37.9	2
-122.4	37.7	1
```

### Drop the sparse cells

A heatmap does not care about a cell holding one stray shop. `HAVING count(*) >= 2` keeps only the squares worth painting (`min_doc_count`, if you come from Elastic).

```sql
WITH pts AS (
  SELECT ST_X(geo) AS lon, ST_Y(geo) AS lat
  FROM shops
)
SELECT
  CAST(floor(lon * 10) / 10 AS DECIMAL(6,1)) AS cell_lon,
  CAST(floor(lat * 10) / 10 AS DECIMAL(6,1)) AS cell_lat,
  count(*) AS shops
FROM pts
GROUP BY cell_lon, cell_lat
HAVING count(*) >= 2
ORDER BY shops DESC, cell_lon, cell_lat;
-- result:
cell_lon	cell_lat	shops
-122.5	37.7	3
-122.3	37.8	3
-122.3	37.9	2
```

### Zoom into a cell

Click the hottest square and you want the shops behind the number. Filter on the same truncated coordinates to list every point in that cell with its exact location.

```sql
WITH pts AS (
  SELECT id, name, ST_AsText(geo) AS location, ST_X(geo) AS lon, ST_Y(geo) AS lat
  FROM shops
)
SELECT id, name, location
FROM pts
WHERE CAST(floor(lon * 10) / 10 AS DECIMAL(6,1)) = -122.5
  AND CAST(floor(lat * 10) / 10 AS DECIMAL(6,1)) = 37.7
ORDER BY id;
-- result:
id	name	location
1	Blue Bottle	POINT (-122.401 37.7905)
2	Ritual	POINT (-122.405 37.792)
4	Philz	POINT (-122.45 37.76)
```

## See also

- [Geospatial Search guide](../../sql/indexes/inverted/geospatial-search.md): indexing polygons, GeoJSON columns and the lat/lon `encode_geopoint` template
- [Geo functions reference](../../sql/functions/search/geo.md): `ST_Intersects`, `ST_Contains`, `ST_Distance_Between`, `ST_Distance_Centroid` and the `<->` operator
- [Faceted Search](./faceted-search.md): combine a location filter with facet counts over the survivors


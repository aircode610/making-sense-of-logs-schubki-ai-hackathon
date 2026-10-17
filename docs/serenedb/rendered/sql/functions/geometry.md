---
title: Geometry Functions
split: headings
---

import SqlLogicTest from "@site/src/components/SqlLogicTest";

This section describes the built-in functions for examining and manipulating [`GEOMETRY`](../../sql/data_types/geometry.md) values.

Geometry operations run on [Boost.Geometry](https://www.boost.org/doc/libs/release/libs/geometry/). Function names and argument order follow PostGIS, but the set of functions is smaller and a few behaviours differ; see [Differences from PostGIS](#differences-from-postgis) at the end of this page.

## Geometry Operators

The table below lists the operators that can be used with `GEOMETRY` values.

| Operator | Description | Example | Result |
| :------- | :---------- | :------ | :----- |
| `&&` | Returns true if the geometries bounding boxes intersect. Equivalent to [`ST_Intersects_Extent`](#st_intersects_extent-function). | `'POINT(5 5)'::GEOMETRY && 'LINESTRING(0 0, 10 20)'::GEOMETRY` | `true` |

## Constructing Geometries

| Name | Description |
| :--- | :---------- |
| [`ST_Point(x, y)`](#st_point-function) | Creates a point from an X and a Y coordinate |
| [`ST_MakeLine(start, end)`](#st_makeline-function) | Creates a line between two points |
| [`ST_MakeLine(geoms)`](#st_makeline-list-function) | Creates a line through a list of points |
| [`ST_MakePolygon(shell[, holes])`](#st_makepolygon-function) | Creates a polygon from a closed ring, optionally with holes |
| [`ST_MakeEnvelope(min_x, min_y, max_x, max_y)`](#st_makeenvelope-function) | Creates a rectangular polygon from minimum and maximum bounds |
| [`ST_Collect(geoms)`](#st_collect-function) | Collects a list of geometries into a multi-geometry |
| [`ST_Points(geom)`](#st_points-function) | Collects every vertex of a geometry into a `MULTIPOINT` |
| [`ST_Multi(geom)`](#st_multi-function) | Wraps a single geometry in the matching multi-geometry |

#### `ST_Point(x, y)` {#st_point-function}

Creates a point from an X and a Y coordinate.

```sql
SELECT ST_AsText(ST_Point(1, 2)) AS geom;
-- result:
geom
POINT (1 2)
```

#### `ST_MakeLine(start, end)` {#st_makeline-function}

Creates a line from the point `start` to the point `end`.

```sql
SELECT ST_AsText(ST_MakeLine('POINT(0 0)'::GEOMETRY, 'POINT(2 2)'::GEOMETRY)) AS geom;
-- result:
geom
LINESTRING (0 0, 2 2)
```

#### `ST_MakeLine(geoms)` {#st_makeline-list-function}

Creates a line through a list of points, in list order.

#### `ST_MakePolygon(shell[, holes])` {#st_makepolygon-function}

Creates a polygon from the closed ring `shell`. The optional `holes` supplies a list of interior rings.

```sql
SELECT ST_AsText(ST_MakePolygon('LINESTRING(0 0,4 0,4 4,0 0)'::GEOMETRY)) AS geom;
-- result:
geom
POLYGON ((0 0, 4 0, 4 4, 0 0))
```

#### `ST_MakeEnvelope(min_x, min_y, max_x, max_y)` {#st_makeenvelope-function}

Creates a rectangular polygon from `min_x`, `min_y`, `max_x` and `max_y`.

```sql
SELECT ST_AsText(ST_MakeEnvelope(0, 0, 2, 1)) AS geom;
-- result:
geom
POLYGON ((0 0, 0 1, 2 1, 2 0, 0 0))
```

#### `ST_Collect(geoms)` {#st_collect-function}

Collects an array of geometries into one geometry. Geometries of one type become the matching multi-geometry, mixed types become a `GEOMETRYCOLLECTION`. `NULL` elements are skipped, and an empty array or an array of only `NULL`s yields `NULL`, as in PostGIS.

```sql
SELECT ST_AsText(ST_Collect(ARRAY['POINT(0 0)'::GEOMETRY, 'POINT(1 1)'::GEOMETRY])) AS geom;
-- result:
geom
MULTIPOINT (0 0, 1 1)
```

#### `ST_Points(geom)` {#st_points-function}

Collects every vertex of a geometry into a `MULTIPOINT`.

```sql
SELECT ST_AsText(ST_Points('LINESTRING(0 0,1 1)'::GEOMETRY)) AS geom;
-- result:
geom
MULTIPOINT (0 0, 1 1)
```

#### `ST_Multi(geom)` {#st_multi-function}

Wraps a single geometry in the matching multi-geometry. A geometry that is already a multi-geometry is returned unchanged.

```sql
SELECT ST_AsText(ST_Multi('POINT(1 2)'::GEOMETRY)) AS geom;
-- result:
geom
MULTIPOINT (1 2)
```

## Reading and Writing Formats

| Name | Description | Aliases |
| :--- | :---------- | :------ |
| [`ST_GeomFromText(wkt[, ignore_invalid])`](#st_geomfromtext-function) | Creates a geometry from Well-Known Text (WKT) | |
| [`ST_GeomFromWKB(wkb)`](#st_geomfromwkb-function) | Creates a geometry from Well-Known Binary (WKB) | |
| [`ST_GeomFromGeoJSON(geojson)`](#st_geomfromgeojson-function) | Creates a geometry from a GeoJSON object | |
| [`ST_AsWKT(geom)`](#st_aswkt-function) | Returns the Well-Known Text (WKT) representation | `ST_AsText` |
| [`ST_AsWKB(geom)`](#st_aswkb-function) | Returns the Well-Known Binary (WKB) representation | `ST_AsBinary` |
| [`ST_AsHEXWKB(geom)`](#st_ashexwkb-function) | Returns the WKB representation as a hexadecimal string | |
| [`ST_AsGeoJSON(geom)`](#st_asgeojson-function) | Returns the GeoJSON representation | |
| [`ST_AsSVG(geom, relative, precision)`](#st_assvg-function) | Returns the SVG path data for the geometry | |

#### `ST_GeomFromText(wkt[, ignore_invalid])` {#st_geomfromtext-function}

Creates a geometry from Well-Known Text (WKT).

```sql
SELECT ST_AsText(ST_GeomFromText('POINT(1 2)')) AS geom;
-- result:
geom
POINT (1 2)
```

Pass `ignore_invalid := true` to get `NULL` for text that does not parse instead of an error. The argument only takes effect when it is named: a positional `true` is ignored.

```sql
SELECT ST_GeomFromText('POINT(1', ignore_invalid := true) IS NULL AS skipped;
-- result:
skipped
t
```

#### `ST_GeomFromWKB(wkb)` {#st_geomfromwkb-function}

Creates a geometry from Well-Known Binary (WKB) representation.

```sql
SELECT ST_AsText(ST_GeomFromWKB('\x0101000000000000000000f03f0000000000000040'::BLOB)) AS geom;
-- result:
geom
POINT (1 2)
```

#### `ST_GeomFromGeoJSON(geojson)` {#st_geomfromgeojson-function}

Creates a geometry from a GeoJSON object.

```sql
SELECT ST_AsText(ST_GeomFromGeoJSON('{"type":"Point","coordinates":[1,2]}')) AS geom;
-- result:
geom
POINT (1 2)
```

#### `ST_AsWKT(geom)` {#st_aswkt-function}

Returns the Well-Known Text (WKT) representation of the geometry. Alias: `ST_AsText`.

```sql
SELECT ST_AsText('POINT(1 2)'::GEOMETRY) AS wkt;
-- result:
wkt
POINT (1 2)
```

#### `ST_AsWKB(geom)` {#st_aswkb-function}

Returns the Well-Known Binary (WKB) representation of the geometry. Alias: `ST_AsBinary`.

```sql
SELECT ST_AsWKB('POINT(1 2)'::GEOMETRY) AS wkb;
-- result:
wkb
\\x0101000000000000000000f03f0000000000000040
```

#### `ST_AsHEXWKB(geom)` {#st_ashexwkb-function}

Returns the WKB representation as a hexadecimal string.

```sql
SELECT ST_AsHEXWKB('POINT(1 2)'::GEOMETRY) AS hexwkb;
-- result:
hexwkb
0101000000000000000000F03F0000000000000040
```

#### `ST_AsGeoJSON(geom)` {#st_asgeojson-function}

Returns the GeoJSON representation of the geometry.

```sql
SELECT ST_AsGeoJSON('POINT(1 2)'::GEOMETRY) AS geojson;
-- result:
geojson
{"type":"Point","coordinates":[1.0,2.0]}
```

#### `ST_AsSVG(geom, relative, precision)` {#st_assvg-function}

Returns the SVG path data for the geometry. `relative` selects relative moves and `precision` sets the number of decimal digits.

```sql
SELECT ST_AsSVG('POINT(1 2)'::GEOMETRY, false, 2) AS svg;
-- result:
svg
cx="1" cy="-2"
```

## Accessing Properties

| Name | Description | Aliases |
| :--- | :---------- | :------ |
| [`ST_GeometryType(geom)`](#st_geometrytype-function) | Returns the geometry type | |
| [`ST_Dimension(geom)`](#st_dimension-function) | Returns the topological dimension (0, 1 or 2) | |
| [`ST_X(geom)`](#st_x-function) | Returns the X coordinate of a point | |
| [`ST_Y(geom)`](#st_y-function) | Returns the Y coordinate of a point | |
| [`ST_Z(geom)`](#st_z-function) | Returns the Z coordinate of a point | |
| [`ST_M(geom)`](#st_m-function) | Returns the M coordinate of a point | |
| [`ST_XMin(geom)`](#st_xmin-function) | Returns the smallest X of the geometry's extent | |
| [`ST_XMax(geom)`](#st_xmax-function) | Returns the largest X of the geometry's extent | |
| [`ST_YMin(geom)`](#st_ymin-function) | Returns the smallest Y of the geometry's extent | |
| [`ST_YMax(geom)`](#st_ymax-function) | Returns the largest Y of the geometry's extent | |
| [`ST_ZMin(geom)`](#st_zmin-function) | Returns the smallest Z of the geometry's extent | |
| [`ST_ZMax(geom)`](#st_zmax-function) | Returns the largest Z of the geometry's extent | |
| [`ST_NPoints(geom)`](#st_npoints-function) | Returns the number of vertices | `ST_NumPoints` |
| [`ST_NumGeometries(geom)`](#st_numgeometries-function) | Returns the number of geometries in a collection | |
| [`ST_NumInteriorRings(geom)`](#st_numinteriorrings-function) | Returns the number of interior rings of a polygon | |
| [`ST_ExteriorRing(geom)`](#st_exteriorring-function) | Returns the exterior ring of a polygon | |
| [`ST_InteriorRingN(geom, n)`](#st_interiorringn-function) | Returns the nth interior ring of a polygon | |
| [`ST_PointN(geom, index)`](#st_pointn-function) | Returns the nth vertex of a line | |
| [`ST_StartPoint(geom)`](#st_startpoint-function) | Returns the first vertex of a line | |
| [`ST_EndPoint(geom)`](#st_endpoint-function) | Returns the last vertex of a line | |
| [`ST_Dump(geom)`](#st_dump-function) | Expands a collection into its parts with their paths | |
| [`ST_CollectionExtract(geom[, type])`](#st_collectionextract-function) | Extracts the elements of one dimension from a collection | |
| [`ST_HasZ(geom)`](#st_hasz-function) | Reports whether the geometry carries Z coordinates | |
| [`ST_HasM(geom)`](#st_hasm-function) | Reports whether the geometry carries M coordinates | |
| [`ST_ZMFlag(geom)`](#st_zmflag-function) | Returns a code for the coordinate dimensions | |
| [`ST_Extent(geom)`](#st_extent-function) | Returns the bounding box of the geometry | |

#### `ST_GeometryType(geom)` {#st_geometrytype-function}

Returns the geometry type, such as `POINT` or `LINESTRING`.

```sql
SELECT ST_GeometryType('LINESTRING(0 0,1 1)'::GEOMETRY) AS type;
-- result:
type
LINESTRING
```

#### `ST_Dimension(geom)` {#st_dimension-function}

Returns the topological dimension: `0` for points, `1` for lines, `2` for areas.

```sql
SELECT ST_Dimension('LINESTRING(0 0,2 2)'::GEOMETRY) AS dim;
-- result:
dim
1
```

#### `ST_X(geom)` {#st_x-function}

Returns the X coordinate of a point. The example also shows `ST_Y`.

```sql
SELECT ST_X('POINT(30 10)'::GEOMETRY) AS x, ST_Y('POINT(30 10)'::GEOMETRY) AS y;
-- result:
x	y
30	10
```

#### `ST_Y(geom)` {#st_y-function}

Returns the Y coordinate of a point. See the `ST_X` example.

#### `ST_Z(geom)` {#st_z-function}

Returns the Z coordinate of a point, or `NULL` when the geometry does not carry Z. The example also shows `ST_M`.

```sql
SELECT ST_Z('POINT Z(1 2 3)'::GEOMETRY) AS z, ST_M('POINT ZM(1 2 3 4)'::GEOMETRY) AS m;
-- result:
z	m
3	4
```

#### `ST_M(geom)` {#st_m-function}

Returns the M coordinate of a point, or `NULL` when the geometry does not carry M. See the `ST_Z` example.

#### `ST_XMin(geom)` {#st_xmin-function}

Returns the smallest X of the geometry's extent. The example shows `ST_XMax`, `ST_YMin` and `ST_YMax` too.

```sql
SELECT ST_XMin('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY) AS xmin, ST_XMax('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY) AS xmax, ST_YMin('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY) AS ymin, ST_YMax('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY) AS ymax;
-- result:
xmin	xmax	ymin	ymax
0	4	0	4
```

#### `ST_XMax(geom)` {#st_xmax-function}

Returns the largest X of the geometry's extent. See the `ST_XMin` example.

#### `ST_YMin(geom)` {#st_ymin-function}

Returns the smallest Y of the geometry's extent. See the `ST_XMin` example.

#### `ST_YMax(geom)` {#st_ymax-function}

Returns the largest Y of the geometry's extent. See the `ST_XMin` example.

#### `ST_ZMin(geom)` {#st_zmin-function}

Returns the smallest Z of the geometry's extent.

#### `ST_ZMax(geom)` {#st_zmax-function}

Returns the largest Z of the geometry's extent.

#### `ST_NPoints(geom)` {#st_npoints-function}

Returns the number of vertices in the geometry. Alias: `ST_NumPoints`.

```sql
SELECT ST_NPoints('LINESTRING(0 0,2 2,4 4)'::GEOMETRY) AS npoints;
-- result:
npoints
3
```

#### `ST_NumGeometries(geom)` {#st_numgeometries-function}

Returns the number of geometries in a collection. A single geometry counts as one.

```sql
SELECT ST_NumGeometries('MULTIPOINT(0 0,1 1)'::GEOMETRY) AS n;
-- result:
n
2
```

#### `ST_NumInteriorRings(geom)` {#st_numinteriorrings-function}

Returns the number of interior rings (holes) of a polygon.

```sql
SELECT ST_NumInteriorRings('POLYGON((0 0,10 0,10 10,0 10,0 0),(2 2,4 2,4 4,2 4,2 2))'::GEOMETRY) AS n;
-- result:
n
1
```

#### `ST_ExteriorRing(geom)` {#st_exteriorring-function}

Returns the exterior ring (the shell) of a polygon as a line.

```sql
SELECT ST_AsText(ST_ExteriorRing('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY)) AS geom;
-- result:
geom
LINESTRING (0 0, 4 0, 4 4, 0 4, 0 0)
```

#### `ST_InteriorRingN(geom, n)` {#st_interiorringn-function}

Returns the nth interior ring of a polygon as a line. Rings are numbered from 1.

```sql
SELECT ST_AsText(ST_InteriorRingN('POLYGON((0 0,10 0,10 10,0 10,0 0),(2 2,4 2,4 4,2 4,2 2))'::GEOMETRY, 1)) AS geom;
-- result:
geom
LINESTRING (2 2, 4 2, 4 4, 2 4, 2 2)
```

#### `ST_PointN(geom, index)` {#st_pointn-function}

Returns the nth vertex of a line. Vertices are numbered from 1.

```sql
SELECT ST_AsText(ST_PointN('LINESTRING(0 0,1 1,2 2)'::GEOMETRY, 2)) AS geom;
-- result:
geom
POINT (1 1)
```

#### `ST_StartPoint(geom)` {#st_startpoint-function}

Returns the first vertex of a line. The example also shows `ST_EndPoint`.

```sql
SELECT ST_AsText(ST_StartPoint('LINESTRING(0 0,1 1,2 2)'::GEOMETRY)) AS start, ST_AsText(ST_EndPoint('LINESTRING(0 0,1 1,2 2)'::GEOMETRY)) AS "end";
-- result:
start	end
POINT (0 0)	POINT (2 2)
```

#### `ST_EndPoint(geom)` {#st_endpoint-function}

Returns the last vertex of a line. See the `ST_StartPoint` example.

#### `ST_Dump(geom)` {#st_dump-function}

Expands a collection into a list of its parts, each with the path that locates it. There is no `ST_GeometryN` in SereneDB, so this is how an individual part is reached.

```sql
SELECT g.path AS path, ST_AsText(g.geom) AS geom FROM unnest(ST_Dump('MULTIPOINT(0 0,1 1)'::GEOMETRY)) AS g;
-- result:
path	geom
{1}	POINT (0 0)
{2}	POINT (1 1)
```

#### `ST_CollectionExtract(geom[, type])` {#st_collectionextract-function}

Extracts the elements of one dimension from a collection, as a multi-geometry: `1` for points, `2` for lines, `3` for polygons. Without `type`, the highest dimension present is used.

```sql
SELECT ST_AsText(ST_CollectionExtract('GEOMETRYCOLLECTION(POINT(1 1),LINESTRING(0 0,2 2))'::GEOMETRY, 1)) AS geom;
-- result:
geom
MULTIPOINT (1 1)
```

#### `ST_HasZ(geom)` {#st_hasz-function}

Reports whether the geometry carries Z coordinates. The example shows `ST_HasM` and `ST_ZMFlag` too.

```sql
SELECT ST_HasZ('POINT Z(1 2 3)'::GEOMETRY) AS has_z, ST_HasM('POINT ZM(1 2 3 4)'::GEOMETRY) AS has_m, ST_ZMFlag('POINT Z(1 2 3)'::GEOMETRY) AS zm_flag;
-- result:
has_z	has_m	zm_flag
t	t	2
```

#### `ST_HasM(geom)` {#st_hasm-function}

Reports whether the geometry carries M coordinates. See the `ST_HasZ` example.

#### `ST_ZMFlag(geom)` {#st_zmflag-function}

Returns a code for the coordinate dimensions of the geometry: `0` for XY, `1` for XYM, `2` for XYZ, `3` for XYZM. See the `ST_HasZ` example.

#### `ST_Extent(geom)` {#st_extent-function}

Returns the bounding box of the geometry.

```sql
SELECT ST_Extent('LINESTRING(0 0,2 3)'::GEOMETRY)::text AS extent;
-- result:
extent
BOX(0 0, 2 3)
```

## Measuring Geometries

These functions work in the geometry's own coordinate units. For measurements on the earth, see [Spheroidal Measurements](#spheroidal-measurements).

| Name | Description |
| :--- | :---------- |
| [`ST_Area(geom)`](#st_area-function) | Returns the area of the geometry |
| [`ST_Length(geom)`](#st_length-function) | Returns the length of the geometry |
| [`ST_Perimeter(geom)`](#st_perimeter-function) | Returns the perimeter of the geometry |
| [`ST_Distance(geom1, geom2)`](#st_distance-function) | Returns the shortest distance between two geometries |
| [`ST_Azimuth(origin, target)`](#st_azimuth-function) | Returns the bearing from one point to another, in radians |

#### `ST_Area(geom)` {#st_area-function}

Returns the area of the geometry. Points and lines have zero area.

```sql
SELECT ST_Area('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY) AS area;
-- result:
area
16
```

#### `ST_Length(geom)` {#st_length-function}

Returns the length of the geometry. Points and polygons have zero length; for a polygon's outline use `ST_Perimeter`.

```sql
SELECT ST_Length('LINESTRING(0 0,3 4)'::GEOMETRY) AS length;
-- result:
length
5
```

#### `ST_Perimeter(geom)` {#st_perimeter-function}

Returns the perimeter of the geometry, the total length of its rings.

```sql
SELECT ST_Perimeter('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY) AS perimeter;
-- result:
perimeter
16
```

#### `ST_Distance(geom1, geom2)` {#st_distance-function}

Returns the shortest distance between two geometries. Geometries that intersect are zero apart.

```sql
SELECT ST_Distance('POINT(0 0)'::GEOMETRY, 'POINT(3 4)'::GEOMETRY) AS distance;
-- result:
distance
5
```

#### `ST_Azimuth(origin, target)` {#st_azimuth-function}

Returns the bearing from the point `origin` to the point `target`, in radians clockwise from north.

```sql
SELECT (ST_Azimuth('POINT(0 0)'::GEOMETRY, 'POINT(1 1)'::GEOMETRY) * 1000000)::bigint AS azimuth_micro;
-- result:
azimuth_micro
785398
```

## Testing Relationships

| Name | Description | Aliases |
| :--- | :---------- | :------ |
| [`ST_Intersects(geom1, geom2)`](#st_intersects-function) | Returns true if the geometries share any point | |
| [`ST_Disjoint(geom1, geom2)`](#st_disjoint-function) | Returns true if the geometries share no point | |
| [`ST_Contains(geom1, geom2)`](#st_contains-function) | Returns true if the first geometry contains the second | |
| [`ST_Within(geom1, geom2)`](#st_within-function) | Returns true if the first geometry lies within the second | |
| [`ST_Covers(geom1, geom2)`](#st_covers-function) | Like `ST_Contains`, but a boundary point counts as covered | |
| [`ST_CoveredBy(geom1, geom2)`](#st_coveredby-function) | Like `ST_Within`, but a boundary point counts as covered | |
| [`ST_ContainsProperly(geom1, geom2)`](#st_containsproperly-function) | Returns true if the second geometry is in the first's interior | |
| [`ST_WithinProperly(geom1, geom2)`](#st_withinproperly-function) | Returns true if the first geometry is in the second's interior | |
| [`ST_Crosses(geom1, geom2)`](#st_crosses-function) | Returns true if the geometries cross | |
| [`ST_Overlaps(geom1, geom2)`](#st_overlaps-function) | Returns true if the geometries overlap at their own dimension | |
| [`ST_Touches(geom1, geom2)`](#st_touches-function) | Returns true if the geometries meet only at their boundaries | |
| [`ST_Equals(geom1, geom2)`](#st_equals-function) | Returns true if the geometries cover the same space | |
| [`ST_DWithin(geom1, geom2, distance)`](#st_dwithin-function) | Returns true if the geometries are within a given distance | |
| [`ST_Intersects_Extent(geom1, geom2)`](#st_intersects_extent-function) | Returns true if the geometries bounding boxes intersect | `&&` |
| [`ST_IsValid(geom)`](#st_isvalid-function) | Reports whether the geometry is valid | |
| [`ST_IsEmpty(geom)`](#st_isempty-function) | Reports whether the geometry holds no points | |
| [`ST_IsClosed(geom)`](#st_isclosed-function) | Reports whether a line starts and ends at the same point | |
| [`ST_IsRing(geom)`](#st_isring-function) | Reports whether a line is closed and simple | |
| [`ST_IsSimple(geom)`](#st_issimple-function) | Reports whether a geometry has no self-intersections | |

#### `ST_Intersects(geom1, geom2)` {#st_intersects-function}

Returns true if the geometries share any point.

```sql
SELECT ST_Intersects('POINT(1 1)'::GEOMETRY, 'POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY) AS intersects;
-- result:
intersects
t
```

#### `ST_Disjoint(geom1, geom2)` {#st_disjoint-function}

Returns true if the geometries share no point. The exact inverse of `ST_Intersects`.

```sql
SELECT ST_Disjoint('POINT(9 9)'::GEOMETRY, 'POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY) AS disjoint;
-- result:
disjoint
t
```

#### `ST_Contains(geom1, geom2)` {#st_contains-function}

Returns true if the first geometry contains the second. The example also shows `ST_Within`.

```sql
SELECT ST_Contains('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY, 'POINT(1 1)'::GEOMETRY) AS contains, ST_Within('POINT(1 1)'::GEOMETRY, 'POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY) AS within;
-- result:
contains	within
t	t
```

#### `ST_Within(geom1, geom2)` {#st_within-function}

Returns true if the first geometry lies within the second. It is `ST_Contains` with the arguments swapped. See the `ST_Contains` example.

#### `ST_Covers(geom1, geom2)` {#st_covers-function}

Like `ST_Contains`, except that a point lying on the boundary counts as covered. The example shows the one case where the two disagree: the polygon's own corner.

```sql
SELECT ST_Covers('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY, 'POINT(0 0)'::GEOMETRY) AS covers, ST_Contains('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY, 'POINT(0 0)'::GEOMETRY) AS contains;
-- result:
covers	contains
t	f
```

#### `ST_CoveredBy(geom1, geom2)` {#st_coveredby-function}

Returns true if every point of the first geometry lies in the second, boundary included. It is `ST_Covers` with the arguments swapped.

#### `ST_ContainsProperly(geom1, geom2)` {#st_containsproperly-function}

Returns true if the second geometry lies in the interior of the first, touching neither its boundary nor its exterior.

```sql
SELECT ST_ContainsProperly('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY, 'POINT(1 1)'::GEOMETRY) AS properly;
-- result:
properly
t
```

#### `ST_WithinProperly(geom1, geom2)` {#st_withinproperly-function}

Returns true if the first geometry lies in the interior of the second. It is `ST_ContainsProperly` with the arguments swapped.

#### `ST_Crosses(geom1, geom2)` {#st_crosses-function}

Returns true if the geometries cross, meaning they share some but not all interior points and the shared part has a lower dimension than at least one of them.

```sql
SELECT ST_Crosses('LINESTRING(0 0,4 4)'::GEOMETRY, 'LINESTRING(0 4,4 0)'::GEOMETRY) AS crosses;
-- result:
crosses
t
```

#### `ST_Overlaps(geom1, geom2)` {#st_overlaps-function}

Returns true if the geometries have the same dimension and share some, but not all, of their interiors.

```sql
SELECT ST_Overlaps('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY, 'POLYGON((2 2,6 2,6 6,2 6,2 2))'::GEOMETRY) AS overlaps;
-- result:
overlaps
t
```

#### `ST_Touches(geom1, geom2)` {#st_touches-function}

Returns true if the geometries meet only at their boundaries, with no shared interior.

```sql
SELECT ST_Touches('LINESTRING(0 0,1 1)'::GEOMETRY, 'LINESTRING(1 1,2 2)'::GEOMETRY) AS touches;
-- result:
touches
t
```

#### `ST_Equals(geom1, geom2)` {#st_equals-function}

Returns true if the geometries cover the same space, regardless of vertex order or representation.

```sql
SELECT ST_Equals('LINESTRING(0 0,2 2)'::GEOMETRY, 'LINESTRING(2 2,0 0)'::GEOMETRY) AS equals;
-- result:
equals
t
```

#### `ST_DWithin(geom1, geom2, distance)` {#st_dwithin-function}

Returns true if the geometries are within `distance` of one another.

```sql
SELECT ST_DWithin('POINT(0 0)'::GEOMETRY, 'POINT(3 4)'::GEOMETRY, 5.0) AS within_5;
-- result:
within_5
t
```

#### `ST_Intersects_Extent(geom1, geom2)` {#st_intersects_extent-function}

Returns true if the geometries bounding boxes intersect. Alias: `&&`.

```sql
SELECT ST_Intersects_Extent('POINT(5 5)'::GEOMETRY, 'LINESTRING(0 0, 10 20)'::GEOMETRY) AS intersects;
-- result:
intersects
t
```

#### `ST_IsValid(geom)` {#st_isvalid-function}

Reports whether the geometry is valid. The example also shows `ST_IsEmpty`.

```sql
SELECT ST_IsValid('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY) AS valid, ST_IsEmpty('POLYGON EMPTY'::GEOMETRY) AS empty;
-- result:
valid	empty
t	t
```

#### `ST_IsEmpty(geom)` {#st_isempty-function}

Reports whether the geometry holds no points. See the `ST_IsValid` example.

#### `ST_IsClosed(geom)` {#st_isclosed-function}

Reports whether a line starts and ends at the same point. The example shows `ST_IsRing` and `ST_IsSimple` too.

```sql
SELECT ST_IsClosed('LINESTRING(0 0,1 0,1 1,0 0)'::GEOMETRY) AS closed, ST_IsRing('LINESTRING(0 0,1 0,1 1,0 0)'::GEOMETRY) AS ring, ST_IsSimple('LINESTRING(0 0,1 1,2 2)'::GEOMETRY) AS simple;
-- result:
closed	ring	simple
t	t	t
```

#### `ST_IsRing(geom)` {#st_isring-function}

Reports whether a line is closed and simple. See the `ST_IsClosed` example.

#### `ST_IsSimple(geom)` {#st_issimple-function}

Reports whether a geometry has no self-intersections. See the `ST_IsClosed` example.

## Deriving New Geometries

| Name | Description |
| :--- | :---------- |
| [`ST_Intersection(geom1, geom2)`](#st_intersection-function) | Returns the part shared by both geometries |
| [`ST_Union(geom1, geom2)`](#st_union-function) | Returns the combination of both geometries |
| [`ST_Difference(geom1, geom2)`](#st_difference-function) | Returns the part of the first geometry not in the second |
| [`ST_SymDifference(geom1, geom2)`](#st_symdifference-function) | Returns the parts belonging to exactly one of the geometries |
| [`ST_Buffer(geom, distance[, num_triangles])`](#st_buffer-function) | Returns the area within a given distance of the geometry |
| [`ST_ConvexHull(geom)`](#st_convexhull-function) | Returns the smallest convex geometry enclosing the input |
| [`ST_Simplify(geom, tolerance)`](#st_simplify-function) | Removes vertices that fall within a tolerance |
| [`ST_Centroid(geom)`](#st_centroid-function) | Returns the centre of mass of the geometry |
| [`ST_Envelope(geom)`](#st_envelope-function) | Returns the bounding box as a polygon |
| [`ST_Boundary(geom)`](#st_boundary-function) | Returns the boundary of the geometry |
| [`ST_PointOnSurface(geom)`](#st_pointonsurface-function) | Returns a point guaranteed to lie on the geometry |
| [`ST_ClosestPoint(geom1, geom2)`](#st_closestpoint-function) | Returns the point of the first geometry closest to the second |
| [`ST_ShortestLine(geom1, geom2)`](#st_shortestline-function) | Returns the shortest line between two geometries |

#### `ST_Intersection(geom1, geom2)` {#st_intersection-function}

Returns the part shared by both geometries.

```sql
SELECT ST_AsText(ST_Intersection('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY, 'POLYGON((2 2,6 2,6 6,2 6,2 2))'::GEOMETRY)) AS geom;
-- result:
geom
POLYGON ((2 4, 4 4, 4 2, 2 2, 2 4))
```

#### `ST_Union(geom1, geom2)` {#st_union-function}

Returns the combination of both geometries. Both arguments must have the same dimension, because a mixed result would need a `GEOMETRYCOLLECTION`.

```sql
SELECT ST_AsText(ST_Union('POINT(0 0)'::GEOMETRY, 'POINT(1 1)'::GEOMETRY)) AS geom;
-- result:
geom
MULTIPOINT (0 0, 1 1)
```

#### `ST_Difference(geom1, geom2)` {#st_difference-function}

Returns the part of the first geometry that is not in the second.

```sql
SELECT ST_AsText(ST_Difference('LINESTRING(0 0,4 0)'::GEOMETRY, 'LINESTRING(1 0,2 0)'::GEOMETRY)) AS geom;
-- result:
geom
MULTILINESTRING ((0 0, 1 0), (2 0, 4 0))
```

#### `ST_SymDifference(geom1, geom2)` {#st_symdifference-function}

Returns the parts that belong to exactly one of the geometries. Like `ST_Union`, both arguments must have the same dimension.

```sql
SELECT ST_AsText(ST_SymDifference('LINESTRING(0 0,2 0)'::GEOMETRY, 'LINESTRING(1 0,3 0)'::GEOMETRY)) AS geom;
-- result:
geom
MULTILINESTRING ((0 0, 1 0), (2 0, 3 0))
```

#### `ST_Buffer(geom, distance[, num_triangles])` {#st_buffer-function}

Returns the area within `distance` of the geometry. The optional `num_triangles` sets the number of triangles used per quarter circle, which controls how round the result is.

```sql
SELECT ST_NPoints(ST_Buffer('POINT(0 0)'::GEOMETRY, 1, 2)) AS npoints;
-- result:
npoints
9
```

#### `ST_ConvexHull(geom)` {#st_convexhull-function}

Returns the smallest convex geometry that encloses the input.

```sql
SELECT ST_AsText(ST_ConvexHull('MULTIPOINT(0 0,2 0,2 2,0 2,1 1)'::GEOMETRY)) AS geom;
-- result:
geom
POLYGON ((0 0, 0 2, 2 2, 2 0, 0 0))
```

#### `ST_Simplify(geom, tolerance)` {#st_simplify-function}

Removes vertices that fall within `tolerance`, using the Douglas-Peucker algorithm. The result may be invalid or may break topology shared with neighbouring geometries; there is no `ST_SimplifyPreserveTopology`.

```sql
SELECT ST_AsText(ST_Simplify('LINESTRING(0 0,1 0.1,2 0)'::GEOMETRY, 0.5)) AS geom;
-- result:
geom
LINESTRING (0 0, 2 0)
```

#### `ST_Centroid(geom)` {#st_centroid-function}

Returns the centre of mass of the geometry, which is not necessarily on the geometry itself. For a point that is, use `ST_PointOnSurface`.

```sql
SELECT ST_AsText(ST_Centroid('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY)) AS geom;
-- result:
geom
POINT (2 2)
```

#### `ST_Envelope(geom)` {#st_envelope-function}

Returns the bounding box of the geometry as a polygon. `ST_Extent` returns the same bounds as a box value instead.

```sql
SELECT ST_AsText(ST_Envelope('LINESTRING(0 0,2 3)'::GEOMETRY)) AS geom;
-- result:
geom
POLYGON ((0 0, 0 3, 2 3, 2 0, 0 0))
```

#### `ST_Boundary(geom)` {#st_boundary-function}

Returns the boundary of the geometry: the rings of a polygon, the endpoints of a line.

```sql
SELECT ST_AsText(ST_Boundary('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY)) AS geom;
-- result:
geom
LINESTRING (0 0, 0 4, 4 4, 4 0, 0 0)
```

#### `ST_PointOnSurface(geom)` {#st_pointonsurface-function}

Returns a point guaranteed to lie on the geometry, the same point PostGIS returns: for polygons, the middle of the widest stretch of a horizontal line across them; for lines, the vertex nearest their centroid, preferring vertices other than endpoints; for points, the point nearest their centroid.

```sql
SELECT ST_AsText(ST_PointOnSurface('POLYGON((0 0,4 0,4 4,0 4,0 0))'::GEOMETRY)) AS geom;
-- result:
geom
POINT (2 2)
```

#### `ST_ClosestPoint(geom1, geom2)` {#st_closestpoint-function}

Returns the point of the first geometry that lies closest to the second.

```sql
SELECT ST_AsText(ST_ClosestPoint('LINESTRING(0 0,4 0)'::GEOMETRY, 'POINT(2 2)'::GEOMETRY)) AS geom;
-- result:
geom
POINT (2 0)
```

#### `ST_ShortestLine(geom1, geom2)` {#st_shortestline-function}

Returns the shortest line between two geometries.

```sql
SELECT ST_AsText(ST_ShortestLine('LINESTRING(0 0,4 0)'::GEOMETRY, 'POINT(2 2)'::GEOMETRY)) AS geom;
-- result:
geom
LINESTRING (2 0, 2 2)
```

## Editing Geometries

| Name | Description | Aliases |
| :--- | :---------- | :------ |
| [`ST_Affine(geom, a, b, d, e, xoff, yoff)`](#st_affine-function) | Applies a two dimensional affine transformation to every vertex | |
| [`ST_Affine(geom, a, b, c, d, e, f, g, h, i, xoff, yoff, zoff)`](#st_affine-3d-function) | Applies a three dimensional affine transformation to every vertex | |
| [`ST_Translate(geom, dx, dy[, dz])`](#st_translate-function) | Moves the geometry by an offset | |
| [`ST_Scale(geom, xs, ys[, zs])`](#st_scale-function) | Scales the geometry by a factor per axis | |
| [`ST_TransScale(geom, dx, dy, xs, ys)`](#st_transscale-function) | Moves and then scales the geometry | |
| [`ST_RotateZ(geom, radians)`](#st_rotatez-function) | Rotates the geometry around the Z axis | `ST_Rotate` |
| [`ST_RotateX(geom, radians)`](#st_rotatex-function) | Rotates the geometry around the X axis | |
| [`ST_RotateY(geom, radians)`](#st_rotatey-function) | Rotates the geometry around the Y axis | |
| [`ST_Expand(geom, distance)`](#st_expand-function) | Returns the bounding box grown by a distance | |
| [`ST_Reverse(geom)`](#st_reverse-function) | Reverses the vertex order | |
| [`ST_Normalize(geom)`](#st_normalize-function) | Rewrites the geometry into a canonical form | |
| [`ST_FlipCoordinates(geom)`](#st_flipcoordinates-function) | Swaps the X and Y of every vertex | |
| [`ST_Force2D(geom)`](#st_force2d-function) | Drops the Z and M dimensions | |
| [`ST_RemoveRepeatedPoints(geom)`](#st_removerepeatedpoints-function) | Removes consecutive duplicate vertices | |

#### `ST_Affine(geom, a, b, d, e, xoff, yoff)` {#st_affine-function}

Applies an affine transformation to every vertex, mapping it to `(a*x + b*y + xoff, d*x + e*y + yoff)`.

```sql
SELECT ST_AsText(ST_Affine('POINT(1 1)'::GEOMETRY, 2, 0, 0, 2, 1, 1)) AS geom;
-- result:
geom
POINT (3 3)
```

#### `ST_Affine(geom, a, b, c, d, e, f, g, h, i, xoff, yoff, zoff)` {#st_affine-3d-function}

Applies an affine transformation in three dimensions, mapping every vertex to `(a*x + b*y + c*z + xoff, d*x + e*y + f*z + yoff, g*x + h*y + i*z + zoff)`.

#### `ST_Translate(geom, dx, dy[, dz])` {#st_translate-function}

Moves every vertex by `dx` along X, `dy` along Y and, when given, `dz` along Z. Without `dz` the Z coordinates are left as they are.

```sql
SELECT ST_AsText(ST_Translate('LINESTRING(0 0,1 1)'::GEOMETRY, 5, -2)) AS geom;
-- result:
geom
LINESTRING (5 -2, 6 -1)
```

#### `ST_Scale(geom, xs, ys[, zs])` {#st_scale-function}

Multiplies the coordinates of every vertex by `xs`, `ys` and, when given, `zs`.

```sql
SELECT ST_AsText(ST_Scale('POINT(1 1)'::GEOMETRY, 2, 3)) AS xy, ST_AsText(ST_Scale('POINT Z(1 2 3)'::GEOMETRY, 2, 2, 2)) AS xyz;
-- result:
xy	xyz
POINT (2 3)	POINT Z (2 4 6)
```

#### `ST_TransScale(geom, dx, dy, xs, ys)` {#st_transscale-function}

Moves every vertex by `dx` and `dy`, then scales it by `xs` and `ys`.

```sql
SELECT ST_AsText(ST_TransScale('POINT(1 1)'::GEOMETRY, 1, 2, 2, 3)) AS geom;
-- result:
geom
POINT (4 9)
```

#### `ST_RotateZ(geom, radians)` {#st_rotatez-function}

Rotates the geometry counterclockwise around the Z axis, which is the plain rotation of a two dimensional geometry about the origin. Alias: `ST_Rotate`.

```sql
WITH r AS (SELECT ST_Rotate('POINT(1 0)'::GEOMETRY, pi() / 2) AS g) SELECT round(ST_X(g), 9) AS x, round(ST_Y(g), 9) AS y FROM r;
-- result:
x	y
0	1
```

#### `ST_RotateX(geom, radians)` {#st_rotatex-function}

Rotates the geometry around the X axis. The example shows all three axes.

```sql
WITH r AS (SELECT ST_RotateX('POINT Z(0 1 0)'::GEOMETRY, pi() / 2) AS gx, ST_RotateY('POINT Z(1 0 0)'::GEOMETRY, pi() / 2) AS gy, ST_RotateZ('POINT Z(1 0 0)'::GEOMETRY, pi() / 2) AS gz) SELECT round(ST_Z(gx), 9) AS x_axis_z, round(ST_Z(gy), 9) AS y_axis_z, round(ST_Y(gz), 9) AS z_axis_y FROM r;
-- result:
x_axis_z	y_axis_z	z_axis_y
1	-1	1
```

#### `ST_RotateY(geom, radians)` {#st_rotatey-function}

Rotates the geometry around the Y axis. See the `ST_RotateX` example.

#### `ST_Expand(geom, distance)` {#st_expand-function}

Returns the bounding box of the geometry grown by `distance` in every direction.

```sql
SELECT ST_AsText(ST_Expand('POINT(1 1)'::GEOMETRY, 1)) AS geom;
-- result:
geom
POLYGON ((0 0, 0 2, 2 2, 2 0, 0 0))
```

#### `ST_Reverse(geom)` {#st_reverse-function}

Reverses the vertex order of the geometry.

```sql
SELECT ST_AsText(ST_Reverse('LINESTRING(0 0,1 1,2 2)'::GEOMETRY)) AS geom;
-- result:
geom
LINESTRING (2 2, 1 1, 0 0)
```

#### `ST_Normalize(geom)` {#st_normalize-function}

Rewrites the geometry into the canonical form PostGIS uses, so that geometries differing only in where their rings start, in their direction or in the order of their parts become identical: every ring starts at its smallest point (by X, then Y), shells and closed lines run clockwise and holes counter-clockwise, an open line starts at its smaller end, and holes and the parts of a multi-geometry are sorted in descending order.

```sql
SELECT ST_AsText(ST_Normalize('LINESTRING(0 0,1 1)'::GEOMETRY)) AS geom;
-- result:
geom
LINESTRING (0 0, 1 1)
```

#### `ST_FlipCoordinates(geom)` {#st_flipcoordinates-function}

Swaps the X and Y of every vertex. Useful for data stored in latitude/longitude order.

```sql
SELECT ST_AsText(ST_FlipCoordinates('POINT(1 2)'::GEOMETRY)) AS geom;
-- result:
geom
POINT (2 1)
```

#### `ST_Force2D(geom)` {#st_force2d-function}

Drops the Z and M dimensions from the geometry.

```sql
SELECT ST_AsText(ST_Force2D('POINT Z(1 2 3)'::GEOMETRY)) AS geom;
-- result:
geom
POINT (1 2)
```

#### `ST_RemoveRepeatedPoints(geom)` {#st_removerepeatedpoints-function}

Removes consecutive duplicate vertices.

```sql
SELECT ST_AsText(ST_RemoveRepeatedPoints('LINESTRING(0 0,0 0,1 1)'::GEOMETRY)) AS geom;
-- result:
geom
LINESTRING (0 0, 1 1)
```

## Linear Referencing

| Name | Description |
| :--- | :---------- |
| [`ST_LineInterpolatePoint(line, fraction)`](#st_lineinterpolatepoint-function) | Returns the point at a fraction along a line |
| [`ST_LineInterpolatePoints(line, fraction, repeat)`](#st_lineinterpolatepoints-function) | Returns the points at a repeating fraction along a line |
| [`ST_LineSubstring(line, start_fraction, end_fraction)`](#st_linesubstring-function) | Returns the part of a line between two fractions |
| [`ST_LineLocatePoint(line, point)`](#st_linelocatepoint-function) | Returns the fraction along a line closest to a point |
| [`ST_LocateAlong(line, measure[, offset])`](#st_locatealong-function) | Returns the positions on a measured line at a measure |
| [`ST_LocateBetween(line, start_measure, end_measure[, offset])`](#st_locatebetween-function) | Returns the part of a measured line between two measures |
| [`ST_InterpolatePoint(line, point)`](#st_interpolatepoint-function) | Returns the measure of a line at the position closest to a point |

#### `ST_LineInterpolatePoint(line, fraction)` {#st_lineinterpolatepoint-function}

Returns the point at `fraction` along a line, where the fraction runs from `0` at the start to `1` at the end.

```sql
SELECT ST_AsText(ST_LineInterpolatePoint('LINESTRING(0 0,4 0)'::GEOMETRY, 0.25)) AS geom;
-- result:
geom
POINT (1 0)
```

#### `ST_LineInterpolatePoints(line, fraction, repeat)` {#st_lineinterpolatepoints-function}

Returns the point at `fraction` along a line and, when `repeat` is true, another point at every further multiple of `fraction`, as a `MULTIPOINT`.

#### `ST_LineSubstring(line, start_fraction, end_fraction)` {#st_linesubstring-function}

Returns the part of a line between two fractions of its length.

```sql
SELECT ST_AsText(ST_LineSubstring('LINESTRING(0 0,4 0)'::GEOMETRY, 0.25, 0.75)) AS geom;
-- result:
geom
LINESTRING (1 0, 3 0)
```

#### `ST_LineLocatePoint(line, point)` {#st_linelocatepoint-function}

Returns the fraction along a line at which it passes closest to the given point.

```sql
SELECT (ST_LineLocatePoint('LINESTRING(0 0,4 0)'::GEOMETRY, 'POINT(1 0)'::GEOMETRY) * 100)::bigint AS pct;
-- result:
pct
25
```

#### `ST_LocateAlong(line, measure[, offset])` {#st_locatealong-function}

Returns the positions on a line carrying M values where the measure equals `measure`. A positive `offset` moves the result that far to the right of the line's direction, a negative one to the left.

```sql
SELECT ST_AsText(ST_LocateAlong('LINESTRING M(0 0 0,4 0 4)'::GEOMETRY, 2)) AS geom;
-- result:
geom
POINT M (2 0 2)
```

#### `ST_LocateBetween(line, start_measure, end_measure[, offset])` {#st_locatebetween-function}

Returns the part of a line carrying M values that falls between two measures. `offset` works as in `ST_LocateAlong`.

```sql
SELECT ST_AsText(ST_LocateBetween('LINESTRING M(0 0 0,4 0 4)'::GEOMETRY, 1, 3)) AS geom;
-- result:
geom
LINESTRING M (1 0 1, 3 0 3)
```

#### `ST_InterpolatePoint(line, point)` {#st_interpolatepoint-function}

Returns the M value of a line at the position closest to `point`. It is the inverse of `ST_LocateAlong`.

## Coordinate Reference Systems

SereneDB attaches the coordinate reference system to the `GEOMETRY` type itself rather than storing an SRID number alongside each value, so `ST_SRID` and `ST_SetSRID` do not exist. `ST_CRS` and `ST_SetCRS` take their place, and identifiers are strings such as `OGC:CRS84`.

A CRS is a label that SereneDB tracks and checks. It does not reproject: there is no `ST_Transform`, because reprojection needs a database of coordinate-system definitions that SereneDB does not ship. Convert coordinates before loading them, and use `ST_SetCRS` to record which system the result is in. Measuring on the WGS84 ellipsoid needs no such database and is supported, see [Spheroidal Measurements](#spheroidal-measurements).

| Name | Description |
| :--- | :---------- |
| [`ST_CRS(geom)`](#st_crs-function) | Returns the CRS identifier of the geometry |
| [`ST_SetCRS(geom, crs)`](#st_setcrs-function) | Sets the CRS identifier of the geometry |

#### `ST_CRS(geom)` {#st_crs-function}

Returns the Coordinate Reference System (CRS) identifier of the geometry.

```sql
SELECT ST_CRS('POINT(1 2)'::GEOMETRY('OGC:CRS84')) AS crs;
-- result:
crs
OGC:CRS84
```

#### `ST_SetCRS(geom, crs)` {#st_setcrs-function}

Sets the Coordinate Reference System (CRS) identifier of the geometry. The coordinates are left as they are; only the label changes.

```sql
SELECT typeof(ST_SetCRS('POINT(1 2)'::GEOMETRY, 'OGC:CRS84')) AS type;
-- result:
type
GEOMETRY('OGC:CRS84')
```

## Spheroidal Measurements

These functions measure on the earth rather than in the coordinate plane and return metres. They take **X as the latitude and Y as the longitude**, which is the opposite of the order used by the planar functions on this page.

`ST_Distance_Sphere` treats the earth as a sphere, which is fast and approximate. The `*_Spheroid` functions use the WGS84 ellipsoid, which is slower and accurate.

| Name | Description |
| :--- | :---------- |
| [`ST_Distance_Sphere(geom1, geom2)`](#st_distance_sphere-function) | Returns the great-circle distance between two points |
| [`ST_Length_Spheroid(geom)`](#st_length_spheroid-function) | Returns the length of a line on the WGS84 spheroid |
| [`ST_Area_Spheroid(geom)`](#st_area_spheroid-function) | Returns the area of a polygon on the WGS84 spheroid |
| [`ST_Perimeter_Spheroid(geom)`](#st_perimeter_spheroid-function) | Returns the perimeter of a polygon on the WGS84 spheroid |

#### `ST_Distance_Sphere(geom1, geom2)` {#st_distance_sphere-function}

Returns the great-circle distance between two points in metres, treating the earth as a sphere. The example measures one degree along the equator.

```sql
SELECT ST_Distance_Sphere('POINT(0 0)'::GEOMETRY, 'POINT(1 0)'::GEOMETRY)::bigint AS meters;
-- result:
meters
111195
```

#### `ST_Length_Spheroid(geom)` {#st_length_spheroid-function}

Returns the length of a line in metres on the WGS84 spheroid. The example spans one degree of latitude, which is why the result is close to 110.6 km rather than the 111.3 km of a degree of longitude at the equator.

```sql
SELECT ST_Length_Spheroid('LINESTRING(0 0,1 0)'::GEOMETRY)::bigint AS meters;
-- result:
meters
110574
```

#### `ST_Area_Spheroid(geom)` {#st_area_spheroid-function}

Returns the area of a polygon in square metres on the WGS84 spheroid.

```sql
SELECT ST_Area_Spheroid('POLYGON((0 0,1 0,1 1,0 1,0 0))'::GEOMETRY)::bigint AS sq_meters;
-- result:
sq_meters
12308778361
```

#### `ST_Perimeter_Spheroid(geom)` {#st_perimeter_spheroid-function}

Returns the perimeter of a polygon in metres on the WGS84 spheroid.

```sql
SELECT ST_Perimeter_Spheroid('POLYGON((0 0,1 0,1 1,0 1,0 0))'::GEOMETRY)::bigint AS meters;
-- result:
meters
443771
```

## Spatial Ordering and Tiling

| Name | Description |
| :--- | :---------- |
| [`ST_Hilbert(geom[, bounds])`](#st_hilbert-function) | Returns the Hilbert curve index of the geometry's centre |
| [`ST_Hilbert(x, y, bounds)`](#st_hilbert-xy-function) | Returns the Hilbert curve index of a coordinate pair |
| [`ST_QuadKey(point, level)`](#st_quadkey-function) | Returns the Bing Maps quadkey for a point at a zoom level |
| [`ST_QuadKey(longitude, latitude, level)`](#st_quadkey-lonlat-function) | Returns the Bing Maps quadkey for a longitude and latitude |
| [`ST_TileEnvelope(tile_zoom, tile_x, tile_y)`](#st_tileenvelope-function) | Returns the Web Mercator extent of an XYZ tile |

#### `ST_Hilbert(geom[, bounds])` {#st_hilbert-function}

Returns the Hilbert curve index of the geometry's centre, which sorts nearby geometries close together. The optional `bounds` is the box, such as one from `ST_Extent`, that the curve covers.

```sql
SELECT ST_Hilbert('POINT(1 2)'::GEOMETRY) AS hilbert;
-- result:
hilbert
3355443200
```

#### `ST_Hilbert(x, y, bounds)` {#st_hilbert-xy-function}

Returns the Hilbert curve index of the coordinate pair `x`, `y` within the box `bounds`.

#### `ST_QuadKey(point, level)` {#st_quadkey-function}

Returns the Bing Maps quadkey for a point at zoom level `level`.

```sql
SELECT ST_QuadKey('POINT(11 22)'::GEOMETRY, 5) AS quadkey;
-- result:
quadkey
12202
```

#### `ST_QuadKey(longitude, latitude, level)` {#st_quadkey-lonlat-function}

Returns the Bing Maps quadkey for a longitude and latitude at zoom level `level`.

#### `ST_TileEnvelope(tile_zoom, tile_x, tile_y)` {#st_tileenvelope-function}

Returns the extent of an XYZ tile as a polygon in Web Mercator coordinates.

```sql
SELECT ST_Area(ST_TileEnvelope(1, 0, 0))::bigint AS area;
-- result:
area
401501740587349
```

## Differences from PostGIS

### How geometries are displayed

A `GEOMETRY` sent to a client is rendered as upper-case hexadecimal WKB, byte for byte what PostGIS sends:

```sql
SELECT 'POINT(1 2)'::GEOMETRY;
-- 0101000000000000000000F03F0000000000000040
```

Wrap the value in `ST_AsText` for the readable spelling, as the examples on this page do.

The hex agrees with PostGIS for two-dimensional geometries. Geometries carrying `Z` or `M` do not: SereneDB writes the ISO WKB type codes (`POINT Z` is `01E9030000...`) where PostGIS sets the EWKB high-bit flags (`0101000080...`).

### Identifying the coordinate reference system

The CRS belongs to the type, not to the value, so there is no SRID integer. Use `ST_CRS` and `ST_SetCRS` with string identifiers in place of `ST_SRID` and `ST_SetSRID`.

### PostGIS functions that are not available

Geometry operations run on [Boost.Geometry](https://www.boost.org/doc/libs/release/libs/geometry/). The following PostGIS functions have no equivalent there and are therefore not provided. Calling one reports that the function does not exist.

| Not available | Closest thing that is |
| :------------ | :-------------------- |
| `ST_MakeValid` | `ST_IsValid` reports the problem, but nothing repairs it |
| `ST_Node`, `ST_Polygonize`, `ST_BuildArea` | -- |
| `ST_LineMerge` | -- |
| `ST_SimplifyPreserveTopology` | `ST_Simplify`, which may break topology |
| `ST_ConcaveHull` | `ST_ConvexHull` |
| `ST_ReducePrecision` | -- |
| `ST_MaximumInscribedCircle` | `ST_PointOnSurface` for a point known to be inside |
| `ST_VoronoiDiagram` | -- |
| `ST_MinimumRotatedRectangle` | `ST_Envelope`, which is axis-aligned |
| `ST_GeometryN` | `ST_Dump`, which expands every part at once |
| `ST_SRID`, `ST_SetSRID` | `ST_CRS` and `ST_SetCRS`, which use string identifiers |
| `ST_Relate` | the individual predicates |
| `ST_Segmentize`, `ST_Split`, `ST_Snap`, `ST_OffsetCurve` | -- |
| `ST_GeoHash` | `ST_QuadKey`, `ST_Hilbert` |

Five further differences apply to functions that do exist:

-   **`ST_Union` and `ST_SymDifference` require both arguments to have the same dimension.** Combining a point with a polygon would produce a `GEOMETRYCOLLECTION`, which cannot be built. `ST_Intersection` and `ST_Difference` accept mixed dimensions.
-   **The overlay functions refuse a polygon that `ST_IsValid` rejects.** `ST_Intersection`, `ST_Union`, `ST_Difference`, `ST_SymDifference` and the union and intersection aggregates raise an error for a self-intersecting ring, a hole outside its shell or overlapping parts of a multipolygon, because Boost.Geometry's answer for such input cannot be trusted. PostGIS raises a GEOS topology error for most of these too, but answers some: when the two bounding boxes do not meet, or when a ring only touches itself at a point. There is no `ST_MakeValid` to repair the input first.
-   **The Boost-backed operations drop `Z` and `M` from their results.** Measurement and predicates are computed in two dimensions, as they are in PostGIS, but PostGIS carries the extra dimensions through to the result and these do not: `ST_Envelope`, `ST_Boundary`, `ST_ConvexHull`, `ST_Simplify`, `ST_Intersection`, `ST_PointOnSurface`, `ST_Normalize` and `ST_RemoveRepeatedPoints`. The functions that move vertices around rather than computing new ones keep every dimension: `ST_Reverse`, `ST_Multi`, `ST_Points`, `ST_StartPoint`, `ST_EndPoint` and `ST_PointN`, and so does `ST_Centroid`.
-   **Only some functions accept a `GEOMETRYCOLLECTION`.** Those that can answer member by member do: `ST_Reverse`, `ST_Centroid`, `ST_Envelope`, `ST_ConvexHull`, `ST_Area`, `ST_Length`, `ST_NumGeometries`, `ST_IsValid`, `ST_IsEmpty`, and the `ST_Intersects` / `ST_Disjoint` predicates. `ST_Boundary` returns `NULL` for one. Everything else rejects it, because a collection's answer is not the combination of its parts' answers -- the other predicates, `ST_Buffer` and `ST_Simplify` among them.
-   **An empty geometry is valid, and empty input yields `NULL` where a geometry is expected.** `ST_IsValid('LINESTRING EMPTY')` is true, and `ST_ClosestPoint` and `ST_ShortestLine` return `NULL` when either argument is empty rather than raising.


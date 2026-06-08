# Vertex Notation System for Goldberg Polyhedron GP(2,2)

This specification defines a unique, unambiguous, and mobile-friendly text notation for referencing all 240 vertices of the Class II (mirror-symmetric, non-skewed) Goldberg polyhedron $GP(2,2)$.

## 1. Global Patch Identification (The Prefix)

The 240 vertices are divided into 12 identical local patches centered around the 12 pentagons of the polyhedron. Each patch is identified by a prefix based on its global position:

- **`N`**: The North Pole patch.
- **`N1` to `N5`**: The 5 Northern hemisphere patches, ordered counter-clockwise (CCW) when viewed from above the North Pole.
- **`S1` to `S5`**: The 5 Southern hemisphere patches, ordered CCW when viewed from above the North Pole. Due to the icosahedral antipodal stagger ($36^\circ$ twist), the meridian of `N1` lines up with the boundary interface between `S1` and `S2`.
- **`S`**: The South Pole patch.

### Patch Adjacency Examples

To illustrate how the northern and southern hemispheres lock together across the equatorial seam:

- **`N1`** is surrounded by: `N`, `N2`, `N5`, `S1`, `S2`.
- **`S1`** is surrounded by: `S`, `S2`, `S5`, `N1`, `N5`.

Note that due to the $36^\circ$ antipodal stagger, each northern hemisphere patch borders **two** southern hemisphere patches and vice versa. The `N1`/`S1`+`S2` boundary alignment means `N1` sits across the equator from the seam between `S1` and `S2`.

## 2. Local Patch Coordinate System (Ring and Index)

Every patch contains exactly 20 vertices structured into 3 concentric rings expanding outward from its central pentagon. The formal syntax is `[Patch]-[Ring][Index]` (e.g., `N-A1`, `N1-B3`, `N2-C10`).

### Winding Order & Orientation (The "12 o'clock" Rule)

All indices increment in a **counter-clockwise (CCW)** direction when viewing the patch straight-on from the outside of the polyhedron. Index `1` for every ring is anchored by drawing a geodesic line (a straight path over the edges) toward a specific neighboring pole:

- **For `N`**: Index `1` points directly toward the boundary between patches `N1` and `N5`.
- **For `N1` to `N5`**: Index `1` points directly toward patch `N`.
- **For `S1` to `S5`**: Index `1` points directly toward patch `S`.
- **For `S`**: Index `1` points directly toward the boundary between patches `S1` and `S5`.

### Ring Structures within a Patch

- **A-Ring (`A1` to `A5`)**: The 5 vertices forming the central pentagon. Index `A1` points toward the anchor pole.
- **B-Ring (`B1` to `B5`)**: The 5 vertices immediately adjacent to the A-Ring. Vertex `B[i]` connects directly to `A[i]` via an outward edge.
- **C-Ring (`C1` to `C10`)**: The 10 outermost boundary vertices of the patch. Because the vertex graph branches moving outward:
  - `B1` connects outward to `C1` and `C2` (where `C1` is the more clockwise vertex, and `C2` is more CCW).
  - `B2` connects outward to `C3` and `C4`.
  - `B3` connects outward to `C5` and `C6`.
  - `B4` connects outward to `C7` and `C8`.
  - `B5` connects outward to `C9` and `C10`.

## 3. Unambiguous Resolution (The Ownership Rule)

Because the polyhedron is a closed surface, adjacent patches share boundary vertices in their C-Rings. To guarantee every physical vertex has exactly **one unique name**, a strict patch hierarchy is enforced:

$$\text{N} > \text{N1} > \text{N2} > \text{N3} > \text{N4} > \text{N5} > \text{S1} > \text{S2} > \text{S3} > \text{S4} > \text{S5} > \text{S}$$

If a physical vertex is shared between multiple patches, it **must strictly be named using the patch highest in this hierarchy**. This applies universally — whether the sharing occurs between a pole and a hemisphere patch, between two northern hemisphere patches, between a northern and a southern hemisphere patch, or between two southern hemisphere patches.

### Examples of Duplicity Resolution:

- A vertex shared between the North Pole (`N`) and a northern hemisphere patch (`N1`) must use the `N-` prefix.
- A vertex sitting exactly on the seam between `N1` and `N5` must use the `N1-` prefix.
- A vertex sitting exactly on the seam between `N2` and `N3` must use the `N2-` prefix.
- A vertex shared between a northern hemisphere patch (`N5`) and a southern hemisphere patch (`S1`) must use the `N5-` prefix.

## 4. Total Vertex Accounting

- **12 Patches $\times$ 5 A-vertices** = 60 vertices (Exclusive to each patch)
- **12 Patches $\times$ 5 B-vertices** = 60 vertices (Exclusive to each patch)
- **12 Patches $\times$ 10 C-vertices** = 120 unique vertices (After eliminating duplicates via the Ownership Rule)
- **Total unique vertices accounted for** = 240 vertices.

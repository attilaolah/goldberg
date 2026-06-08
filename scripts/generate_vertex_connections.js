const fs = require("node:fs");
const path = require("node:path");

const BABYLON = require("babylonjs");

const OUTPUT_PATH = path.join(__dirname, "..", "data", "gp_2_2_vertex_connections.json");
const PATCH_HIERARCHY = ["N", "N1", "N2", "N3", "N4", "N5", "S1", "S2", "S3", "S4", "S5", "S"];

function main() {
  BABYLON.Logger.LogLevels = BABYLON.Logger.NoneLogLevel;

  const originalLog = console.log;
  console.log = () => {};
  const engine = new BABYLON.NullEngine();
  console.log = originalLog;

  const scene = new BABYLON.Scene(engine);
  const goldberg = BABYLON.MeshBuilder.CreateGoldberg(
    "gp_2_2",
    {
      m: 2,
      n: 2,
      size: 4.5,
    },
    scene,
  );

  const graph = buildGraph(goldberg);
  const faceData = buildFaceData(goldberg, graph);
  const patches = mapPatches(faceData, graph);
  const labelByVertex = buildVertexLabels(patches, graph);
  const vertexByLabel = invertMap(labelByVertex);
  const labelOrder = buildLabelOrder();
  const labelRank = new Map(labelOrder.map((label, index) => [label, index]));

  validateGraph(graph, labelByVertex, vertexByLabel);

  const vertices = {};
  for (const label of labelOrder) {
    const vertexIndex = vertexByLabel.get(label);
    if (vertexIndex === undefined) {
      continue;
    }
    vertices[label] = {
      neighbours: [...graph.adjacency[vertexIndex]].map((neighbour) => labelByVertex.get(neighbour)).sort((left, right) => labelRank.get(left) - labelRank.get(right)),
    };
  }

  const output = {
    name: "Goldberg GP(2,2) vertex connections",
    notation: "[Patch][Ring][Index], for example NA1 or S3C5",
    vertex_count: Object.keys(vertices).length,
    neighbour_count_per_vertex: 3,
    vertices,
  };

  fs.mkdirSync(path.dirname(OUTPUT_PATH), { recursive: true });
  fs.writeFileSync(OUTPUT_PATH, `${JSON.stringify(output, null, 2)}\n`);
}

function buildGraph(mesh) {
  const positionData = mesh.getVerticesData(BABYLON.VertexBuffer.PositionKind);
  const indices = mesh.getIndices();
  const keyToIndex = new Map();
  const remapped = new Array(positionData.length / 3);
  const positions = [];
  const adjacency = [];

  function getOrCreateVertex(x, y, z) {
    const key = `${x.toFixed(6)},${y.toFixed(6)},${z.toFixed(6)}`;
    if (keyToIndex.has(key)) {
      return keyToIndex.get(key);
    }
    const index = positions.length;
    positions.push(new BABYLON.Vector3(x, y, z));
    adjacency.push(new Set());
    keyToIndex.set(key, index);
    return index;
  }

  for (let i = 0; i < positionData.length; i += 3) {
    remapped[i / 3] = getOrCreateVertex(positionData[i], positionData[i + 1], positionData[i + 2]);
  }

  const triangles = [];
  for (let i = 0; i < indices.length; i += 3) {
    const a = remapped[indices[i]];
    const b = remapped[indices[i + 1]];
    const c = remapped[indices[i + 2]];
    triangles.push([a, b, c]);
    link(adjacency, a, b);
    link(adjacency, b, c);
    link(adjacency, c, a);
  }

  return { adjacency, positions, triangles };
}

function buildFaceData(goldberg, graph) {
  const faceCenters = goldberg.goldbergData.faceCenters;
  const grouped = new Map();

  for (const triangle of graph.triangles) {
    const centroid = graph.positions[triangle[0]]
      .add(graph.positions[triangle[1]])
      .add(graph.positions[triangle[2]])
      .scale(1 / 3);
    const faceIndex = findClosestFace(centroid, faceCenters);
    if (!grouped.has(faceIndex)) {
      grouped.set(faceIndex, {
        edgeCounts: new Map(),
        vertices: new Set(),
      });
    }
    const face = grouped.get(faceIndex);
    face.vertices.add(triangle[0]);
    face.vertices.add(triangle[1]);
    face.vertices.add(triangle[2]);
    countEdge(face.edgeCounts, triangle[0], triangle[1]);
    countEdge(face.edgeCounts, triangle[1], triangle[2]);
    countEdge(face.edgeCounts, triangle[2], triangle[0]);
  }

  graph.adjacency = buildPolygonAdjacency(grouped, graph.positions.length);

  const pentagons = [];
  grouped.forEach((face, faceIndex) => {
    if (face.vertices.size !== 5) {
      return;
    }
    const vertices = [...face.vertices];
    pentagons.push({
      faceIndex,
      center: faceCenters[faceIndex].clone(),
      labelCenter: averagePositions(vertices, graph.positions),
      vertices,
    });
  });

  if (pentagons.length !== 12) {
    throw new Error(`Expected 12 pentagons, found ${pentagons.length}.`);
  }

  return pentagons;
}

function buildPolygonAdjacency(groupedFaces, vertexCount) {
  const adjacency = Array.from({ length: vertexCount }, () => new Set());

  groupedFaces.forEach((face) => {
    for (const [edgeKey, count] of face.edgeCounts) {
      if (count !== 1) {
        continue;
      }
      const [left, right] = edgeKey.split(":").map(Number);
      link(adjacency, left, right);
    }
  });

  return adjacency;
}

function countEdge(edgeCounts, left, right) {
  const edgeKey = left < right ? `${left}:${right}` : `${right}:${left}`;
  edgeCounts.set(edgeKey, (edgeCounts.get(edgeKey) || 0) + 1);
}

function mapPatches(pentagons, graph) {
  const { adjacency, positions } = graph;
  const north = pentagons.reduce((best, current) => (current.center.y > best.center.y ? current : best));
  const northDirection = north.center.clone().normalize();
  const south = pentagons.reduce((best, current) => (BABYLON.Vector3.Dot(current.center.clone().normalize(), northDirection) < BABYLON.Vector3.Dot(best.center.clone().normalize(), northDirection) ? current : best));
  const middle = pentagons.filter((patch) => patch.faceIndex !== north.faceIndex && patch.faceIndex !== south.faceIndex);

  const northNeighbors = sortByDistance(middle, north.center).slice(0, 5);
  const northNeighborIds = new Set(northNeighbors.map((patch) => patch.faceIndex));
  const southNeighbors = middle.filter((patch) => !northNeighborIds.has(patch.faceIndex));

  const northBand = sortCounterClockwise(northNeighbors, (patch) => patch.center);
  const southBand = sortCounterClockwise(southNeighbors, (patch) => patch.center);

  const northBandRotated = rotateToMaxZ(northBand);
  const southBandRotated = rotateToMaxZ(southBand);

  const patchByName = new Map();
  patchByName.set("N", north);
  patchByName.set("S", south);
  northBandRotated.forEach((patch, index) => patchByName.set(`N${index + 1}`, patch));
  southBandRotated.forEach((patch, index) => patchByName.set(`S${index + 1}`, patch));

  const namedPatches = [];

  for (const patchName of PATCH_HIERARCHY) {
    const patch = patchByName.get(patchName);
    if (!patch) {
      continue;
    }
    const anchor = getAnchorVector(patchName, patchByName);
    const aRing = orderRing(patch.vertices, patch.center, anchor, positions);
    const bRing = buildBRing(aRing, adjacency, patch.center, anchor, positions);
    const cRing = buildCRing(aRing, bRing, adjacency, patch.center, anchor, positions);
    namedPatches.push({
      anchor,
      center: patch.center.clone(),
      labelCenter: patch.labelCenter.clone(),
      name: patchName,
      rings: { A: aRing, B: bRing, C: cRing },
    });
  }

  return namedPatches;
}

function buildVertexLabels(patches, graph) {
  const labelByVertex = new Map();
  const patchByName = new Map(patches.map((patch) => [patch.name, patch]));

  for (const patchName of PATCH_HIERARCHY) {
    const patch = patchByName.get(patchName);
    if (!patch) {
      continue;
    }

    for (let index = 0; index < patch.rings.A.length; index += 1) {
      applyVertexLabel(labelByVertex, patch.rings.A[index], `${patchName}A${index + 1}`);
    }
    for (let index = 0; index < patch.rings.B.length; index += 1) {
      applyVertexLabel(labelByVertex, patch.rings.B[index], `${patchName}B${index + 1}`);
    }
    for (let index = 0; index < patch.rings.C.length; index += 1) {
      applyVertexLabel(labelByVertex, patch.rings.C[index], `${patchName}C${index + 1}`);
    }
  }

  return labelByVertex;
}

function getAnchorVector(patchName, patchByName) {
  const patchCenter = patchByName.get(patchName).center;
  const northCenter = patchByName.get("N").center;
  const southCenter = patchByName.get("S").center;

  if (patchName === "N") {
    return tangentDirection(patchCenter, patchByName.get("N1").center.subtract(patchCenter));
  }
  if (patchName === "S") {
    return tangentDirection(patchCenter, patchByName.get("S1").center.subtract(patchCenter));
  }
  if (patchName.startsWith("N")) {
    return tangentDirection(patchCenter, northCenter.subtract(patchCenter));
  }
  return tangentDirection(patchCenter, southCenter.subtract(patchCenter));
}

function buildBRing(aRing, adjacency, patchCenter, anchor, positions) {
  const aSet = new Set(aRing);
  const bCandidates = new Set();

  for (const vertex of aRing) {
    for (const neighbour of adjacency[vertex]) {
      if (!aSet.has(neighbour)) {
        bCandidates.add(neighbour);
      }
    }
  }

  if (bCandidates.size !== 5) {
    return orderRing([...bCandidates], patchCenter, anchor, positions).slice(0, 5);
  }

  const bRing = [];
  for (const aVertex of aRing) {
    const outwardNeighbours = [...adjacency[aVertex]].filter((neighbour) => bCandidates.has(neighbour));
    if (outwardNeighbours.length === 1) {
      bRing.push(outwardNeighbours[0]);
    } else {
      const ordered = orderRing(outwardNeighbours, patchCenter, anchor, positions);
      bRing.push(ordered[0]);
    }
  }
  return bRing;
}

function buildCRing(aRing, bRing, adjacency, patchCenter, anchor, positions) {
  const aSet = new Set(aRing);
  const bSet = new Set(bRing);
  const cRing = [];

  const basis = buildBasis(patchCenter, anchor);
  const bAngles = new Map(bRing.map((vertex) => [vertex, angleInBasis(positions[vertex], basis, patchCenter)]));

  for (const bVertex of bRing) {
    const cCandidates = [...adjacency[bVertex]].filter((neighbour) => !aSet.has(neighbour) && !bSet.has(neighbour));

    if (cCandidates.length < 2) {
      continue;
    }

    const bAngle = bAngles.get(bVertex);
    const candidateWithDelta = cCandidates.map((vertex) => {
      const angle = angleInBasis(positions[vertex], basis, patchCenter);
      const delta = normalizeAngle(angle - bAngle);
      return { delta, vertex };
    });

    const clockwise = candidateWithDelta.filter((item) => item.delta < 0).sort((left, right) => right.delta - left.delta)[0];
    const counterClockwise = candidateWithDelta.filter((item) => item.delta > 0).sort((left, right) => left.delta - right.delta)[0];

    if (clockwise && counterClockwise) {
      cRing.push(clockwise.vertex, counterClockwise.vertex);
      continue;
    }

    const ordered = orderRing(cCandidates, patchCenter, anchor, positions);
    cRing.push(ordered[0], ordered[1]);
  }

  return rotateArray(cRing, 1);
}

function orderRing(vertices, patchCenter, anchor, positions) {
  const basis = buildBasis(patchCenter, anchor);
  const sorted = [...vertices].sort((left, right) => {
    const leftAngle = angleInBasis(positions[left], basis, patchCenter);
    const rightAngle = angleInBasis(positions[right], basis, patchCenter);
    return leftAngle - rightAngle;
  });

  const mostAlignedIndex = sorted.reduce((bestIndex, vertex, index) => {
    const direction = tangentDirection(patchCenter, positions[vertex].subtract(patchCenter));
    const bestDirection = tangentDirection(patchCenter, positions[sorted[bestIndex]].subtract(patchCenter));
    return BABYLON.Vector3.Dot(direction, basis.x) > BABYLON.Vector3.Dot(bestDirection, basis.x) ? index : bestIndex;
  }, 0);

  return rotateArray(sorted, mostAlignedIndex);
}

function buildBasis(patchCenter, anchor) {
  const normal = patchCenter.normalize();
  const x = tangentDirection(patchCenter, anchor);
  const y = BABYLON.Vector3.Cross(x, normal).normalize();
  return { normal, x, y };
}

function angleInBasis(point, basis, center) {
  const localPoint = point.subtract(center);
  const projected = localPoint.subtract(basis.normal.scale(BABYLON.Vector3.Dot(localPoint, basis.normal)));
  return Math.atan2(BABYLON.Vector3.Dot(projected, basis.y), BABYLON.Vector3.Dot(projected, basis.x));
}

function tangentDirection(center, vector) {
  const normal = center.normalize();
  const projected = vector.subtract(normal.scale(BABYLON.Vector3.Dot(vector, normal)));
  if (projected.lengthSquared() < 1e-8) {
    return new BABYLON.Vector3(1, 0, 0);
  }
  return projected.normalize();
}

function findClosestFace(point, faceCenters) {
  let closestIndex = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (let index = 0; index < faceCenters.length; index += 1) {
    const distance = BABYLON.Vector3.DistanceSquared(point, faceCenters[index]);
    if (distance < bestDistance) {
      bestDistance = distance;
      closestIndex = index;
    }
  }
  return closestIndex;
}

function sortCounterClockwise(items, getCenter) {
  return [...items].sort((left, right) => {
    const leftAzimuth = Math.atan2(getCenter(left).z, getCenter(left).x);
    const rightAzimuth = Math.atan2(getCenter(right).z, getCenter(right).x);
    return leftAzimuth - rightAzimuth;
  });
}

function sortByDistance(items, point) {
  return [...items].sort((left, right) => BABYLON.Vector3.DistanceSquared(left.center, point) - BABYLON.Vector3.DistanceSquared(right.center, point));
}

function rotateToMaxZ(items) {
  if (items.length === 0) {
    return [];
  }
  const maxZIndex = items.reduce((best, item, index) => (item.center.z > items[best].center.z ? index : best), 0);
  return rotateArray(items, maxZIndex);
}

function rotateArray(items, startIndex) {
  return items.slice(startIndex).concat(items.slice(0, startIndex));
}

function normalizeAngle(value) {
  let angle = value;
  while (angle <= -Math.PI) {
    angle += Math.PI * 2;
  }
  while (angle > Math.PI) {
    angle -= Math.PI * 2;
  }
  return angle;
}

function averagePositions(vertices, positions) {
  return vertices.reduce((sum, vertex) => sum.add(positions[vertex]), BABYLON.Vector3.Zero()).scale(1 / vertices.length);
}

function applyVertexLabel(map, vertexIndex, label) {
  if (!map.has(vertexIndex)) {
    map.set(vertexIndex, label);
  }
}

function link(adjacency, left, right) {
  if (left === right) {
    return;
  }
  adjacency[left].add(right);
  adjacency[right].add(left);
}

function invertMap(map) {
  const inverted = new Map();
  for (const [key, value] of map) {
    inverted.set(value, key);
  }
  return inverted;
}

function buildLabelOrder() {
  const labels = [];
  for (const patchName of PATCH_HIERARCHY) {
    for (const ringName of ["A", "B"]) {
      for (let index = 1; index <= 5; index += 1) {
        labels.push(`${patchName}${ringName}${index}`);
      }
    }
    for (let index = 1; index <= 10; index += 1) {
      labels.push(`${patchName}C${index}`);
    }
  }
  return labels;
}

function validateGraph(graph, labelByVertex, vertexByLabel) {
  if (graph.positions.length !== 240) {
    throw new Error(`Expected 240 vertices, got ${graph.positions.length}.`);
  }
  if (labelByVertex.size !== 240) {
    throw new Error(`Expected 240 vertex labels, got ${labelByVertex.size}.`);
  }
  if (vertexByLabel.size !== 240) {
    throw new Error(`Expected 240 unique label lookups, got ${vertexByLabel.size}.`);
  }

  for (let vertexIndex = 0; vertexIndex < graph.adjacency.length; vertexIndex += 1) {
    const label = labelByVertex.get(vertexIndex);
    if (!label) {
      throw new Error(`Vertex ${vertexIndex} has no label.`);
    }
    if (graph.adjacency[vertexIndex].size !== 3) {
      throw new Error(`${label} has ${graph.adjacency[vertexIndex].size} neighbours instead of 3.`);
    }
    for (const neighbourIndex of graph.adjacency[vertexIndex]) {
      if (!graph.adjacency[neighbourIndex].has(vertexIndex)) {
        throw new Error(`${label} has a one-way connection to ${labelByVertex.get(neighbourIndex)}.`);
      }
    }
  }
}

main();

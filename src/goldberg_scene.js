(function renderGoldbergScene() {
  const canvas = document.getElementById("render_canvas");
  const engine = new BABYLON.Engine(canvas, true);
  const scene = new BABYLON.Scene(engine);

  scene.clearColor = new BABYLON.Color4(0.04, 0.05, 0.08, 1);

  const camera = new BABYLON.ArcRotateCamera("camera", -Math.PI / 2, Math.PI / 2.5, 18, BABYLON.Vector3.Zero(), scene);
  camera.attachControl(canvas, true);
  camera.lowerRadiusLimit = 7;
  camera.upperRadiusLimit = 30;
  camera.panningSensibility = 0;
  camera.wheelDeltaPercentage = 0.01;

  const light = new BABYLON.HemisphericLight("light", new BABYLON.Vector3(0, 1, 0), scene);
  light.intensity = 0.95;

  const goldberg = BABYLON.MeshBuilder.CreateGoldberg(
    "gp_2_2",
    {
      m: 2,
      n: 2,
      size: 4.5,
    },
    scene,
  );

  const surfaceMaterial = new BABYLON.StandardMaterial("surface", scene);
  surfaceMaterial.diffuseColor = new BABYLON.Color3(0.15, 0.55, 0.9);
  surfaceMaterial.specularColor = new BABYLON.Color3(0.1, 0.1, 0.1);
  surfaceMaterial.alpha = 0.8;
  goldberg.material = surfaceMaterial;
  goldberg.enableEdgesRendering();
  goldberg.edgesWidth = 1.8;
  goldberg.edgesColor = new BABYLON.Color4(0.98, 0.98, 0.98, 0.95);

  const graph = buildGraph(goldberg);
  const faceData = buildFaceData(goldberg, graph);
  const patches = mapPatches(faceData, graph);
  const vertexLabels = buildVertexLabels(patches, graph);
  const globeRoot = createGlobeRoot(scene, patches);

  goldberg.parent = globeRoot;
  createFaceLabels(scene, patches, graph.positions, globeRoot);
  createVertexLabels(scene, vertexLabels, graph.positions, globeRoot);

  engine.runRenderLoop(() => {
    scene.render();
  });

  window.addEventListener("resize", () => {
    engine.resize();
  });
})();

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
      grouped.set(faceIndex, new Set());
    }
    const vertices = grouped.get(faceIndex);
    vertices.add(triangle[0]);
    vertices.add(triangle[1]);
    vertices.add(triangle[2]);
  }

  const pentagons = [];
  grouped.forEach((vertexSet, faceIndex) => {
    if (vertexSet.size !== 5) {
      return;
    }
    const vertices = [...vertexSet];
    pentagons.push({
      faceIndex,
      center: faceCenters[faceIndex].clone(),
      labelCenter: averagePositions(vertices, graph.positions),
      vertices,
    });
  });

  if (pentagons.length !== 12) {
    console.warn(`Expected 12 pentagons, found ${pentagons.length}.`);
  }

  return pentagons;
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

  const patchNames = ["N", "N1", "N2", "N3", "N4", "N5", "S1", "S2", "S3", "S4", "S5", "S"];
  const namedPatches = [];

  for (const patchName of patchNames) {
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
  const hierarchy = ["N", "N1", "N2", "N3", "N4", "N5", "S1", "S2", "S3", "S4", "S5", "S"];
  const patchByName = new Map(patches.map((patch) => [patch.name, patch]));

  for (const patchName of hierarchy) {
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

  if (labelByVertex.size !== graph.positions.length) {
    console.warn(`Expected ${graph.positions.length} vertex labels, got ${labelByVertex.size}.`);
  }

  return labelByVertex;
}

function createGlobeRoot(scene, patches) {
  const northPatch = patches.find((patch) => patch.name === "N");
  const root = new BABYLON.TransformNode("globe_root", scene);
  root.rotationQuaternion = rotationBetweenDirections(northPatch.center, BABYLON.Axis.Y);
  return root;
}

function createFaceLabels(scene, patches, positions, parent) {
  const backgroundMaterial = new BABYLON.StandardMaterial("pentagon_label_background", scene);
  backgroundMaterial.diffuseColor = BABYLON.Color3.FromHexString("#ff8c00");
  backgroundMaterial.emissiveColor = BABYLON.Color3.FromHexString("#ff8c00");
  backgroundMaterial.disableLighting = true;
  backgroundMaterial.backFaceCulling = false;
  backgroundMaterial.zOffset = -4;

  for (const patch of patches) {
    const normal = patch.labelCenter.clone().normalize();
    createPentagonBackground(scene, patch, positions, normal, backgroundMaterial, parent);
    createFaceTextPlane(scene, patch.name, patch.labelCenter.add(normal.scale(0.04)), normal, patch.anchor, 1.23, "bold 150px monospace", true, parent);
    createFaceTextPlane(scene, `${patch.name}_inside`, patch.labelCenter.subtract(normal.scale(0.04)), normal.scale(-1), patch.anchor, 1.23, "bold 150px monospace", true, parent, patch.name);
  }
}

function createPentagonBackground(scene, patch, positions, normal, material, parent) {
  const center = patch.labelCenter.add(normal.scale(0.02));
  const vertices = patch.rings.A.map((vertex) => positions[vertex].add(normal.scale(0.02)));
  const meshPositions = center.asArray().concat(vertices.flatMap((vertex) => vertex.asArray()));
  const indices = [];

  for (let index = 0; index < vertices.length; index += 1) {
    indices.push(0, index + 1, ((index + 1) % vertices.length) + 1);
  }

  const mesh = new BABYLON.Mesh(`pentagon_background_${patch.name}`, scene);
  const vertexData = new BABYLON.VertexData();
  vertexData.positions = meshPositions;
  vertexData.indices = indices;
  vertexData.applyToMesh(mesh);
  mesh.parent = parent;
  mesh.isPickable = false;
  mesh.material = material;
}

function createVertexLabels(scene, labelsByVertex, positions, parent) {
  labelsByVertex.forEach((label, vertexIndex) => {
    const basePosition = positions[vertexIndex];
    const labelPosition = basePosition
      .clone()
      .normalize()
      .scale(basePosition.length() + 0.28);
    createTextPlane(scene, label, labelPosition, 0.54, "bold 78px monospace", parent);
  });
}

function createTextPlane(scene, text, position, size, font, parent) {
  const plane = createLabelPlane(scene, text, position, size, font, false, parent);
  plane.billboardMode = BABYLON.Mesh.BILLBOARDMODE_ALL;
}

function createFaceTextPlane(scene, name, position, normal, anchor, size, font, backFaceCulling = false, parent, text = name) {
  const plane = createLabelPlane(scene, name, position, size, font, backFaceCulling, parent, text);
  const zAxis = normal.scale(-1);
  const yAxis = tangentDirection(normal, anchor).normalize();
  const xAxis = BABYLON.Vector3.Cross(yAxis, zAxis).normalize();
  plane.rotation = BABYLON.Vector3.RotationFromAxis(xAxis, yAxis, zAxis);
}

function createLabelPlane(scene, name, position, size, font, backFaceCulling = false, parent, text = name) {
  const textureSize = 512;
  const texture = new BABYLON.DynamicTexture(`label_texture_${name}`, { height: textureSize, width: textureSize }, scene, true);
  texture.hasAlpha = true;
  texture.drawText(text, null, textureSize * 0.62, font, "#ffffff", "transparent", true, true);

  const material = new BABYLON.StandardMaterial(`label_material_${name}`, scene);
  material.diffuseTexture = texture;
  material.emissiveColor = BABYLON.Color3.White();
  material.disableLighting = true;
  material.opacityTexture = texture;
  material.backFaceCulling = backFaceCulling;
  material.zOffset = -2;

  const plane = BABYLON.MeshBuilder.CreatePlane(`label_${name}`, { size }, scene);
  plane.parent = parent;
  plane.isPickable = false;
  plane.material = material;
  plane.position = position;
  return plane;
}

function averagePositions(vertices, positions) {
  return vertices.reduce((sum, vertex) => sum.add(positions[vertex]), BABYLON.Vector3.Zero()).scale(1 / vertices.length);
}

function rotationBetweenDirections(from, to) {
  const start = from.clone().normalize();
  const end = to.clone().normalize();
  const dot = BABYLON.Vector3.Dot(start, end);

  if (dot > 0.999999) {
    return BABYLON.Quaternion.Identity();
  }

  if (dot < -0.999999) {
    const fallback = Math.abs(start.x) < 0.9 ? BABYLON.Axis.X : BABYLON.Axis.Z;
    return BABYLON.Quaternion.RotationAxis(BABYLON.Vector3.Cross(start, fallback).normalize(), Math.PI);
  }

  return BABYLON.Quaternion.RotationAxis(BABYLON.Vector3.Cross(start, end).normalize(), Math.acos(dot));
}

function getAnchorVector(patchName, patchByName) {
  const patchCenter = patchByName.get(patchName).center;
  const northCenter = patchByName.get("N").center;
  const southCenter = patchByName.get("S").center;

  if (patchName === "N") {
    const edgeMidpoint = patchByName.get("N1").center.add(patchByName.get("N5").center).scale(0.5);
    return tangentDirection(patchCenter, edgeMidpoint.subtract(patchCenter));
  }
  if (patchName === "S") {
    const edgeMidpoint = patchByName.get("S1").center.add(patchByName.get("S5").center).scale(0.5);
    return tangentDirection(patchCenter, edgeMidpoint.subtract(patchCenter));
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
    for (const neighbor of adjacency[vertex]) {
      if (!aSet.has(neighbor)) {
        bCandidates.add(neighbor);
      }
    }
  }

  if (bCandidates.size !== 5) {
    return orderRing([...bCandidates], patchCenter, anchor, positions).slice(0, 5);
  }

  const bRing = [];
  for (const aVertex of aRing) {
    const outwardNeighbors = [...adjacency[aVertex]].filter((neighbor) => bCandidates.has(neighbor));
    if (outwardNeighbors.length === 1) {
      bRing.push(outwardNeighbors[0]);
    } else {
      const ordered = orderRing(outwardNeighbors, patchCenter, anchor, positions);
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
    const cCandidates = [...adjacency[bVertex]].filter((neighbor) => !aSet.has(neighbor) && !bSet.has(neighbor));

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

  return cRing;
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
  const y = BABYLON.Vector3.Cross(normal, x).normalize();
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

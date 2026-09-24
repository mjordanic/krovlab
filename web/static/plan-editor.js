(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.KrovlabPlanEditor = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var HINTS = {
    hip: "Sloping face from this wall. Hips meet at the corners.",
    gable: "No roof face here. The wall is vertical; neighbours meet it at verges.",
    knee: "Wall rises vertically by this height, then the roof starts (a gablet, not a gable).",
    gambrel: "Two pitches on this wall: steep below, shallower above, split at the break."
  };

  function esc(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function snap(n) {
    return Math.round(n * 10) / 10;
  }

  function prefixOf(index) {
    return index === 0 ? "" : "cell-" + index + "-";
  }

  function signedArea(verts) {
    var a = 0;
    var i;
    var j;
    for (i = 0; i < verts.length; i += 1) {
      j = (i + 1) % verts.length;
      a += verts[i].x * verts[j].y - verts[j].x * verts[i].y;
    }
    return a / 2;
  }

  function isCcw(verts) {
    return signedArea(verts) > 0;
  }

  function outward(a, b, ccw) {
    var dx = b.x - a.x;
    var dy = b.y - a.y;
    var len = Math.hypot(dx, dy) || 1;
    var ox = dy / len;
    var oy = -dx / len;
    if (!ccw) {
      ox = -ox;
      oy = -oy;
    }
    return { x: ox, y: oy };
  }

  function bbox(cells) {
    var minX = 0;
    var minY = 0;
    var maxX = 0;
    var maxY = 0;
    var started = false;
    cells.forEach(function (cell) {
      cell.vertices.forEach(function (pt) {
        if (!started) {
          minX = maxX = pt.x;
          minY = maxY = pt.y;
          started = true;
        }
        if (pt.x < minX) { minX = pt.x; }
        if (pt.y < minY) { minY = pt.y; }
        if (pt.x > maxX) { maxX = pt.x; }
        if (pt.y > maxY) { maxY = pt.y; }
      });
    });
    return { minX: minX, minY: minY, maxX: maxX, maxY: maxY, started: started };
  }

  function defaultHole(verts) {
    var box = bbox([{ vertices: verts }]);
    var hx = Math.max(0.5, (box.maxX - box.minX) * 0.2);
    var hy = Math.max(0.5, (box.maxY - box.minY) * 0.2);
    return [
      { x: snap(box.minX + hx), y: snap(box.minY + hy) },
      { x: snap(box.maxX - hx), y: snap(box.minY + hy) },
      { x: snap(box.maxX - hx), y: snap(box.maxY - hy) },
      { x: snap(box.minX + hx), y: snap(box.maxY - hy) }
    ];
  }

  function blankCell(verts, pitch) {
    pitch = pitch || "45";
    return {
      vertices: verts,
      types: verts.map(function () { return "hip"; }),
      pitches: verts.map(function () { return pitch; }),
      knees: verts.map(function () { return "0"; }),
      shallows: verts.map(function () { return ""; }),
      breaks: verts.map(function () { return "0"; }),
      overhang: "0",
      useOverhang: false,
      eaveHeight: "0",
      useEave: false,
      hole: [],
      extraHoles: [],
      useHole: false,
      roofHeight: ""
    };
  }

  function distToSegment(x, y, a, b) {
    var dx = b.x - a.x;
    var dy = b.y - a.y;
    var len2 = dx * dx + dy * dy;
    if (len2 === 0) {
      return Math.hypot(x - a.x, y - a.y);
    }
    var t = ((x - a.x) * dx + (y - a.y) * dy) / len2;
    if (t < 0) { t = 0; } else if (t > 1) { t = 1; }
    return Math.hypot(x - (a.x + t * dx), y - (a.y + t * dy));
  }

  function pointInRing(x, y, vertices) {
    var inside = false;
    var n = vertices.length;
    var j = n - 1;
    var i;
    for (i = 0; i < n; i += 1) {
      var a = vertices[i];
      var b = vertices[j];
      if (a.y > y !== b.y > y && x < ((b.x - a.x) * (y - a.y)) / (b.y - a.y) + a.x) {
        inside = !inside;
      }
      j = i;
    }
    return inside;
  }

  function createEditor(options) {
    options = options || {};
    var applyToAll = options.applyToAll || "45";
    var cells = [];
    var dormers = [];
    var selectedCell = -1;
    var selectedEdge = null;
    var selectedVertex = null;
    var selectedDormer = -1;
    var selectedDormerVertex = null;

    function allRings(cell) {
      var rings = [cell.vertices];
      if (cell.useHole && cell.hole && cell.hole.length) {
        rings.push(cell.hole);
      }
      return rings;
    }

    function hitVertex(x, y) {
      var best = null;
      var bestDist = 0.25;
      var c;
      var r;
      var i;
      var offset;
      for (c = 0; c < cells.length; c += 1) {
        offset = 0;
        var rings = allRings(cells[c]);
        for (r = 0; r < rings.length; r += 1) {
          for (i = 0; i < rings[r].length; i += 1) {
            var pt = rings[r][i];
            var d = Math.hypot(x - pt.x, y - pt.y);
            if (d <= bestDist) {
              bestDist = d;
              best = { cell: c, vertex: offset + i };
            }
          }
          offset += rings[r].length;
        }
      }
      return best;
    }

    function hitEdge(x, y) {
      var best = null;
      var bestDist = 0.35;
      var c;
      var r;
      var i;
      var offset;
      for (c = 0; c < cells.length; c += 1) {
        offset = 0;
        var rings = allRings(cells[c]);
        for (r = 0; r < rings.length; r += 1) {
          var verts = rings[r];
          for (i = 0; i < verts.length; i += 1) {
            var d = distToSegment(x, y, verts[i], verts[(i + 1) % verts.length]);
            if (d <= bestDist) {
              bestDist = d;
              best = { cell: c, edge: offset + i };
            }
          }
          offset += verts.length;
        }
      }
      return best;
    }

    function hitDormerVertex(x, y) {
      var best = null;
      var bestDist = 0.25;
      var d;
      var i;
      for (d = 0; d < dormers.length; d += 1) {
        for (i = 0; i < dormers[d].vertices.length; i += 1) {
          var pt = dormers[d].vertices[i];
          var dist = Math.hypot(x - pt.x, y - pt.y);
          if (dist <= bestDist) {
            bestDist = dist;
            best = { dormer: d, vertex: i };
          }
        }
      }
      return best;
    }

    function clickPlan(x, y) {
      var dvert = hitDormerVertex(x, y);
      if (dvert) {
        selectedDormer = dvert.dormer;
        selectedDormerVertex = dvert.vertex;
        selectedCell = dormers[dvert.dormer].cell;
        selectedVertex = null;
        selectedEdge = null;
        return;
      }
      var vert = hitVertex(x, y);
      if (vert) {
        selectedCell = vert.cell;
        selectedVertex = vert.vertex;
        selectedEdge = null;
        selectedDormer = -1;
        selectedDormerVertex = null;
        return;
      }
      var edge = hitEdge(x, y);
      if (edge) {
        selectedCell = edge.cell;
        selectedEdge = edge.edge;
        selectedVertex = null;
        selectedDormer = -1;
        selectedDormerVertex = null;
        return;
      }
      var i;
      for (i = cells.length - 1; i >= 0; i -= 1) {
        if (pointInRing(x, y, cells[i].vertices)) {
          selectedCell = i;
          selectedEdge = null;
          selectedVertex = null;
          selectedDormer = -1;
          selectedDormerVertex = null;
          return;
        }
      }
    }

    function addDetachedCell() {
      var box = bbox(cells);
      var originX = box.started ? box.maxX + 1 : 0;
      var originY = box.started ? box.minY : 0;
      var rect = [
        { x: snap(originX), y: snap(originY) },
        { x: snap(originX + 5), y: snap(originY) },
        { x: snap(originX + 5), y: snap(originY + 6) },
        { x: snap(originX), y: snap(originY + 6) }
      ];
      cells.push(blankCell(rect, applyToAll));
      selectedCell = cells.length - 1;
      selectedEdge = null;
      selectedVertex = null;
      selectedDormer = -1;
      selectedDormerVertex = null;
    }

    function addCellOnSelectedWall() {
      if (selectedCell < 0 || selectedEdge === null) {
        return;
      }
      var cell = cells[selectedCell];
      if (selectedEdge >= cell.vertices.length) {
        return;
      }
      var a = cell.vertices[selectedEdge];
      var b = cell.vertices[(selectedEdge + 1) % cell.vertices.length];
      var n = outward(a, b, isCcw(cell.vertices));
      var depth = 5;
      var nx = n.x * depth;
      var ny = n.y * depth;
      var quad = [
        { x: snap(a.x), y: snap(a.y) },
        { x: snap(a.x + nx), y: snap(a.y + ny) },
        { x: snap(b.x + nx), y: snap(b.y + ny) },
        { x: snap(b.x), y: snap(b.y) }
      ];
      if (!isCcw(quad)) {
        quad.reverse();
      }
      cells.push(blankCell(quad, applyToAll));
      selectedCell = cells.length - 1;
      selectedEdge = null;
      selectedVertex = null;
      selectedDormer = -1;
      selectedDormerVertex = null;
    }

    function addVertexOnSelectedWall() {
      if (selectedCell < 0 || selectedEdge === null) {
        return;
      }
      var cell = cells[selectedCell];
      var i = selectedEdge;
      var ring = cell.vertices;
      var local = i;
      if (i >= cell.vertices.length) {
        ring = cell.hole;
        local = i - cell.vertices.length;
      }
      if (!ring || !ring.length) {
        return;
      }
      var a = ring[local];
      var b = ring[(local + 1) % ring.length];
      var mid = { x: snap((a.x + b.x) / 2), y: snap((a.y + b.y) / 2) };
      ring.splice(local + 1, 0, mid);
      cell.types.splice(i + 1, 0, cell.types[i]);
      cell.pitches.splice(i + 1, 0, cell.pitches[i]);
      cell.knees.splice(i + 1, 0, cell.knees[i]);
      cell.shallows.splice(i + 1, 0, cell.shallows[i]);
      cell.breaks.splice(i + 1, 0, cell.breaks[i]);
      selectedEdge = i;
    }

    function deleteCell() {
      if (cells.length <= 1) {
        return;
      }
      if (selectedCell < 0) {
        selectedCell = cells.length - 1;
      }
      cells.splice(selectedCell, 1);
      if (selectedCell >= cells.length) {
        selectedCell = cells.length - 1;
      }
      selectedEdge = null;
      selectedVertex = null;
      selectedDormer = -1;
      selectedDormerVertex = null;
    }

    function setWallType(kind) {
      if (selectedCell < 0 || selectedEdge === null) {
        return;
      }
      var cell = cells[selectedCell];
      var i = selectedEdge;
      cell.types[i] = kind;
      if (kind === "gable") {
        cell.pitches[i] = "90";
        cell.knees[i] = "0";
        cell.shallows[i] = "";
        cell.breaks[i] = "0";
      } else if (kind === "knee") {
        if (cell.pitches[i] === "90") {
          cell.pitches[i] = applyToAll;
        }
        cell.shallows[i] = "";
        cell.breaks[i] = "0";
        if (!(parseFloat(cell.knees[i]) > 0)) {
          cell.knees[i] = "3";
        }
      } else if (kind === "gambrel") {
        if (cell.pitches[i] === "90") {
          cell.pitches[i] = "60";
        }
        cell.knees[i] = "0";
        if (!cell.shallows[i]) {
          cell.shallows[i] = "30";
        }
        if (!(parseFloat(cell.breaks[i]) > 0)) {
          cell.breaks[i] = "1";
        }
      } else {
        if (cell.pitches[i] === "90") {
          cell.pitches[i] = applyToAll;
        }
        cell.knees[i] = "0";
        cell.shallows[i] = "";
        cell.breaks[i] = "0";
      }
    }

    function setPitch(pitch) {
      if (selectedCell < 0 || selectedEdge === null) {
        return;
      }
      var cell = cells[selectedCell];
      cell.pitches[selectedEdge] = String(pitch);
      if (cell.types[selectedEdge] === "gable") {
        cell.types[selectedEdge] = "hip";
      }
    }

    function setGable(on) {
      if (on) {
        setWallType("gable");
      } else if (selectedCell >= 0 && selectedEdge !== null) {
        setWallType("hip");
      }
    }

    function setKneeHeight(height) {
      if (selectedCell < 0 || selectedEdge === null) {
        return;
      }
      var cell = cells[selectedCell];
      cell.knees[selectedEdge] = String(height);
      if (parseFloat(String(height)) > 0) {
        setWallType("knee");
        cell.knees[selectedEdge] = String(height);
      }
    }

    function setGambrel(steep, shallow, breakHeight) {
      if (selectedCell < 0 || selectedEdge === null) {
        return;
      }
      var cell = cells[selectedCell];
      cell.types[selectedEdge] = "gambrel";
      cell.pitches[selectedEdge] = String(steep);
      cell.shallows[selectedEdge] = String(shallow);
      cell.breaks[selectedEdge] = String(breakHeight);
      cell.knees[selectedEdge] = "0";
    }

    function setEaveHeight(height) {
      if (selectedCell < 0) {
        return;
      }
      cells[selectedCell].eaveHeight = String(height);
      cells[selectedCell].useEave = parseFloat(String(height)) !== 0;
    }

    function setPitchOnSloping(value) {
      applyToAll = value;
      cells.forEach(function (cell) {
        cell.types.forEach(function (kind, i) {
          if (kind === "hip" || kind === "gambrel") {
            cell.pitches[i] = value;
          }
        });
      });
    }

    function moveDormerVertex(dormerIndex, vertexIndex, x, y) {
      var dormer = dormers[dormerIndex];
      if (!dormer || vertexIndex < 0 || vertexIndex >= dormer.vertices.length) {
        return;
      }
      dormer.vertices[vertexIndex] = { x: x, y: y };
    }

    function applySettings(map) {
      if (map.set_pitch) {
        applyToAll = map.set_pitch;
      }
      cells.forEach(function (cell, index) {
        var p = prefixOf(index);
        if (!Object.prototype.hasOwnProperty.call(map, p + "outer-x-0")) {
          return;
        }
        var verts = readRingFromMap(map, p, "outer");
        if (!verts.length) {
          return;
        }
        cells[index] = cellFromMap(map, p, verts);
      });
      if (Object.prototype.hasOwnProperty.call(map, "dormer-0-x-0")) {
        dormers = readDormers(map);
      }
    }

    function moveVertex(cellIndex, vertexIndex, x, y) {
      var cell = cells[cellIndex];
      if (!cell || vertexIndex < 0) {
        return;
      }
      var n = cell.vertices.length;
      if (vertexIndex < n) {
        cell.vertices[vertexIndex] = { x: x, y: y };
        return;
      }
      var holeIndex = vertexIndex - n;
      if (cell.hole && holeIndex < cell.hole.length) {
        cell.hole[holeIndex] = { x: x, y: y };
      }
    }

    function kindFromMap(map, pfx, i) {
      var t = map[pfx + "type-" + i];
      if (t === "hip" || t === "gable" || t === "knee" || t === "gambrel") {
        return t;
      }
      if (map[pfx + "gable-" + i] === "on") {
        return "gable";
      }
      var brk = parseFloat(map[pfx + "gambrel-break-" + i]);
      if (map[pfx + "gambrel-shallow-" + i] && brk > 0) {
        return "gambrel";
      }
      var knee = parseFloat(map[pfx + "knee-" + i]);
      if (knee > 0) {
        return "knee";
      }
      return "hip";
    }

    function readRingFromMap(map, pfx, kind) {
      var pts = [];
      var i = 0;
      while (Object.prototype.hasOwnProperty.call(map, pfx + kind + "-x-" + i)) {
        var xs = map[pfx + kind + "-x-" + i];
        var ys = map[pfx + kind + "-y-" + i];
        if (xs !== "" && ys !== "" && xs != null && ys != null &&
            !Number.isNaN(parseFloat(String(xs))) &&
            !Number.isNaN(parseFloat(String(ys)))) {
          pts.push({ x: parseFloat(String(xs)), y: parseFloat(String(ys)) });
        }
        i += 1;
      }
      return pts;
    }

    function cellFromMap(map, pfx, vertices) {
      var types = [];
      var pitches = [];
      var knees = [];
      var shallows = [];
      var breaks = [];
      var i;
      var holePts = map[pfx + "use_hole"] === "on" ? readRingFromMap(map, pfx, "hole") : [];
      var extraHoles = [];
      if (map[pfx + "use_hole"] === "on") {
        var h = 1;
        while (true) {
          var extra = readRingFromMap(map, pfx, "hole-" + h);
          if (!extra.length) {
            break;
          }
          extraHoles.push(extra);
          h += 1;
        }
      }
      var extraLen = 0;
      extraHoles.forEach(function (ring) { extraLen += ring.length; });
      var n = vertices.length + holePts.length + extraLen;
      for (i = 0; i < n; i += 1) {
        var kind = kindFromMap(map, pfx, i);
        types.push(kind);
        var pitch = map[pfx + "pitch-" + i];
        pitches.push(kind === "gable" ? "90" : (pitch ? String(pitch) : applyToAll));
        var knee = map[pfx + "knee-" + i];
        knees.push(knee != null && knee !== "" ? String(knee) : "0");
        var shallow = map[pfx + "gambrel-shallow-" + i];
        shallows.push(shallow != null && shallow !== "" ? String(shallow) : "");
        var brk = map[pfx + "gambrel-break-" + i];
        breaks.push(brk != null && brk !== "" ? String(brk) : "0");
      }
      return {
        vertices: vertices,
        types: types,
        pitches: pitches,
        knees: knees,
        shallows: shallows,
        breaks: breaks,
        overhang: map[pfx + "overhang"] || "0",
        useOverhang: map[pfx + "use_overhang"] === "on",
        eaveHeight: map[pfx + "eave_height"] || "0",
        useEave: map[pfx + "use_eave_height"] === "on",
        hole: holePts,
        extraHoles: extraHoles,
        useHole: map[pfx + "use_hole"] === "on",
        roofHeight: pfx === "" ? (map.roof_height || "") : ""
      };
    }

    function loadFields(map) {
      cells = [];
      selectedEdge = null;
      selectedVertex = null;
      var first = readRingFromMap(map, "", "outer");
      if (first.length) {
        cells.push(cellFromMap(map, "", first));
      }
      var n = 1;
      while (true) {
        var extra = readRingFromMap(map, "cell-" + n + "-", "outer");
        if (!extra.length) {
          break;
        }
        cells.push(cellFromMap(map, "cell-" + n + "-", extra));
        n += 1;
      }
      dormers = readDormers(map);
      selectedCell = cells.length ? 0 : -1;
      var rawSel = map.selected_cell;
      if (rawSel != null && rawSel !== "" && rawSel !== "-1") {
        var idx = parseInt(String(rawSel), 10);
        if (!Number.isNaN(idx) && idx >= 0 && idx < cells.length) {
          selectedCell = idx;
        }
      }
      selectedEdge = null;
      selectedVertex = null;
      selectedDormer = -1;
      selectedDormerVertex = null;
    }

    function readDormers(map) {
      var items = [];
      var index = 0;
      while (Object.prototype.hasOwnProperty.call(map, "dormer-" + index + "-x-0")) {
        var vertices = [];
        var i = 0;
        while (Object.prototype.hasOwnProperty.call(map, "dormer-" + index + "-x-" + i)) {
          var xs = map["dormer-" + index + "-x-" + i];
          var ys = map["dormer-" + index + "-y-" + i];
          if (xs !== "" && ys !== "" && xs != null && ys != null &&
              !Number.isNaN(parseFloat(String(xs))) &&
              !Number.isNaN(parseFloat(String(ys)))) {
            vertices.push({ x: parseFloat(String(xs)), y: parseFloat(String(ys)) });
          }
          i += 1;
        }
        var pitches = [];
        var types = [];
        for (i = 0; i < vertices.length; i += 1) {
          var kind = map["dormer-" + index + "-type-" + i] ||
            (map["dormer-" + index + "-gable-" + i] === "on" ? "gable" : "hip");
          types.push(kind);
          var pitch = map["dormer-" + index + "-pitch-" + i];
          pitches.push(kind === "gable" ? "90" : (pitch ? String(pitch) : applyToAll));
        }
        var cell = parseInt(String(map["dormer-" + index + "-cell"] || "0"), 10);
        items.push({
          cell: Number.isNaN(cell) ? 0 : cell,
          vertices: vertices,
          pitches: pitches,
          types: types
        });
        index += 1;
      }
      return items;
    }

    function fields() {
      var out = {};
      cells.forEach(function (cell, index) {
        var p = prefixOf(index);
        cell.vertices.forEach(function (pt, i) {
          out[p + "outer-x-" + i] = String(pt.x);
          out[p + "outer-y-" + i] = String(pt.y);
        });
        cell.types.forEach(function (kind, i) {
          out[p + "type-" + i] = kind;
          out[p + "pitch-" + i] = kind === "gable" ? "90" : String(cell.pitches[i] || applyToAll);
          if (kind === "knee") {
            out[p + "knee-" + i] = String(cell.knees[i] || "0");
          }
          if (kind === "gambrel") {
            out[p + "gambrel-shallow-" + i] = String(cell.shallows[i] || "");
            if (parseFloat(String(cell.breaks[i])) > 0) {
              out[p + "gambrel-break-" + i] = String(cell.breaks[i]);
            }
          }
        });
        out[p + "overhang"] = cell.overhang;
        if (cell.useOverhang) {
          out[p + "use_overhang"] = "on";
        }
        out[p + "eave_height"] = cell.eaveHeight;
        if (cell.useEave) {
          out[p + "use_eave_height"] = "on";
        }
        if (index === 0 && cell.roofHeight) {
          out.roof_height = String(cell.roofHeight);
        }
        if (cell.useHole) {
          out[p + "use_hole"] = "on";
          (cell.hole || []).forEach(function (pt, i) {
            out[p + "hole-x-" + i] = String(pt.x);
            out[p + "hole-y-" + i] = String(pt.y);
          });
          (cell.extraHoles || []).forEach(function (ring, hi) {
            ring.forEach(function (pt, i) {
              out[p + "hole-" + (hi + 1) + "-x-" + i] = String(pt.x);
              out[p + "hole-" + (hi + 1) + "-y-" + i] = String(pt.y);
            });
          });
        }
      });
      dormers.forEach(function (dormer, index) {
        var dp = "dormer-" + index + "-";
        out[dp + "cell"] = String(dormer.cell);
        dormer.vertices.forEach(function (pt, i) {
          out[dp + "x-" + i] = String(pt.x);
          out[dp + "y-" + i] = String(pt.y);
        });
        (dormer.types || []).forEach(function (kind, i) {
          out[dp + "type-" + i] = kind;
        });
        (dormer.pitches || []).forEach(function (pitch, i) {
          out[dp + "pitch-" + i] = String(pitch);
        });
      });
      return out;
    }

    function rings() {
      return cells.map(function (cell) {
        return cell.vertices.map(function (pt) {
          return [pt.x, pt.y];
        });
      });
    }

    function formMap(form) {
      var map = {};
      Array.prototype.forEach.call(form.querySelectorAll("[name]"), function (el) {
        if (el.type === "checkbox") {
          if (el.checked) {
            map[el.name] = "on";
          }
        } else if (el.type === "radio") {
          if (el.checked) {
            map[el.name] = el.value;
          }
        } else if (el.name) {
          map[el.name] = el.value;
        }
      });
      var apply = form.querySelector("[name=set_pitch]");
      if (apply && apply.value) {
        map.set_pitch = apply.value;
      }
      return map;
    }

    function loadForm(form) {
      var map = formMap(form);
      var apply = form.querySelector("[name=set_pitch]");
      if (apply && apply.value) {
        applyToAll = apply.value;
      }
      loadFields(map);
    }

    return {
      clickPlan: clickPlan,
      addDetachedCell: addDetachedCell,
      addCellOnSelectedWall: addCellOnSelectedWall,
      addVertexOnSelectedWall: addVertexOnSelectedWall,
      deleteCell: deleteCell,
      setWallType: setWallType,
      setPitch: setPitch,
      setGable: setGable,
      setKneeHeight: setKneeHeight,
      setGambrel: setGambrel,
      setEaveHeight: setEaveHeight,
      setPitchOnSloping: setPitchOnSloping,
      moveVertex: moveVertex,
      moveDormerVertex: moveDormerVertex,
      applySettings: applySettings,
      applyForm: function (formEl) { applySettings(formMap(formEl)); },
      loadFields: loadFields,
      loadForm: loadForm,
      fields: fields,
      rings: rings,
      setApplyToAll: function (value) { applyToAll = value; },
      selectedCell: function () { return selectedCell; },
      selectedEdge: function () { return selectedEdge; },
      selectedVertex: function () { return selectedVertex; },
      selectedDormer: function () { return selectedDormer; },
      selectedDormerVertex: function () { return selectedDormerVertex; },
      cells: function () { return cells; },
      dormers: function () { return dormers; },
      setUseHole: function (on) {
        if (selectedCell < 0) { return; }
        var cell = cells[selectedCell];
        cell.useHole = !!on;
        if (cell.useHole && (!cell.hole || !cell.hole.length)) {
          cell.hole = defaultHole(cell.vertices);
        }
        if (!cell.useHole) {
          cell.types.splice(cell.vertices.length);
          cell.pitches.splice(cell.vertices.length);
          cell.knees.splice(cell.vertices.length);
          cell.shallows.splice(cell.vertices.length);
          cell.breaks.splice(cell.vertices.length);
          cell.hole = [];
          cell.extraHoles = [];
        } else {
          var holeLen = (cell.hole ? cell.hole.length : 0);
          (cell.extraHoles || []).forEach(function (ring) { holeLen += ring.length; });
          while (cell.types.length < cell.vertices.length + holeLen) {
            cell.types.push("hip");
            cell.pitches.push(applyToAll);
            cell.knees.push("0");
            cell.shallows.push("");
            cell.breaks.push("0");
          }
        }
      }
    };
  }

  function ringAttr(ring) {
    return ring.map(function (pt) {
      return pt[0] + "," + pt[1];
    }).join(" ");
  }

  function metresFromEvent(svg, event) {
    var group = svg.querySelector("#plan-metres") || svg;
    var ctm = group.getScreenCTM();
    if (!ctm) {
      return { x: 0, y: 0 };
    }
    var pt = svg.createSVGPoint();
    pt.x = event.clientX;
    pt.y = event.clientY;
    var loc = pt.matrixTransform(ctm.inverse());
    return { x: snap(loc.x), y: snap(loc.y) };
  }

  function collectPoints(editor) {
    var pts = [];
    editor.cells().forEach(function (cell) {
      cell.vertices.forEach(function (pt) { pts.push([pt.x, pt.y]); });
      if (cell.useHole && cell.hole) {
        cell.hole.forEach(function (pt) { pts.push([pt.x, pt.y]); });
        (cell.extraHoles || []).forEach(function (ring) {
          ring.forEach(function (pt) { pts.push([pt.x, pt.y]); });
        });
      }
    });
    editor.dormers().forEach(function (d) {
      d.vertices.forEach(function (pt) { pts.push([pt.x, pt.y]); });
    });
    return pts;
  }

  function appendRing(html, ring, index, wallOffset, selectedCell, selectedEdge, holeClass) {
    var cls = index === selectedCell ? " is-selected" : "";
    if (holeClass) {
      cls += " " + holeClass;
    }
    html += "<polygon class=\"" + cls.trim() + "\" data-cell=\"" + index + "\" data-ring=\"" +
      ringAttr(ring) + "\" points=\"" + ringAttr(ring) + "\"></polygon>";
    ring.forEach(function (start, i) {
      var wall = wallOffset + i;
      var end = ring[(i + 1) % ring.length];
      var hitCls = (index === selectedCell && selectedEdge === wall) ? " is-selected" : "";
      html += "<line class=\"wall-hit" + hitCls + "\" x1=\"" + start[0] + "\" y1=\"" + start[1] +
        "\" x2=\"" + end[0] + "\" y2=\"" + end[1] + "\" data-cell=\"" + index + "\" data-wall=\"" + wall + "\"></line>";
      var mx = (start[0] + end[0]) / 2;
      var my = (start[1] + end[1]) / 2;
      html += "<text font-size=\"0.35\" transform=\"translate(" + mx + " " + my + ") scale(1,-1)\" text-anchor=\"middle\" dy=\"-0.4em\">" +
        (wall + 1) + "</text>";
    });
    ring.forEach(function (pt, i) {
      html += "<circle cx=\"" + pt[0] + "\" cy=\"" + pt[1] + "\" r=\"0.18\" data-cell=\"" +
        index + "\" data-vertex=\"" + (wallOffset + i) + "\"></circle>";
    });
    return html;
  }

  function drawSvg(svg, editor) {
    var pts = collectPoints(editor);
    var minX = 0;
    var minY = 0;
    var maxX = 10;
    var maxY = 6;
    if (pts.length) {
      minX = maxX = pts[0][0];
      minY = maxY = pts[0][1];
      pts.forEach(function (pt) {
        if (pt[0] < minX) { minX = pt[0]; }
        if (pt[1] < minY) { minY = pt[1]; }
        if (pt[0] > maxX) { maxX = pt[0]; }
        if (pt[1] > maxY) { maxY = pt[1]; }
      });
    }
    var pad = 1.5;
    minX -= pad;
    minY -= pad;
    maxX += pad;
    maxY += pad;
    var width = maxX - minX || 12;
    var height = maxY - minY || 8;
    svg.setAttribute("viewBox", minX + " " + (-maxY) + " " + width + " " + height);
    svg.setAttribute("preserveAspectRatio", "xMinYMid meet");
    var html = "<g id=\"plan-metres\" transform=\"scale(1,-1)\">";
    var selectedCell = editor.selectedCell();
    var selectedEdge = editor.selectedEdge();
    editor.cells().forEach(function (cell, index) {
      var outer = cell.vertices.map(function (pt) { return [pt.x, pt.y]; });
      html = appendRing(html, outer, index, 0, selectedCell, selectedEdge, "");
      if (cell.useHole && cell.hole && cell.hole.length) {
        var hole = cell.hole.map(function (pt) { return [pt.x, pt.y]; });
        html = appendRing(html, hole, index, outer.length, selectedCell, selectedEdge, "is-hole");
        var holeOffset = outer.length + hole.length;
        (cell.extraHoles || []).forEach(function (ring) {
          var extra = ring.map(function (pt) { return [pt.x, pt.y]; });
          html = appendRing(html, extra, index, holeOffset, selectedCell, selectedEdge, "is-hole");
          holeOffset += extra.length;
        });
      }
    });
    editor.dormers().forEach(function (dormer, dIndex) {
      var dRing = dormer.vertices.map(function (pt) { return [pt.x, pt.y]; });
      html += "<polygon class=\"is-dormer\" points=\"" + ringAttr(dRing) + "\"></polygon>";
      dRing.forEach(function (pt, i) {
        var dSel = (editor.selectedDormer() === dIndex && editor.selectedDormerVertex() === i) ? " is-selected" : "";
        html += "<circle class=\"is-dormer" + dSel + "\" cx=\"" + pt[0] + "\" cy=\"" + pt[1] +
          "\" r=\"0.18\" data-dormer=\"" + dIndex + "\" data-vertex=\"" + i + "\"></circle>";
      });
    });
    html += "</g>";
    svg.innerHTML = html;
  }

  function experimentalSelected() {
    if (typeof document === "undefined") {
      return false;
    }
    var checked = document.querySelector("input[name=\"method\"]:checked");
    return !!(checked && checked.value === "experimental");
  }

  function wallRowHtml(pfx, cell, i, cellIndex) {
    var kind = cell.types[i] || "hip";
    var hints = (typeof window !== "undefined" && window.KROVLAB_HINTS) ? window.KROVLAB_HINTS : HINTS;
    var html = "<div class=\"wall\" data-cell=\"" + cellIndex + "\" data-wall=\"" + i + "\">";
    html += "<div class=\"wall-head\"><span>Wall " + (i + 1) + "</span></div>";
    if (experimentalSelected()) {
      html += "<input type=\"hidden\" name=\"" + pfx + "type-" + i + "\" value=\"" + esc(kind) + "\">";
      html += "<input type=\"hidden\" name=\"" + pfx + "pitch-" + i + "\" value=\"" +
        esc(cell.pitches[i] || "45") + "\"></div>";
      return html;
    }
    html += "<div class=\"wall-types\" role=\"radiogroup\">";
    ["hip", "gable", "knee", "gambrel"].forEach(function (k) {
      var label = k.charAt(0).toUpperCase() + k.slice(1);
      html += "<label><input type=\"radio\" name=\"" + pfx + "type-" + i + "\" value=\"" + k + "\"";
      if (kind === k) { html += " checked"; }
      html += "> " + label + "</label>";
    });
    html += "</div><p class=\"hint wall-hint\">" + esc(hints[kind] || "") + "</p>";
    html += "<p class=\"wall-extra js-pitch\"" + (kind === "gable" ? " hidden" : "") + "><label>Pitch ";
    html += "<input name=\"" + pfx + "pitch-" + i + "\" value=\"" + esc(cell.pitches[i] || "45") + "\"";
    if (kind === "gable") { html += " disabled"; }
    html += "></label></p>";
    html += "<p class=\"wall-extra js-knee\"" + (kind !== "knee" ? " hidden" : "") + "><label>Knee height ";
    html += "<input name=\"" + pfx + "knee-" + i + "\" value=\"" + esc(cell.knees[i] || "0") + "\"> m</label></p>";
    html += "<p class=\"wall-extra js-gambrel\"" + (kind !== "gambrel" ? " hidden" : "") + ">";
    html += "<label>Shallow pitch <input name=\"" + pfx + "gambrel-shallow-" + i + "\" value=\"" +
      esc(cell.shallows[i] || "") + "\"></label> ";
    html += "<label>Break <input name=\"" + pfx + "gambrel-break-" + i + "\" value=\"" +
      esc(cell.breaks[i] || "0") + "\"> m</label></p></div>";
    return html;
  }

  function writeForm(form, editor) {
    var root = form.querySelector("#cells-root");
    var vertex = form.querySelector("#vertex-editor");
    if (!root) {
      return;
    }
    var html = "";
    var vhtml = "";
    editor.cells().forEach(function (cell, index) {
      var p = prefixOf(index);
      html += "<section class=\"cell-card\" data-cell=\"" + index + "\"><h3>Cell " + (index + 1) + "</h3>";
      html += "<div class=\"cell-extras\">";
      html += "<label><input type=\"checkbox\" name=\"" + p + "use_overhang\"" + (cell.useOverhang ? " checked" : "") +
        " data-extra=\"overhang\"> Overhang</label>";
      html += "<label><input type=\"checkbox\" name=\"" + p + "use_eave_height\"" + (cell.useEave ? " checked" : "") +
        " data-extra=\"eave\"> Eave height</label>";
      if (!experimentalSelected()) {
        html += "<label><input type=\"checkbox\" name=\"" + p + "use_hole\"" + (cell.useHole ? " checked" : "") +
          " data-extra=\"hole\"> Courtyard / hole</label>";
      }
      html += "</div>";
      html += "<p class=\"wall-extra js-extra\" data-kind=\"overhang\"" + (cell.useOverhang ? "" : " hidden") +
        "><label>Overhang <input name=\"" + p + "overhang\" value=\"" + esc(cell.overhang) + "\"> m past the walls</label></p>";
      html += "<p class=\"wall-extra js-extra\" data-kind=\"eave\"" + (cell.useEave ? "" : " hidden") +
        "><label>Eave height <input name=\"" + p + "eave_height\" value=\"" + esc(cell.eaveHeight) +
        "\"> m above datum</label></p>";
      if (index === 0 && experimentalSelected() && cell.roofHeight) {
        html += "<p class=\"wall-extra\"><label>Roof height <input name=\"roof_height\" value=\"" +
          esc(cell.roofHeight) + "\"> m above the eaves</label></p>";
      }
      var extraLen = 0;
      (cell.extraHoles || []).forEach(function (ring) { extraLen += ring.length; });
      var wallCount = cell.vertices.length + ((cell.useHole && cell.hole) ? cell.hole.length : 0) + extraLen;
      var w;
      for (w = 0; w < wallCount; w += 1) {
        html += wallRowHtml(p, cell, w, index);
      }
      html += "</section>";
      vhtml += "<p>Cell " + (index + 1) + " vertices (m)</p><table><thead><tr><th>x</th><th>y</th></tr></thead><tbody id=\"" +
        p + "outer-vertices\">";
      cell.vertices.forEach(function (pt, i) {
        vhtml += "<tr><td><input name=\"" + p + "outer-x-" + i + "\" value=\"" + esc(pt.x) +
          "\"></td><td><input name=\"" + p + "outer-y-" + i + "\" value=\"" + esc(pt.y) + "\"></td></tr>";
      });
      vhtml += "</tbody></table>";
      vhtml += "<p class=\"js-extra\" data-kind=\"hole\"" + (cell.useHole ? "" : " hidden") + ">Cell " +
        (index + 1) + " courtyard vertices (m)</p>";
      vhtml += "<table class=\"js-extra\" data-kind=\"hole\"" + (cell.useHole ? "" : " hidden") +
        "><thead><tr><th>x</th><th>y</th></tr></thead><tbody id=\"" + p + "hole-vertices\">";
      (cell.hole || []).forEach(function (pt, i) {
        vhtml += "<tr><td><input name=\"" + p + "hole-x-" + i + "\" value=\"" + esc(pt.x) +
          "\"></td><td><input name=\"" + p + "hole-y-" + i + "\" value=\"" + esc(pt.y) + "\"></td></tr>";
      });
      vhtml += "</tbody></table>";
      (cell.extraHoles || []).forEach(function (ring, hi) {
        var hn = hi + 1;
        vhtml += "<p class=\"js-extra\" data-kind=\"hole\"" + (cell.useHole ? "" : " hidden") + ">Cell " +
          (index + 1) + " courtyard " + (hn + 1) + " vertices (m)</p>";
        vhtml += "<table class=\"js-extra\" data-kind=\"hole\"" + (cell.useHole ? "" : " hidden") +
          "><thead><tr><th>x</th><th>y</th></tr></thead><tbody>";
        ring.forEach(function (pt, i) {
          vhtml += "<tr><td><input name=\"" + p + "hole-" + hn + "-x-" + i + "\" value=\"" + esc(pt.x) +
            "\"></td><td><input name=\"" + p + "hole-" + hn + "-y-" + i + "\" value=\"" + esc(pt.y) +
            "\"></td></tr>";
        });
        vhtml += "</tbody></table>";
      });
    });
    root.innerHTML = html;
    if (vertex) {
      vertex.innerHTML = vhtml;
    }
    var dormerBox = form.querySelector("#dormer-tables");
    if (dormerBox) {
      var dhtml = "";
      editor.dormers().forEach(function (dormer, index) {
        var dp = "dormer-" + index + "-";
        dhtml += "<section class=\"cell-card\"><h3>Dormer " + (index + 1) + "</h3>";
        dhtml += "<input type=\"hidden\" name=\"" + dp + "cell\" value=\"" + esc(dormer.cell) + "\">";
        dormer.vertices.forEach(function (pt, i) {
          dhtml += "<input type=\"hidden\" name=\"" + dp + "x-" + i + "\" value=\"" + esc(pt.x) + "\">";
          dhtml += "<input type=\"hidden\" name=\"" + dp + "y-" + i + "\" value=\"" + esc(pt.y) + "\">";
        });
        (dormer.pitches || []).forEach(function (pitch, i) {
          var kind = (dormer.types && dormer.types[i]) || "hip";
          dhtml += "<p><span>Dormer wall " + (i + 1) + "</span> ";
          dhtml += "<label><input type=\"radio\" name=\"" + dp + "type-" + i + "\" value=\"hip\"" +
            (kind === "hip" ? " checked" : "") + "> Hip</label> ";
          dhtml += "<label><input type=\"radio\" name=\"" + dp + "type-" + i + "\" value=\"gable\"" +
            (kind === "gable" ? " checked" : "") + "> Gable</label> ";
          dhtml += "<label>Pitch <input name=\"" + dp + "pitch-" + i + "\" value=\"" + esc(pitch) + "\"" +
            (kind === "gable" ? " disabled" : "") + "></label></p>";
        });
        dhtml += "</section>";
      });
      dormerBox.innerHTML = dhtml;
    }
  }

  function highlightWalls(form, editor) {
    var cell = editor.selectedCell();
    var edge = editor.selectedEdge();
    form.querySelectorAll(".wall").forEach(function (el) {
      var c = parseInt(el.getAttribute("data-cell") || el.closest(".cell-card").getAttribute("data-cell"), 10);
      var w = parseInt(el.getAttribute("data-wall"), 10);
      if (c === cell && w === edge) {
        el.classList.add("is-selected");
      } else {
        el.classList.remove("is-selected");
      }
    });
  }

  function mount(svg, form) {
    if (!svg || !form) {
      return null;
    }
    var apply = form.querySelector("[name=set_pitch]");
    var editor = createEditor({ applyToAll: apply ? apply.value : "45" });
    editor.loadForm(form);

    function commit(rebuild) {
      if (rebuild) {
        writeForm(form, editor);
      }
      drawSvg(svg, editor);
      highlightWalls(form, editor);
      var onWall = form.querySelector("#add-cell-on-wall");
      var addVert = form.querySelector("#add-vertex");
      var disabled = editor.selectedEdge() === null;
      if (onWall) { onWall.disabled = disabled; }
      if (addVert) { addVert.disabled = disabled; }
      var hint = form.querySelector("#wall-action-hint");
      if (hint) {
        hint.textContent = disabled
          ? "Select a wall on the building plan to attach a cell or split a vertex."
          : "A wall is selected. Add a cell on it, or add a vertex at its midpoint.";
      }
      var selected = form.querySelector("[name=selected_cell]");
      if (selected) {
        var cell = editor.selectedCell();
        selected.value = cell >= 0 ? String(cell) : "";
      }
    }

    drawSvg(svg, editor);
    highlightWalls(form, editor);
    commit(false);

    editor.applyFields = function (map) {
      editor.loadFields(map);
      commit(true);
    };

    var dragging = null;

    svg.addEventListener("pointerdown", function (event) {
      var metres = metresFromEvent(svg, event);
      editor.clickPlan(metres.x, metres.y);
      if (editor.selectedDormer() >= 0 && editor.selectedDormerVertex() !== null) {
        dragging = { dormer: editor.selectedDormer(), vertex: editor.selectedDormerVertex() };
        svg.setPointerCapture(event.pointerId);
      } else if (editor.selectedVertex() !== null) {
        dragging = { cell: editor.selectedCell(), vertex: editor.selectedVertex() };
        svg.setPointerCapture(event.pointerId);
      }
      commit(false);
    });
    svg.addEventListener("pointermove", function (event) {
      if (!dragging) { return; }
      var metres = metresFromEvent(svg, event);
      if (dragging.dormer !== undefined) {
        editor.moveDormerVertex(dragging.dormer, dragging.vertex, metres.x, metres.y);
        var dxName = "dormer-" + dragging.dormer + "-x-" + dragging.vertex;
        var dyName = "dormer-" + dragging.dormer + "-y-" + dragging.vertex;
        var dxIn = form.querySelector("[name='" + dxName + "']");
        var dyIn = form.querySelector("[name='" + dyName + "']");
        if (dxIn) { dxIn.value = String(metres.x); }
        if (dyIn) { dyIn.value = String(metres.y); }
        drawSvg(svg, editor);
        return;
      }
      editor.moveVertex(dragging.cell, dragging.vertex, metres.x, metres.y);
      var p = prefixOf(dragging.cell);
      var cell = editor.cells()[dragging.cell];
      var n = cell ? cell.vertices.length : 0;
      var xName = dragging.vertex < n ? p + "outer-x-" + dragging.vertex : p + "hole-x-" + (dragging.vertex - n);
      var yName = dragging.vertex < n ? p + "outer-y-" + dragging.vertex : p + "hole-y-" + (dragging.vertex - n);
      var xIn = form.querySelector("[name='" + xName + "']");
      var yIn = form.querySelector("[name='" + yName + "']");
      if (xIn) { xIn.value = String(metres.x); }
      if (yIn) { yIn.value = String(metres.y); }
      drawSvg(svg, editor);
    });
    svg.addEventListener("pointerup", function () {
      dragging = null;
    });

    var addDetached = form.querySelector("#add-detached-cell");
    var onWall = form.querySelector("#add-cell-on-wall");
    var addVert = form.querySelector("#add-vertex");
    if (addDetached) {
      addDetached.addEventListener("click", function () {
        editor.applyForm(form);
        editor.addDetachedCell();
        commit(true);
      });
    }
    if (onWall) {
      onWall.addEventListener("click", function () {
        editor.applyForm(form);
        editor.addCellOnSelectedWall();
        commit(true);
      });
    }
    if (addVert) {
      addVert.addEventListener("click", function () {
        editor.applyForm(form);
        editor.addVertexOnSelectedWall();
        commit(true);
      });
    }
    var del = form.querySelector("#delete-cell");
    if (del) {
      del.addEventListener("click", function () {
        editor.deleteCell();
        commit(true);
      });
    }
    var setPitchBtn = form.querySelector("#set-pitch");
    if (setPitchBtn) {
      setPitchBtn.addEventListener("click", function () {
        var input = form.querySelector("[name=set_pitch]");
        editor.setPitchOnSloping(input ? input.value : "45");
        commit(true);
      });
    }
    var edit = form.querySelector("#edit-coordinates");
    if (edit) {
      edit.addEventListener("change", function () {
        var box = form.querySelector("#vertex-editor");
        if (box) { box.hidden = !edit.checked; }
      });
    }

    form.addEventListener("change", function (event) {
      var el = event.target;
      if (!el || !el.name) { return; }
      if (el.name.indexOf("type-") !== -1 && el.type === "radio" && el.checked) {
        var match = el.name.match(/^(?:cell-(\d+)-)?type-(\d+)$/);
        if (match) {
          var ci = match[1] ? parseInt(match[1], 10) : 0;
          var wi = parseInt(match[2], 10);
          var cell = editor.cells()[ci];
          if (cell) {
            var outerN = cell.vertices.length;
            var ring = wi < outerN ? cell.vertices : cell.hole;
            var local = wi < outerN ? wi : wi - outerN;
            if (ring && ring.length) {
              var a = ring[local];
              var b = ring[(local + 1) % ring.length];
              editor.clickPlan((a.x + b.x) / 2, (a.y + b.y) / 2);
            }
          }
          editor.setWallType(el.value);
          commit(true);
        }
        return;
      }
      if (el.dataset && el.dataset.extra === "hole") {
        var card = el.closest(".cell-card");
        var idx = card ? parseInt(card.getAttribute("data-cell"), 10) : 0;
        var target = editor.cells()[idx];
        if (target && target.vertices.length) {
          editor.clickPlan(target.vertices[0].x, target.vertices[0].y);
        }
        editor.setUseHole(el.checked);
        commit(true);
        return;
      }
      if (el.dataset && el.dataset.extra === "overhang") {
        var cardO = el.closest(".cell-card");
        var idxO = cardO ? parseInt(cardO.getAttribute("data-cell"), 10) : 0;
        if (editor.cells()[idxO]) {
          editor.cells()[idxO].useOverhang = el.checked;
          if (el.checked && (!editor.cells()[idxO].overhang || editor.cells()[idxO].overhang === "0")) {
            editor.cells()[idxO].overhang = "0.5";
          }
        }
        commit(true);
        return;
      }
      if (el.dataset && el.dataset.extra === "eave") {
        var cardE = el.closest(".cell-card");
        var idxE = cardE ? parseInt(cardE.getAttribute("data-cell"), 10) : 0;
        if (editor.cells()[idxE]) {
          editor.cells()[idxE].useEave = el.checked;
        }
        commit(true);
      }
    });

    form.addEventListener("input", function (event) {
      var input = event.target;
      if (!input || !input.name) { return; }
      var vm = input.name.match(/^(?:cell-(\d+)-)?outer-([xy])-(\d+)$/);
      if (!vm) { return; }
      var cellIndex = vm[1] ? parseInt(vm[1], 10) : 0;
      var axis = vm[2];
      var vertex = parseInt(vm[3], 10);
      var ring = editor.rings()[cellIndex];
      if (!ring || !ring[vertex]) { return; }
      var parsed = parseFloat(input.value);
      if (Number.isNaN(parsed)) { return; }
      var x = ring[vertex][0];
      var y = ring[vertex][1];
      if (axis === "x") { x = parsed; } else { y = parsed; }
      editor.moveVertex(cellIndex, vertex, x, y);
      drawSvg(svg, editor);
    });

    form.addEventListener("submit", function () {
      form.querySelectorAll("input[name*='pitch-']").forEach(function (input) {
        input.disabled = false;
      });
    });

    return editor;
  }

  return { createEditor: createEditor, mount: mount };
});

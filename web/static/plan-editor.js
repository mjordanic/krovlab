(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.KrovlabPlanEditor = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function esc(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function createEditor(options) {
    options = options || {};
    var applyToAll = options.applyToAll || "45";
    var cells = [];
    var draft = [];
    var drawing = false;
    var selectedCell = -1;
    var selectedEdge = null;

    function pointInRing(x, y, vertices) {
      var inside = false;
      var n = vertices.length;
      var j = n - 1;
      var i;
      for (i = 0; i < n; i += 1) {
        var a = vertices[i];
        var b = vertices[j];
        if (a.y > y !== b.y > y &&
            x < ((b.x - a.x) * (y - a.y)) / (b.y - a.y) + a.x) {
          inside = !inside;
        }
        j = i;
      }
      return inside;
    }

    function distToSegment(x, y, a, b) {
      var dx = b.x - a.x;
      var dy = b.y - a.y;
      var len2 = dx * dx + dy * dy;
      if (len2 === 0) {
        dx = x - a.x;
        dy = y - a.y;
        return Math.sqrt(dx * dx + dy * dy);
      }
      var t = ((x - a.x) * dx + (y - a.y) * dy) / len2;
      if (t < 0) {
        t = 0;
      } else if (t > 1) {
        t = 1;
      }
      var px = a.x + t * dx;
      var py = a.y + t * dy;
      dx = x - px;
      dy = y - py;
      return Math.sqrt(dx * dx + dy * dy);
    }

    function hitEdge(x, y) {
      var best = null;
      var bestDist = 0.35;
      var c;
      var i;
      for (c = 0; c < cells.length; c += 1) {
        var verts = cells[c].vertices;
        for (i = 0; i < verts.length; i += 1) {
          var d = distToSegment(x, y, verts[i], verts[(i + 1) % verts.length]);
          if (d <= bestDist) {
            bestDist = d;
            best = { cell: c, edge: i };
          }
        }
      }
      return best;
    }

    function clickPlan(x, y) {
      if (drawing || draft.length > 0 || cells.length === 0) {
        if (draft.length >= 3) {
          var first = draft[0];
          var dx = x - first.x;
          var dy = y - first.y;
          if (Math.sqrt(dx * dx + dy * dy) <= 0.35) {
            closeRing();
            return;
          }
        }
        draft.push({ x: x, y: y });
        drawing = true;
        return;
      }
      var edge = hitEdge(x, y);
      if (edge) {
        selectedCell = edge.cell;
        selectedEdge = edge.edge;
        return;
      }
      var i;
      for (i = cells.length - 1; i >= 0; i -= 1) {
        if (pointInRing(x, y, cells[i].vertices)) {
          selectedCell = i;
          selectedEdge = null;
          return;
        }
      }
    }

    function addCell() {
      drawing = true;
      draft = [];
      selectedCell = -1;
      selectedEdge = null;
    }

    function setEaveHeight(height) {
      if (selectedCell < 0) {
        return;
      }
      cells[selectedCell].eaveHeight = String(height);
    }

    function setPitch(pitch) {
      if (selectedCell < 0 || selectedEdge === null) {
        return;
      }
      var cell = cells[selectedCell];
      cell.pitches[selectedEdge] = String(pitch);
      cell.gables[selectedEdge] = false;
    }

    function setGable(on) {
      if (selectedCell < 0 || selectedEdge === null) {
        return;
      }
      var cell = cells[selectedCell];
      cell.gables[selectedEdge] = !!on;
      if (on) {
        cell.pitches[selectedEdge] = "90";
        cell.knees[selectedEdge] = "0";
      }
    }

    function setKneeHeight(height) {
      if (selectedCell < 0 || selectedEdge === null) {
        return;
      }
      var cell = cells[selectedCell];
      cell.knees[selectedEdge] = String(height);
      if (parseFloat(String(height)) > 0) {
        cell.gables[selectedEdge] = false;
      }
    }

    function moveVertex(cellIndex, vertexIndex, x, y) {
      var cell = cells[cellIndex];
      if (!cell || vertexIndex < 0 || vertexIndex >= cell.vertices.length) {
        return;
      }
      cell.vertices[vertexIndex] = { x: x, y: y };
    }

    function deleteCell() {
      if (draft.length || drawing) {
        draft = [];
        drawing = false;
        if (cells.length) {
          selectedCell = 0;
        }
        selectedEdge = null;
        return;
      }
      if (selectedCell < 0) {
        return;
      }
      cells.splice(selectedCell, 1);
      if (cells.length === 0) {
        selectedCell = -1;
      } else if (selectedCell >= cells.length) {
        selectedCell = cells.length - 1;
      }
      selectedEdge = null;
      drawing = false;
      draft = [];
    }

    function closeRing() {
      if (draft.length < 3) {
        return;
      }
      cells.push({
        vertices: draft.slice(),
        pitches: draft.map(function () {
          return applyToAll;
        }),
        gables: draft.map(function () {
          return false;
        }),
        knees: draft.map(function () {
          return "0";
        }),
        overhang: "0",
        eaveHeight: "0",
        hole: [],
      });
      selectedCell = cells.length - 1;
      selectedEdge = null;
      draft = [];
      drawing = false;
    }

    function prefix(index) {
      return index === 0 ? "" : "cell-" + index + "-";
    }

    function fields() {
      var out = {};
      if (cells.length) {
        out.edit_vertices = "on";
      }
      cells.forEach(function (cell, index) {
        var p = prefix(index);
        cell.vertices.forEach(function (pt, i) {
          out[p + "outer-x-" + i] = String(pt.x);
          out[p + "outer-y-" + i] = String(pt.y);
        });
        cell.pitches.forEach(function (pitch, i) {
          out[p + "pitch-" + i] = String(pitch);
        });
        cell.gables.forEach(function (gable, i) {
          if (gable) {
            out[p + "gable-" + i] = "on";
          }
        });
        (cell.knees || []).forEach(function (knee, i) {
          if (knee !== "" && knee != null) {
            out[p + "knee-" + i] = String(knee);
          }
        });
        out[p + "overhang"] = cell.overhang;
        out[p + "eave_height"] = cell.eaveHeight;
        (cell.hole || []).forEach(function (pt, i) {
          out[p + "hole-x-" + i] = String(pt.x);
          out[p + "hole-y-" + i] = String(pt.y);
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

    function readRingFromMap(map, pfx, kind) {
      var pts = [];
      var i = 0;
      var key = prefixName(pfx, kind + "-x-");
      while (Object.prototype.hasOwnProperty.call(map, key + i)) {
        var xs = map[key + i];
        var ys = map[prefixName(pfx, kind + "-y-" + i)];
        if (xs !== "" && ys !== "" && xs != null && ys != null &&
            !Number.isNaN(parseFloat(String(xs))) &&
            !Number.isNaN(parseFloat(String(ys)))) {
          pts.push({ x: parseFloat(String(xs)), y: parseFloat(String(ys)) });
        }
        i += 1;
      }
      return pts;
    }

    function prefixName(pfx, rest) {
      return pfx + rest;
    }

    function cellFromMap(map, pfx, vertices) {
      var pitches = [];
      var gables = [];
      var knees = [];
      var i;
      for (i = 0; i < vertices.length; i += 1) {
        var gable = map[pfx + "gable-" + i] === "on";
        gables.push(gable);
        var pitch = map[pfx + "pitch-" + i];
        pitches.push(gable ? "90" : (pitch ? String(pitch) : applyToAll));
        var knee = map[pfx + "knee-" + i];
        knees.push(knee != null && knee !== "" ? String(knee) : "0");
      }
      return {
        vertices: vertices,
        pitches: pitches,
        gables: gables,
        knees: knees,
        overhang: map[pfx + "overhang"] || "0",
        eaveHeight: map[pfx + "eave_height"] || "0",
        hole: readRingFromMap(map, pfx, "hole"),
      };
    }

    function loadFields(map) {
      cells = [];
      draft = [];
      drawing = false;
      selectedEdge = null;
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
      selectedCell = cells.length ? 0 : -1;
    }

    function loadForm(form) {
      var map = {};
      Array.prototype.forEach.call(form.querySelectorAll("[name]"), function (el) {
        if (el.type === "checkbox") {
          if (el.checked) {
            map[el.name] = "on";
          }
        } else if (el.name) {
          map[el.name] = el.value;
        }
      });
      var apply = form.querySelector("[name=apply_to_all]");
      if (apply && apply.value) {
        applyToAll = apply.value;
      }
      loadFields(map);
    }

    function fillTbody(tbody, pfx, kind, vertices) {
      if (!tbody) {
        return;
      }
      var html = "";
      vertices.forEach(function (pt, i) {
        html += "<tr><td><input name=\"" + pfx + kind + "-x-" + i + "\" value=\"" + esc(pt.x) + "\"></td>";
        html += "<td><input name=\"" + pfx + kind + "-y-" + i + "\" value=\"" + esc(pt.y) + "\"></td></tr>";
      });
      tbody.innerHTML = html;
    }

    function pitchRowsHtml(pfx, cell) {
      var html = "";
      cell.vertices.forEach(function (start, i) {
        var end = cell.vertices[(i + 1) % cell.vertices.length];
        var gable = cell.gables[i];
        html += "<p><label>" + i + ": (" + esc(start.x) + ", " + esc(start.y) + ") → (" + esc(end.x) + ", " + esc(end.y) + ")";
        html += " <input name=\"" + pfx + "pitch-" + i + "\" value=\"" + esc(cell.pitches[i] || applyToAll) + "\"";
        if (gable) {
          html += " disabled";
        }
        html += "></label> <label><input type=\"checkbox\" name=\"" + pfx + "gable-" + i + "\"";
        if (gable) {
          html += " checked";
        }
        html += "> Gable</label> <label>Knee <input name=\"" + pfx + "knee-" + i + "\" value=\"" + esc((cell.knees && cell.knees[i]) || "0") + "\"> m</label></p>";
      });
      return html;
    }

    function writeForm(form) {
      var edit = form.querySelector("[name=edit_vertices]");
      if (edit) {
        edit.checked = true;
      }
      var editorBox = form.querySelector("#vertex-editor");
      if (editorBox) {
        editorBox.hidden = false;
      }
      if (cells[0]) {
        fillTbody(form.querySelector("#outer-vertices"), "", "outer", cells[0].vertices);
        fillTbody(form.querySelector("#hole-vertices"), "", "hole", cells[0].hole || []);
        var pitchBox = form.querySelector("#pitch-rows");
        if (pitchBox) {
          pitchBox.innerHTML = pitchRowsHtml("", cells[0]);
        }
        var eave = form.querySelector("[name=eave_height]");
        if (eave) {
          eave.value = cells[0].eaveHeight;
        }
        var over = form.querySelector("[name=overhang]");
        if (over) {
          over.value = cells[0].overhang;
        }
      }
      var extra = form.querySelector("#extra-cells");
      if (extra) {
        var html = "";
        cells.forEach(function (cell, index) {
          if (index === 0) {
            return;
          }
          var p = prefix(index);
          html += "<div class=\"cell-block\" data-cell=\"" + index + "\">";
          html += "<p>Cell " + index + "</p>";
          html += "<p>Outer vertices (m)</p><table><thead><tr><th>x</th><th>y</th></tr></thead>";
          html += "<tbody id=\"" + p + "outer-vertices\"></tbody></table>";
          html += "<p>Hole vertices (m)</p><table><thead><tr><th>x</th><th>y</th></tr></thead>";
          html += "<tbody id=\"" + p + "hole-vertices\"></tbody></table>";
          html += "<div>" + pitchRowsHtml(p, cell) + "</div>";
          html += "<p><label>Overhang <input name=\"" + p + "overhang\" value=\"" + esc(cell.overhang) + "\"> m</label> ";
          html += "<label>Eave height <input name=\"" + p + "eave_height\" value=\"" + esc(cell.eaveHeight) + "\"> m</label></p></div>";
        });
        extra.innerHTML = html;
        cells.forEach(function (cell, index) {
          if (index === 0) {
            return;
          }
          var p = prefix(index);
          fillTbody(form.querySelector("#" + p + "outer-vertices"), p, "outer", cell.vertices);
          fillTbody(form.querySelector("#" + p + "hole-vertices"), p, "hole", cell.hole || []);
        });
      }
      if (draft.length) {
        var dp = prefix(cells.length);
        if (cells.length === 0) {
          fillTbody(form.querySelector("#outer-vertices"), "", "outer", draft);
        } else if (extra) {
          extra.insertAdjacentHTML(
            "beforeend",
            "<div class=\"cell-block\" data-cell=\"" + cells.length + "\"><p>Cell " + cells.length + "</p>" +
              "<p>Outer vertices (m)</p><table><thead><tr><th>x</th><th>y</th></tr></thead>" +
              "<tbody id=\"" + dp + "outer-vertices\"></tbody></table></div>"
          );
          fillTbody(form.querySelector("#" + dp + "outer-vertices"), dp, "outer", draft);
        }
      }
    }

    return {
      clickPlan: clickPlan,
      closeRing: closeRing,
      addCell: addCell,
      setEaveHeight: setEaveHeight,
      setPitch: setPitch,
      setGable: setGable,
      setKneeHeight: setKneeHeight,
      moveVertex: moveVertex,
      deleteCell: deleteCell,
      fields: fields,
      rings: rings,
      draft: function () {
        return draft.map(function (pt) {
          return [pt.x, pt.y];
        });
      },
      loadForm: loadForm,
      writeForm: writeForm,
      setApplyToAll: function (value) {
        applyToAll = value;
      },
      selectedCell: function () {
        return selectedCell;
      },
      selectedEdge: function () {
        return selectedEdge;
      },
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
    return {
      x: Math.round(loc.x * 100) / 100,
      y: Math.round(loc.y * 100) / 100,
    };
  }

  function collectPoints(editor) {
    var pts = [];
    editor.rings().forEach(function (ring) {
      ring.forEach(function (pt) {
        pts.push(pt);
      });
    });
    editor.draft().forEach(function (pt) {
      pts.push(pt);
    });
    return pts;
  }

  function drawSvg(svg, editor) {
    var pts = collectPoints(editor);
    var minX = 0;
    var minY = 0;
    var maxX = 10;
    var maxY = 6;
    if (pts.length) {
      minX = pts[0][0];
      minY = pts[0][1];
      maxX = pts[0][0];
      maxY = pts[0][1];
      pts.forEach(function (pt) {
        if (pt[0] < minX) { minX = pt[0]; }
        if (pt[1] < minY) { minY = pt[1]; }
        if (pt[0] > maxX) { maxX = pt[0]; }
        if (pt[1] > maxY) { maxY = pt[1]; }
      });
    }
    var pad = 1;
    minX -= pad;
    minY -= pad;
    maxX += pad;
    maxY += pad;
    var width = maxX - minX || 12;
    var height = maxY - minY || 8;
    svg.setAttribute("viewBox", minX + " " + (-maxY) + " " + width + " " + height);
    var html = "<g id=\"plan-metres\" transform=\"scale(1,-1)\">";
    editor.rings().forEach(function (ring, index) {
      html += "<polygon data-cell=\"" + index + "\" data-ring=\"" + ringAttr(ring) + "\" points=\"" + ringAttr(ring) + "\"></polygon>";
    });
    if (editor.draft().length) {
      html += "<polyline data-draft=\"1\" data-ring=\"" + ringAttr(editor.draft()) + "\" points=\"" + ringAttr(editor.draft()) + "\" fill=\"none\"></polyline>";
    }
    html += "</g>";
    svg.innerHTML = html;
  }

  function syncInspector(form, editor) {
    var eave = form.querySelector("#selected-eave-height");
    var pitch = form.querySelector("#selected-pitch");
    var gable = form.querySelector("#selected-gable");
    var knee = form.querySelector("#selected-knee-height");
    var cellIndex = editor.selectedCell();
    var data = editor.fields();
    var p = cellIndex <= 0 ? "" : "cell-" + cellIndex + "-";
    if (eave) {
      eave.value = cellIndex < 0 ? "" : (data[p + "eave_height"] || "");
    }
    var edge = editor.selectedEdge();
    if (pitch) {
      pitch.value = edge === null || cellIndex < 0 ? "" : (data[p + "pitch-" + edge] || "");
      pitch.disabled = !!(edge !== null && data[p + "gable-" + edge]);
    }
    if (gable) {
      gable.checked = !!(edge !== null && data[p + "gable-" + edge]);
    }
    if (knee) {
      knee.value = edge === null || cellIndex < 0 ? "" : (data[p + "knee-" + edge] || "0");
    }
  }

  function mount(svg, form) {
    if (!svg || !form) {
      return null;
    }
    var apply = form.querySelector("[name=apply_to_all]");
    var editor = createEditor({ applyToAll: apply ? apply.value : "45" });
    editor.loadForm(form);

    function commit() {
      editor.writeForm(form);
      drawSvg(svg, editor);
      syncInspector(form, editor);
    }

    drawSvg(svg, editor);
    syncInspector(form, editor);

    svg.addEventListener("click", function (event) {
      var metres = metresFromEvent(svg, event);
      editor.clickPlan(metres.x, metres.y);
      commit();
    });

    var closeBtn = form.querySelector("#close-ring");
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        editor.closeRing();
        commit();
      });
    }
    var deleteBtn = form.querySelector("#delete-cell");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", function () {
        editor.deleteCell();
        commit();
      });
    }
    var addBtn = form.querySelector("#add-cell");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        editor.addCell();
        commit();
      });
    }

    form.addEventListener("input", function (event) {
      var input = event.target;
      if (!input || !input.name && !input.id) {
        return;
      }
      if (input.id === "selected-eave-height") {
        editor.setEaveHeight(input.value);
        editor.writeForm(form);
        drawSvg(svg, editor);
        return;
      }
      if (input.id === "selected-pitch") {
        editor.setPitch(input.value);
        commit();
        return;
      }
      if (input.id === "selected-knee-height") {
        editor.setKneeHeight(input.value);
        commit();
        return;
      }
      if (input.name === "apply_to_all") {
        editor.setApplyToAll(input.value);
        return;
      }
      var match = input.name && input.name.match(/^(?:cell-(\d+)-)?outer-([xy])-(\d+)$/);
      if (!match) {
        return;
      }
      var cellIndex = match[1] ? parseInt(match[1], 10) : 0;
      var axis = match[2];
      var vertex = parseInt(match[3], 10);
      var ring = editor.rings()[cellIndex];
      if (!ring || !ring[vertex]) {
        editor.loadForm(form);
        drawSvg(svg, editor);
        return;
      }
      var x = ring[vertex][0];
      var y = ring[vertex][1];
      var parsed = parseFloat(input.value);
      if (Number.isNaN(parsed)) {
        return;
      }
      if (axis === "x") {
        x = parsed;
      } else {
        y = parsed;
      }
      editor.moveVertex(cellIndex, vertex, x, y);
      drawSvg(svg, editor);
    });

    form.addEventListener("change", function (event) {
      var box = event.target;
      if (box && box.id === "selected-gable") {
        editor.setGable(box.checked);
        commit();
      }
    });

    return editor;
  }

  return { createEditor: createEditor, mount: mount };
});

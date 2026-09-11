(function (root) {
  "use strict";

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
    return map;
  }

  function merge(base, patches) {
    var out = {};
    var key;
    for (key in base) {
      if (Object.prototype.hasOwnProperty.call(base, key)) {
        out[key] = base[key];
      }
    }
    for (key in patches) {
      if (!Object.prototype.hasOwnProperty.call(patches, key)) {
        continue;
      }
      if (patches[key] === "" || patches[key] == null) {
        delete out[key];
      } else {
        out[key] = String(patches[key]);
      }
    }
    return out;
  }

  function selectedOf(editor) {
    if (!editor || typeof editor.selectedCell !== "function") {
      return {};
    }
    var cell = editor.selectedCell();
    var wall = editor.selectedEdge();
    var out = {};
    if (cell >= 0) {
      out.cell = cell + 1;
    }
    if (wall !== null && wall >= 0) {
      out.wall = wall + 1;
    }
    return out;
  }

  function takeoffText(form) {
    var root = form.parentNode;
    var pre = root ? root.querySelector(".takeoff pre") : null;
    return pre ? pre.textContent || "" : "";
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function latexToPlain(inner) {
    return String(inner)
      .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "$1 / $2")
      .replace(/\\(?:text|mathrm|operatorname|textit|textbf)\{([^{}]*)\}/g, "$1")
      .replace(/\\[,;! ]/g, " ")
      .replace(/\\times\b/g, "*")
      .replace(/\\cdot\b/g, "*")
      .replace(/\\(cos|sin|tan|log|ln)\b/g, "$1")
      .replace(/\\(left|right)\b/g, "")
      .replace(/[{}\\]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function unwrapLatex(value) {
    return String(value)
      .replace(/\$\$([\s\S]+?)\$\$/g, function (_, inner) {
        return latexToPlain(inner);
      })
      .replace(/\\\[([\s\S]+?)\\\]/g, function (_, inner) {
        return latexToPlain(inner);
      })
      .replace(/\\\(([\s\S]+?)\\\)/g, function (_, inner) {
        return latexToPlain(inner);
      })
      .replace(/\$([\s\S]+?)\$/g, function (_, inner) {
        return latexToPlain(inner);
      });
  }

  function formatMessage(text) {
    var s = unwrapLatex(String(text || ""));
    s = escapeHtml(s);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\n\n+/g, "<br><br>");
    s = s.replace(/\n/g, "<br>");
    return s;
  }

  function appendLog(log, who, text) {
    var p = document.createElement("p");
    var label = document.createElement("span");
    var body = document.createElement("span");
    p.className = who;
    label.className = "who";
    label.textContent = who === "you" ? "You: " : "Help: ";
    body.className = "said";
    body.innerHTML = formatMessage(text);
    p.appendChild(label);
    p.appendChild(body);
    log.appendChild(p);
    log.scrollTop = log.scrollHeight;
  }

  function flashUpdate(form) {
    var button = form.querySelector("button[type='submit']");
    if (!button) {
      return;
    }
    button.classList.add("needs-update");
    window.setTimeout(function () {
      button.classList.remove("needs-update");
    }, 2400);
  }

  function mount(root, form, editor) {
    if (!root || !form) {
      return;
    }
    var toggle = root.querySelector("#need-help");
    var panel = root.querySelector("#help-panel");
    var log = root.querySelector("#help-log");
    var input = root.querySelector("#help-input");
    var send = root.querySelector("#help-send");
    var history = [];
    if (toggle && panel) {
      toggle.addEventListener("change", function () {
        panel.hidden = !toggle.checked;
        if (toggle.checked && input) {
          input.focus();
        }
      });
    }
    function submit() {
      var text = input ? String(input.value || "").trim() : "";
      if (!text) {
        return;
      }
      if (input) {
        input.value = "";
      }
      history.push({ role: "user", content: text });
      if (log) {
        appendLog(log, "you", text);
      }
      if (send) {
        send.disabled = true;
      }
      fetch("/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history,
          fields: formMap(form),
          describe: takeoffText(form),
          selected: selectedOf(editor)
        })
      }).then(function (res) {
        return res.json().then(function (body) {
          return { ok: res.ok, status: res.status, body: body };
        });
      }).then(function (result) {
        var body = result.body || {};
        var reply = body.reply || body.error || "Help could not answer.";
        if (!result.ok && body.error) {
          reply = body.error;
        }
        history.push({ role: "assistant", content: reply });
        if (log) {
          appendLog(log, "help", reply);
        }
        if (result.ok && body.fields && editor && typeof editor.applyFields === "function") {
          editor.applyFields(merge(formMap(form), body.fields));
          flashUpdate(form);
        }
      }).catch(function () {
        if (log) {
          appendLog(log, "help", "Help could not reach the server.");
        }
      }).then(function () {
        if (send) {
          send.disabled = false;
        }
      });
    }
    if (send) {
      send.addEventListener("click", function (event) {
        event.preventDefault();
        submit();
      });
    }
    if (input) {
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          submit();
        }
      });
    }
  }

  root.KrovlabHelp = { mount: mount, formatMessage: formatMessage };
})(typeof globalThis !== "undefined" ? globalThis : this);

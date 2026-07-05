import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "PromptMixerV2dAIly";
const MAX_ATTRIBUTES = 64;
const ATTR_PREFIX = "attr_";
const HIDDEN_WIDGET_TYPE = "daily-hidden";
const AUTOCOMPLETE_LIMIT = 12;

function attrSlot(index) {
  return `${ATTR_PREFIX}${String(index + 1).padStart(3, "0")}`;
}

function findWidget(node, name) {
  return node.widgets?.find((widget) => widget.name === name);
}

function parseSchema(widget) {
  try {
    const value = JSON.parse(widget?.value || "[]");
    if (!Array.isArray(value)) return [];
    return value
      .map((item) => (typeof item === "string" ? item : item?.name))
      .filter((name) => typeof name === "string" && name.trim())
      .slice(0, MAX_ATTRIBUTES);
  } catch {
    return [];
  }
}

function setSchemaWidget(node, columns) {
  const value = JSON.stringify(
    columns.slice(0, MAX_ATTRIBUTES).map((column, index) => ({
      slot: attrSlot(index),
      name: column.name,
      count: column.count ?? 0,
    }))
  );
  syncWidgetValue(node, "schema_json", value);
}

function hideWidget(node, widget, hidden) {
  if (!widget) return;
  if (!widget.__dailyOriginal) {
    widget.__dailyOriginal = {
      type: widget.type,
      computeSize: widget.computeSize,
      computedHeight: widget.computedHeight,
      label: widget.label,
      hidden: widget.hidden,
    };
  }

  if (hidden) {
    widget.hidden = true;
    widget.type = HIDDEN_WIDGET_TYPE;
    widget.computeSize = () => [0, -4];
    widget.computedHeight = 0;
  } else {
    widget.hidden = widget.__dailyOriginal.hidden;
    widget.type = widget.__dailyOriginal.type;
    widget.computeSize = widget.__dailyOriginal.computeSize;
    widget.computedHeight = widget.__dailyOriginal.computedHeight;
  }
}

function syncWidgetValue(node, widgetName, value) {
  const widget = findWidget(node, widgetName);
  if (!widget) return;
  widget.value = value;
  if (node.widgets_values) {
    const index = node.widgets.indexOf(widget);
    if (index >= 0) node.widgets_values[index] = value;
  }
}

function applyFixedLabels(node) {
  const labels = {
    csv_path: "CSV path",
    template: "Template",
    flat_mode: "Flat mode",
    show_attribute_outputs: "Attribute outputs",
    seed: "Seed",
    control_after_generate: "Seed control",
  };

  for (const [name, label] of Object.entries(labels)) {
    const widget = findWidget(node, name);
    if (widget) {
      widget.label = label;
    }
  }
}

function getAttributeNames(node) {
  return parseSchema(findWidget(node, "schema_json"));
}

function getTemplateAutocompleteContext(textarea) {
  const cursor = textarea.selectionStart ?? textarea.value.length;
  const beforeCursor = textarea.value.slice(0, cursor);
  const openIndex = beforeCursor.lastIndexOf("{");
  if (openIndex < 0) return null;

  const closeIndex = beforeCursor.lastIndexOf("}");
  if (closeIndex > openIndex) return null;

  const fragment = beforeCursor.slice(openIndex + 1);
  if (fragment.includes("\n")) return null;

  return { cursor, openIndex, fragment };
}

function positionAutocompletePopup(node, textarea, popup) {
  const rect = textarea.getBoundingClientRect();
  popup.style.left = `${Math.round(rect.left)}px`;
  popup.style.top = `${Math.round(rect.bottom + 4)}px`;
  popup.style.width = `${Math.round(rect.width)}px`;
  popup.style.zIndex = "100000";
}

function closeAutocomplete(node) {
  const state = node.__dailyTemplateAutocomplete;
  if (!state) return;
  state.visible = false;
  state.items = [];
  state.selectedIndex = 0;
  state.popup.style.display = "none";
}

function insertAutocompleteValue(node, value) {
  const state = node.__dailyTemplateAutocomplete;
  const textarea = state?.textarea;
  if (!textarea || !state.context) return;

  const before = textarea.value.slice(0, state.context.openIndex);
  const after = textarea.value.slice(state.context.cursor);
  const replacement = `{${value}}`;
  const newCursor = before.length + replacement.length;
  const nextValue = `${before}${replacement}${after}`;

  textarea.value = nextValue;
  syncWidgetValue(node, "template", nextValue);
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
  textarea.focus();
  textarea.setSelectionRange(newCursor, newCursor);
  closeAutocomplete(node);
}

function renderAutocomplete(node) {
  const state = node.__dailyTemplateAutocomplete;
  if (!state) return;

  state.popup.innerHTML = "";
  state.items.forEach((name, index) => {
    const item = document.createElement("button");
    item.type = "button";
    item.textContent = name;
    item.style.cssText = [
      "display:block",
      "width:100%",
      "border:0",
      "padding:5px 8px",
      "text-align:left",
      "font:12px sans-serif",
      "cursor:pointer",
      "color:var(--input-text,#ddd)",
      `background:${index === state.selectedIndex ? "var(--comfy-menu-bg,#444)" : "var(--comfy-input-bg,#222)"}`,
    ].join(";");
    item.addEventListener("mousedown", (event) => {
      event.preventDefault();
      insertAutocompleteValue(node, name);
    });
    state.popup.appendChild(item);
  });
}

function updateAutocomplete(node) {
  const state = node.__dailyTemplateAutocomplete;
  if (!state) return;

  const context = getTemplateAutocompleteContext(state.textarea);
  if (!context) {
    closeAutocomplete(node);
    return;
  }

  const query = context.fragment.trim().toLowerCase();
  const names = getAttributeNames(node);
  const matches = names
    .filter((name) => !query || name.toLowerCase().includes(query))
    .slice(0, AUTOCOMPLETE_LIMIT);

  if (!matches.length) {
    closeAutocomplete(node);
    return;
  }

  state.context = context;
  state.items = matches;
  state.selectedIndex = Math.min(state.selectedIndex, matches.length - 1);
  state.visible = true;
  positionAutocompletePopup(node, state.textarea, state.popup);
  state.popup.style.display = "block";
  renderAutocomplete(node);
}

function setupTemplateAutocomplete(node) {
  if (node.__dailyTemplateAutocomplete) return;

  const templateWidget = findWidget(node, "template");
  const textarea = templateWidget?.inputEl;
  if (!textarea) return;

  const popup = document.createElement("div");
  popup.style.cssText = [
    "position:fixed",
    "display:none",
    "max-height:180px",
    "overflow:auto",
    "border:1px solid var(--border-color,#555)",
    "border-radius:4px",
    "box-shadow:0 6px 18px rgba(0,0,0,.35)",
    "background:var(--comfy-input-bg,#222)",
  ].join(";");
  document.body.appendChild(popup);

  const state = {
    textarea,
    popup,
    visible: false,
    items: [],
    selectedIndex: 0,
    context: null,
    cleanups: [],
  };
  node.__dailyTemplateAutocomplete = state;

  const onInput = () => {
    state.selectedIndex = 0;
    updateAutocomplete(node);
  };
  const onKeydown = (event) => {
    if (!state.visible) {
      if (event.key === "{") {
        setTimeout(() => updateAutocomplete(node), 0);
      }
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      closeAutocomplete(node);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      state.selectedIndex = (state.selectedIndex + 1) % state.items.length;
      renderAutocomplete(node);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      state.selectedIndex = (state.selectedIndex + state.items.length - 1) % state.items.length;
      renderAutocomplete(node);
      return;
    }
    if (event.key === "Enter" || event.key === "Tab") {
      event.preventDefault();
      insertAutocompleteValue(node, state.items[state.selectedIndex]);
    }
  };
  const onBlur = () => setTimeout(() => closeAutocomplete(node), 150);
  const onScrollOrResize = () => {
    if (state.visible) {
      positionAutocompletePopup(node, textarea, popup);
    }
  };

  textarea.addEventListener("input", onInput);
  textarea.addEventListener("keydown", onKeydown);
  textarea.addEventListener("blur", onBlur);
  window.addEventListener("resize", onScrollOrResize);
  window.addEventListener("scroll", onScrollOrResize, true);

  state.cleanups.push(
    () => textarea.removeEventListener("input", onInput),
    () => textarea.removeEventListener("keydown", onKeydown),
    () => textarea.removeEventListener("blur", onBlur),
    () => window.removeEventListener("resize", onScrollOrResize),
    () => window.removeEventListener("scroll", onScrollOrResize, true),
    () => popup.remove()
  );
}

function cleanupTemplateAutocomplete(node) {
  const state = node.__dailyTemplateAutocomplete;
  if (!state) return;
  for (const cleanup of state.cleanups) {
    cleanup();
  }
  node.__dailyTemplateAutocomplete = null;
}

function removeOutputLinks(node, index) {
  const output = node.outputs?.[index];
  if (!output?.links?.length || !node.graph) return;
  for (const linkId of [...output.links]) {
    node.graph.removeLink(linkId);
  }
}

function rebuildOutputs(node, names, showAttributeOutputs) {
  if (!node.outputs?.length) {
    node.addOutput("PROMPT", "STRING");
  }

  const desired = ["PROMPT"];
  if (showAttributeOutputs) {
    desired.push("USED_JSON", ...names);
  }

  for (let index = node.outputs.length - 1; index >= desired.length; index -= 1) {
    removeOutputLinks(node, index);
    node.removeOutput(index);
  }

  for (let index = 0; index < desired.length; index += 1) {
    if (!node.outputs[index]) {
      node.addOutput(desired[index], "STRING");
    }

    if (index > 0 && node.outputs[index].name !== desired[index]) {
      removeOutputLinks(node, index);
    }

    node.outputs[index].name = desired[index];
    node.outputs[index].label = desired[index];
    node.outputs[index].type = "STRING";
  }
}

function ensureAttrInputCache(node) {
  if (node.__dailyAttrInputs) return;
  node.__dailyAttrInputs = new Map();
  for (const input of node.inputs || []) {
    if (input.name?.startsWith(ATTR_PREFIX)) {
      node.__dailyAttrInputs.set(input.name, input);
    }
  }
}

function restoreInputAtEnd(node, input) {
  if (!node.inputs) {
    node.inputs = [];
  }
  node.inputs.push(input);
  if (node.onInputAdded) {
    node.onInputAdded(input);
  }
  LiteGraph.registerNodeAndSlotType(node, input.type || 0);
  return input;
}

function syncAttrInputs(node, names) {
  ensureAttrInputCache(node);
  const desired = new Set(names.map((_, index) => attrSlot(index)));

  if (!node.inputs) return;
  for (let index = node.inputs.length - 1; index >= 0; index -= 1) {
    const input = node.inputs[index];
    if (input.name?.startsWith(ATTR_PREFIX) && !desired.has(input.name)) {
      node.removeInput(index);
    }
  }

  for (let index = 0; index < names.length; index += 1) {
    const slot = attrSlot(index);
    let input = node.inputs?.find((candidate) => candidate.name === slot);
    if (!input) {
      input = node.__dailyAttrInputs.get(slot) || {
        name: slot,
        type: "STRING",
        link: null,
      };
      restoreInputAtEnd(node, input);
    }
    input.label = names[index];
  }
}

function updateAttrWidgets(node, names) {
  for (let index = 0; index < MAX_ATTRIBUTES; index += 1) {
    const slot = attrSlot(index);
    const widget = findWidget(node, slot);
    const activeName = names[index];
    if (!widget) continue;

    if (activeName) {
      widget.label = activeName;
      hideWidget(node, widget, false);
    } else {
      widget.label = slot;
      hideWidget(node, widget, true);
    }
  }

  hideWidget(node, findWidget(node, "schema_json"), true);
}

function applySchema(node) {
  const names = parseSchema(findWidget(node, "schema_json"));
  const showOutputs = findWidget(node, "show_attribute_outputs")?.value !== false;

  applyFixedLabels(node);
  updateAttrWidgets(node, names);
  syncAttrInputs(node, names);
  rebuildOutputs(node, names, showOutputs);
  if (node.__dailyTemplateAutocomplete?.visible) {
    updateAutocomplete(node);
  }

  const computedSize = node.computeSize();
  node.setSize([
    Math.max(node.size?.[0] || 0, computedSize[0]),
    Math.max(node.size?.[1] || 0, computedSize[1]),
  ]);
  node.setDirtyCanvas(true, true);
  node.graph?.setDirtyCanvas(true, true);
}

async function refreshCsv(node) {
  const path = findWidget(node, "csv_path")?.value || "";
  if (!path.trim()) {
    alert("Set csv_path or use Choose CSV before refreshing.");
    return;
  }

  const response = await api.fetchApi(
    `/daily/prompt-mixer-v2/schema?path=${encodeURIComponent(path)}`,
    { cache: "no-store" }
  );
  const data = await response.json();
  if (!data.ok) {
    alert(data.error || "CSV not found or unreadable.");
    return;
  }

  syncWidgetValue(node, "csv_path", data.path);
  setSchemaWidget(node, data.columns || []);
  applySchema(node);
}

async function uploadCsv(node, file) {
  const body = new FormData();
  body.append("csv", file);

  const response = await api.fetchApi("/daily/prompt-mixer-v2/upload-csv", {
    method: "POST",
    body,
  });
  const data = await response.json();
  if (!data.ok) {
    alert(data.error || "CSV upload failed.");
    return;
  }

  syncWidgetValue(node, "csv_path", data.path);
  setSchemaWidget(node, data.columns || []);
  applySchema(node);
}

function addCsvPicker(node) {
  if (node.__dailyCsvPicker) return;

  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = ".csv,text/csv";
  fileInput.style.display = "none";
  fileInput.addEventListener("change", async () => {
    if (fileInput.files?.length) {
      await uploadCsv(node, fileInput.files[0]);
      fileInput.value = "";
    }
  });
  document.body.appendChild(fileInput);
  node.__dailyCsvPicker = fileInput;

  node.addWidget("button", "Choose CSV", null, () => fileInput.click());
  node.addWidget("button", "Refresh CSV", null, () => refreshCsv(node));

  const onRemoved = node.onRemoved;
  node.onRemoved = function () {
    fileInput.remove();
    return onRemoved?.apply(this, arguments);
  };
}

app.registerExtension({
  name: "daily.promptMixerV2",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated?.apply(this, arguments);

      addCsvPicker(this);
      setupTemplateAutocomplete(this);
      const showOutputsWidget = findWidget(this, "show_attribute_outputs");
      if (showOutputsWidget) {
        const callback = showOutputsWidget.callback;
        showOutputsWidget.callback = (...args) => {
          const callbackResult = callback?.apply(showOutputsWidget, args);
          applySchema(this);
          return callbackResult;
        };
      }

      setTimeout(() => applySchema(this), 0);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure?.apply(this, arguments);
      setTimeout(() => {
        setupTemplateAutocomplete(this);
        applySchema(this);
      }, 0);
      return result;
    };

    const onRemoved = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
      cleanupTemplateAutocomplete(this);
      return onRemoved?.apply(this, arguments);
    };
  },
});

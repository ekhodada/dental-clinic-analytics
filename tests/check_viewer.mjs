// I compare every supported selection with the original display fingerprints.
import fs from "node:fs";
import vm from "node:vm";
import crypto from "node:crypto";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const baseline = JSON.parse(fs.readFileSync(new URL("tests/viewer_baseline.json", root)));
const nodes = new Map();

// I provide the small part of the document used by the viewer.
function node(id) {
  if (!nodes.has(id)) {
    nodes.set(id, {
      value: id === "year" ? "2025" : "all",
      innerHTML: "",
      textContent: "",
      add() {},
      addEventListener() {},
    });
  }
  return nodes.get(id);
}

// I fingerprint visible output without retaining a second copy of its HTML.
function fingerprint(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

const context = vm.createContext({
  window: {},
  document: { getElementById: node, querySelectorAll: () => [] },
  Option: function () {},
  console,
});
vm.runInContext(fs.readFileSync(new URL("dashboard/data.js", root), "utf8"), context);
vm.runInContext(fs.readFileSync(new URL("dashboard/app.js", root), "utf8"), context);

for (const [key, expected] of Object.entries(baseline)) {
  const [year, month, location] = key.split("|");
  node("year").value = year;
  node("month").value = month;
  node("location").value = location;
  for (const page of ["overview", "trends", "finance"]) {
    vm.runInContext(`page=${JSON.stringify(page)};category=0;render()`, context);
    for (const part of ["metrics", "content"]) {
      assert.equal(fingerprint(node(part).innerHTML), expected[page][part], `${key} ${page} ${part}`);
    }
    if (page === "overview") {
      for (let category = 0; category < 6; category++) {
        vm.runInContext(`category=${category};renderCategory(getState())`, context);
        assert.equal(fingerprint(node("care-panel").innerHTML), expected.categories[category]);
      }
    }
    if (page === "finance") {
      const csvRows = vm.runInContext("JSON.stringify(latestExport)", context);
      assert.equal(fingerprint(csvRows), expected.weekly, `${key} weekly export`);
    }
  }
}
console.log("PASS: 156 selections, six care categories and every weekly export match.");

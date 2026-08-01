### Task 7: lib/sparkline.js — inline SVG sparklines

**Files:**
- Create: `lib/sparkline.js`

**Interfaces:**
- Produces: `NFOD.sparkline.render(container, values, color)` — draws a ~64×16 SVG polyline; `values` = numeric array; `color` = CSS color; returns the SVG element.

- [ ] **Step 1: Write sparkline.js**

```js
window.NFOD = window.NFOD || {};
NFOD.sparkline = (function () {
  function render(container, values, color) {
    const W = 64, H = 16, P = 2;
    container.innerHTML = "";
    if (!values || values.length < 2) {
      const empty = document.createElement("span");
      empty.className = "sparkline-empty";
      empty.textContent = "·";
      container.appendChild(empty);
      return empty;
    }
    const min = Math.min(...values), max = Math.max(...values);
    const span = max - min || 1;
    const step = (W - 2 * P) / (values.length - 1);
    const pts = values.map((v, i) => {
      const x = P + i * step;
      const y = H - P - ((v - min) / span) * (H - 2 * P);
      return x.toFixed(1) + "," + y.toFixed(1);
    });
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("width", W); svg.setAttribute("height", H);
    svg.setAttribute("class", "sparkline");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    const poly = document.createElementNS(svgNS, "polyline");
    poly.setAttribute("points", pts.join(" "));
    poly.setAttribute("fill", "none");
    poly.setAttribute("stroke", color);
    poly.setAttribute("stroke-width", "1.5");
    poly.setAttribute("stroke-linecap", "round");
    poly.setAttribute("stroke-linejoin", "round");
    svg.appendChild(poly);
    container.appendChild(svg);
    return svg;
  }
  return { render };
})();
```

- [ ] **Step 2: Verify**

In a scratch page: `NFOD.sparkline.render(document.body, [1,5,3,8,2], "#34d399")` draws a 5-point polyline; `[1,1,1]` renders flat (no divide-by-zero); `[1]` renders the empty dot.

- [ ] **Step 3: Commit**

```bash
git add lib/sparkline.js
git commit -m "feat(sparkline): tiny inline SVG trend renderer"
```

---


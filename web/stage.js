/* Narthex stage renderer — absolute widgets + WS */
(function () {
  const stageEl = document.getElementById("stage");
  let style = {};
  let stage = { width: 1000, height: 1000 };
  let clockTimers = [];

  function clearClocks() {
    clockTimers.forEach(clearInterval);
    clockTimers = [];
  }

  function scaleBox(w) {
    const sw = stageEl.clientWidth;
    const sh = stageEl.clientHeight;
    const sx = sw / stage.width;
    const sy = sh / stage.height;
    const s = Math.min(sx, sy);
    const ox = (sw - stage.width * s) / 2;
    const oy = (sh - stage.height * s) / 2;
    return {
      left: ox + w.x * s,
      top: oy + w.y * s,
      width: w.w * s,
      height: w.h * s,
      zIndex: w.z || 0,
    };
  }

  function renderClock(el) {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    el.textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  }

  function renderDate(el) {
    el.textContent = new Date().toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
  }

  function renderScene(scene) {
    clearClocks();
    stageEl.innerHTML = "";
    const widgets = (scene.widgets || []).slice().sort((a, b) => (a.z || 0) - (b.z || 0));
    for (const w of widgets) {
      const el = document.createElement("div");
      el.className = `widget widget-${w.type}`;
      if (w.effect) el.classList.add(`effect-${w.effect}`);
      el.dataset.id = w.id;
      const box = scaleBox(w);
      Object.assign(el.style, {
        left: box.left + "px",
        top: box.top + "px",
        width: box.width + "px",
        height: box.height + "px",
        zIndex: String(box.zIndex),
      });
      if (w.type === "clock") {
        renderClock(el);
        clockTimers.push(setInterval(() => renderClock(el), 1000));
      } else if (w.type === "text") {
        if ((w.props || {}).role === "date") renderDate(el);
        else el.textContent = (w.props || {}).content || "";
      } else if (w.type === "gold_node") {
        el.title = "Hermes";
      } else if (w.type === "voice_stage") {
        const p = w.props || {};
        if (p.visible) el.classList.add("visible");
        el.innerHTML = `
          <div class="voice-state">${p.state || ""}</div>
          <div class="voice-user">${p.user_text || p.partial || ""}</div>
          <div class="voice-assistant">${p.assistant_text || ""}</div>
        `;
      } else {
        el.textContent = w.type;
      }
      stageEl.appendChild(el);
    }
  }

  function applyState(data) {
    if (data.style) {
      style = data.style;
      if (style.void) {
        document.body.style.background = style.void;
        stageEl.style.background = style.void;
      }
    }
    if (data.stage) stage = data.stage;
    if (data.scene) renderScene(data.scene);
  }

  async function refresh() {
    try {
      const r = await fetch("/api/state");
      applyState(await r.json());
    } catch (e) {
      console.error(e);
    }
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.topic === "hello" || msg.topic === "scene" || msg.scene) applyState(msg);
      } catch (e) {
        console.error(e);
      }
    };
    ws.onclose = () => setTimeout(connectWs, 2000);
    ws.onopen = () => {
      /* keep-alive pings */
      setInterval(() => {
        if (ws.readyState === 1) ws.send("ping");
      }, 25000);
    };
  }

  window.addEventListener("resize", refresh);
  refresh();
  connectWs();
  setInterval(refresh, 15000);
})();

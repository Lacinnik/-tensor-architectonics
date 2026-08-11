const canvas = document.getElementById("scene");
const context = canvas.getContext("2d", { alpha: false });
const ui = Object.fromEntries(["stereo", "motion", "enter-xr", "reset-view", "mode", "notice"].map(id => [id, document.getElementById(id)]));
const state = { yaw: 0, pitch: 0, zoom: 1, stereo: false, motion: false, dragging: false, lastX: 0, lastY: 0, alpha: 0, beta: 0, gamma: 0, xr: null };

let seed = 0x51f15e;
const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);
const points = Array.from({ length: 720 }, (_, index) => {
  const arm = index % 5;
  const radius = .12 + Math.pow(random(), .62) * 2.8;
  const angle = arm * Math.PI * .4 + radius * 2.25 + (random() - .5) * .75;
  return { x: Math.cos(angle) * radius, y: (random() - .5) * .52 * (1 - radius / 4), z: Math.sin(angle) * radius, light: .35 + random() * .65 };
});

function resize() {
  const ratio = Math.min(2, devicePixelRatio || 1);
  canvas.width = Math.round(innerWidth * ratio); canvas.height = Math.round(innerHeight * ratio);
  canvas.style.width = `${innerWidth}px`; canvas.style.height = `${innerHeight}px`;
}

function project(point, eye = 0) {
  const yaw = state.yaw + (state.motion ? state.alpha * .004 : 0);
  const pitch = state.pitch + (state.motion ? state.beta * .003 : 0);
  const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  const x1 = point.x * cy - point.z * sy - eye;
  const z1 = point.x * sy + point.z * cy;
  const y1 = point.y * cp - z1 * sp;
  const z2 = point.y * sp + z1 * cp + 4.2 / state.zoom;
  const scale = Math.min(canvas.width, canvas.height) * .31 / Math.max(.25, z2);
  return { x: x1 * scale, y: y1 * scale, z: z2, light: point.light };
}

function drawView(left, width, eye) {
  context.save(); context.beginPath(); context.rect(left, 0, width, canvas.height); context.clip();
  const cx = left + width / 2, cy = canvas.height / 2;
  const projected = points.map(point => project(point, eye)).sort((a, b) => b.z - a.z);
  for (const point of projected) {
    const alpha = Math.max(.12, Math.min(.95, point.light * (5.4 - point.z) / 4));
    context.fillStyle = `rgba(${point.light > .87 ? "255,211,106" : "116,218,255"},${alpha})`;
    const size = Math.max(.7, 4.6 / point.z) * devicePixelRatio;
    context.beginPath(); context.arc(cx + point.x, cy + point.y, size, 0, Math.PI * 2); context.fill();
  }
  const glow = context.createRadialGradient(cx, cy, 0, cx, cy, 80 * devicePixelRatio);
  glow.addColorStop(0, "rgba(255,255,255,.95)"); glow.addColorStop(.15, "rgba(104,240,210,.52)"); glow.addColorStop(1, "rgba(104,240,210,0)");
  context.fillStyle = glow; context.fillRect(cx - 90 * devicePixelRatio, cy - 90 * devicePixelRatio, 180 * devicePixelRatio, 180 * devicePixelRatio);
  context.restore();
}

function frame() {
  context.fillStyle = "#02050d"; context.fillRect(0, 0, canvas.width, canvas.height);
  if (state.stereo) {
    drawView(0, canvas.width / 2, -.035); drawView(canvas.width / 2, canvas.width / 2, .035);
    context.fillStyle = "#182c40"; context.fillRect(canvas.width / 2 - 1, 0, 2, canvas.height);
  } else drawView(0, canvas.width, 0);
  requestAnimationFrame(frame);
}

function setMode() { ui.mode.textContent = state.xr ? "WEBXR" : state.stereo ? "STEREO" : state.motion ? "MOTION" : "MONO"; }
ui.stereo.addEventListener("click", () => { state.stereo = !state.stereo; ui.stereo.classList.toggle("active", state.stereo); setMode(); });
ui.motion.addEventListener("click", async () => {
  try {
    if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") await DeviceOrientationEvent.requestPermission();
    state.motion = !state.motion; ui.motion.classList.toggle("active", state.motion); setMode();
  } catch { ui.notice.textContent = "Доступ к датчикам не предоставлен. Q=null."; }
});
addEventListener("deviceorientation", event => { state.alpha = event.alpha || 0; state.beta = event.beta || 0; state.gamma = event.gamma || 0; }, true);
ui["reset-view"].addEventListener("click", () => Object.assign(state, { yaw: 0, pitch: 0, zoom: 1 }));
canvas.addEventListener("pointerdown", event => { state.dragging = true; state.lastX = event.clientX; state.lastY = event.clientY; canvas.setPointerCapture(event.pointerId); });
canvas.addEventListener("pointermove", event => { if (!state.dragging) return; state.yaw += (event.clientX - state.lastX) * .006; state.pitch = Math.max(-1.1, Math.min(1.1, state.pitch + (event.clientY - state.lastY) * .006)); state.lastX = event.clientX; state.lastY = event.clientY; });
canvas.addEventListener("pointerup", () => { state.dragging = false; });
canvas.addEventListener("wheel", event => { state.zoom = Math.max(.55, Math.min(2.2, state.zoom * Math.exp(-event.deltaY * .001))); }, { passive: true });

function compileShader(gl, type, source) {
  const shader = gl.createShader(type); gl.shaderSource(shader, source); gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
  return shader;
}

async function startXr() {
  const xrCanvas = document.createElement("canvas");
  const gl = xrCanvas.getContext("webgl", { alpha: false, antialias: true, xrCompatible: true });
  if (!gl) throw new Error("WebGL недоступен");
  await gl.makeXRCompatible?.();
  const program = gl.createProgram();
  gl.attachShader(program, compileShader(gl, gl.VERTEX_SHADER, `
    attribute vec3 p; uniform mat4 projection; uniform mat4 view;
    void main(){ gl_Position=projection*view*vec4(p.x*0.9,p.y*0.9,p.z*0.9-5.0,1.0); gl_PointSize=max(1.5,5.0/gl_Position.w); }
  `));
  gl.attachShader(program, compileShader(gl, gl.FRAGMENT_SHADER, `
    precision mediump float; void main(){ vec2 q=gl_PointCoord-vec2(.5); if(dot(q,q)>.25) discard; gl_FragColor=vec4(.45,.88,1.0,.9); }
  `));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
  const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(points.flatMap(point => [point.x, point.y, point.z])), gl.STATIC_DRAW);
  gl.useProgram(program);
  const position = gl.getAttribLocation(program, "p"); gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 3, gl.FLOAT, false, 0, 0);
  const projection = gl.getUniformLocation(program, "projection"), viewMatrix = gl.getUniformLocation(program, "view");
  const session = await navigator.xr.requestSession("immersive-vr", { optionalFeatures: ["local-floor"] });
  session.updateRenderState({ baseLayer: new XRWebGLLayer(session, gl) });
  const referenceSpace = await session.requestReferenceSpace("local-floor").catch(() => session.requestReferenceSpace("local"));
  state.xr = session; setMode(); ui["enter-xr"].textContent = "Выйти из XR"; ui.notice.textContent = "XR-сцена открыта. Синтетический пространственный проводник; Q=null.";
  const onFrame = (time, frame) => {
    const pose = frame.getViewerPose(referenceSpace);
    const layer = session.renderState.baseLayer;
    gl.bindFramebuffer(gl.FRAMEBUFFER, layer.framebuffer); gl.clearColor(.008, .02, .055, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    if (pose) for (const view of pose.views) {
      const viewport = layer.getViewport(view); gl.viewport(viewport.x, viewport.y, viewport.width, viewport.height);
      gl.uniformMatrix4fv(projection, false, view.projectionMatrix); gl.uniformMatrix4fv(viewMatrix, false, view.transform.inverse.matrix);
      gl.drawArrays(gl.POINTS, 0, points.length);
    }
    session.requestAnimationFrame(onFrame);
  };
  session.addEventListener("end", () => { state.xr = null; ui["enter-xr"].textContent = "Войти в XR"; setMode(); });
  session.requestAnimationFrame(onFrame);
}

if (navigator.xr) {
  navigator.xr.isSessionSupported("immersive-vr").then(supported => { ui["enter-xr"].hidden = !supported; });
  ui["enter-xr"].addEventListener("click", async () => {
    try { state.xr ? await state.xr.end() : await startXr(); }
    catch { ui.notice.textContent = "XR-сессия недоступна. Q=null."; }
  });
}

addEventListener("resize", resize); resize(); setMode(); frame();

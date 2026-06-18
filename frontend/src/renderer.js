import { mat4, vec4, vec2 } from 'gl-matrix';

const VERT_SRC = `
attribute vec2 a_position;
uniform mat4 u_mvp;
uniform vec4 u_color;
varying vec4 v_color;
void main() {
  gl_Position = u_mvp * vec4(a_position, 0.0, 1.0);
  v_color = u_color;
}
`;

const FRAG_SRC = `
precision mediump float;
varying vec4 v_color;
void main() {
  gl_FragColor = v_color;
}
`;

const VERT_SRC_OUTLINE = `
attribute vec2 a_position;
uniform mat4 u_mvp;
uniform vec4 u_color;
void main() {
  gl_Position = u_mvp * vec4(a_position, 0.0, 1.0);
}
`;

const FRAG_SRC_OUTLINE = `
precision mediump float;
uniform vec4 u_color;
void main() {
  gl_FragColor = u_color;
}
`;

const VERT_SRC_GLOW = `
attribute vec2 a_position;
attribute float a_intensity;
uniform mat4 u_mvp;
varying float v_intensity;
void main() {
  gl_Position = u_mvp * vec4(a_position, 0.0, 1.0);
  v_intensity = a_intensity;
}
`;

const FRAG_SRC_GLOW = `
precision mediump float;
varying float v_intensity;
uniform vec4 u_glowColor;
void main() {
  float i = clamp(v_intensity, 0.0, 1.0);
  float core = smoothstep(0.3, 0.7, i);
  float glow = smoothstep(0.0, 0.4, i) * 0.5;
  float alpha = (core * 0.7 + glow) * u_glowColor.a;
  vec3 col = mix(u_glowColor.rgb * 0.6, u_glowColor.rgb, core);
  gl_FragColor = vec4(col, alpha);
}
`;

export class WebGLRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.gl = null;
    this.program = null;
    this.outlineProgram = null;
    this.glowProgram = null;
    this.vertexBuffer = null;
    this.viewMatrix = mat4.create();
    this.projMatrix = mat4.create();
    this.mvpMatrix = mat4.create();
    this.backgroundColor = [0.059, 0.059, 0.078, 1.0];
    this.dirty = true;
    this.layers = new Map();
    this._vaoExtensions = null;
    this.drawCalls = 0;
    this.vertexCount = 0;
    this.layersDrawn = 0;
    this.gridEnabled = true;
    this._gridVerts = null;
    this._gridBuffer = null;
    this._outlineBuffer = null;
    this._dieRectBuffer = null;
    this._dieRectVerts = null;

    this._drcViolations = [];
    this._drcGlowBuffer = null;
    this._drcGlowVerts = null;
    this._drcVisible = true;
    this._drcHeatmapBuffer = null;
    this._drcHeatmapVerts = null;
  }

  init() {
    const gl = this.canvas.getContext('webgl', {
      antialias: true,
      alpha: false,
      preserveDrawingBuffer: false,
      premultipliedAlpha: false,
    });
    if (!gl) {
      throw new Error('WebGL is not supported in this browser');
    }
    this.gl = gl;
    this._vaoExtensions = gl.getExtension('OES_vertex_array_object');

    this.program = this._compileProgram(VERT_SRC, FRAG_SRC);
    this.outlineProgram = this._compileProgram(VERT_SRC_OUTLINE, FRAG_SRC_OUTLINE);
    this.glowProgram = this._compileProgram(VERT_SRC_GLOW, FRAG_SRC_GLOW);

    this.vertexBuffer = gl.createBuffer();
    this._outlineBuffer = gl.createBuffer();
    this._gridBuffer = gl.createBuffer();
    this._dieRectBuffer = gl.createBuffer();
    this._drcGlowBuffer = gl.createBuffer();
    this._drcHeatmapBuffer = gl.createBuffer();

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.disable(gl.DEPTH_TEST);
    gl.disable(gl.CULL_FACE);

    this.resize();
  }

  _compileShader(type, source) {
    const gl = this.gl;
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const info = gl.getShaderInfoLog(shader);
      console.error('Shader compile error:', info);
      gl.deleteShader(shader);
      throw new Error('Shader compile failed: ' + info);
    }
    return shader;
  }

  _compileProgram(vertSrc, fragSrc) {
    const gl = this.gl;
    const vs = this._compileShader(gl.VERTEX_SHADER, vertSrc);
    const fs = this._compileShader(gl.FRAGMENT_SHADER, fragSrc);
    const prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      const info = gl.getProgramInfoLog(prog);
      console.error('Program link error:', info);
      throw new Error('Program link failed: ' + info);
    }
    return prog;
  }

  resize() {
    if (!this.gl) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    const w = Math.floor(rect.width * dpr);
    const h = Math.floor(rect.height * dpr);
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    this.dirty = true;
  }

  setMatrices(proj, view) {
    mat4.copy(this.projMatrix, proj);
    mat4.copy(this.viewMatrix, view);
    mat4.multiply(this.mvpMatrix, proj, view);
    this.dirty = true;
  }

  setLayerData(layerName, vertices, color) {
    let entry = this.layers.get(layerName);
    if (!entry) {
      entry = {
        buffer: this.gl.createBuffer(),
        count: 0,
        color: color || [0.5, 0.5, 0.5, 0.8],
        visible: true,
      };
      this.layers.set(layerName, entry);
    }
    entry.count = vertices.length / 2;
    entry.color = color || entry.color;
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, entry.buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.DYNAMIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    this.dirty = true;
  }

  clearLayer(layerName) {
    const entry = this.layers.get(layerName);
    if (entry) {
      entry.count = 0;
      this.dirty = true;
    }
  }

  setLayerVisible(layerName, visible) {
    const entry = this.layers.get(layerName);
    if (entry) {
      entry.visible = visible;
      this.dirty = true;
    }
  }

  setLayerColor(layerName, color) {
    const entry = this.layers.get(layerName);
    if (entry) {
      entry.color = color;
      this.dirty = true;
    }
  }

  setDRCViolations(violations) {
    this._drcViolations = violations || [];
    this._buildDRCBuffers();
    this.dirty = true;
  }

  setDRCVisible(visible) {
    this._drcVisible = visible;
    this.dirty = true;
  }

  _buildDRCBuffers() {
    const gl = this.gl;
    if (!gl) return;

    const glowVerts = [];
    const heatmapVerts = [];

    for (const v of this._drcViolations) {
      const [llx, lly, urx, ury] = v.bbox;
      const cx = (llx + urx) / 2;
      const cy = (lly + ury) / 2;
      const hw = (urx - llx) / 2;
      const hh = (ury - lly) / 2;

      const isSevere = v.severity === 'error';
      const coreIntensity = isSevere ? 1.0 : 0.6;

      glowVerts.push(
        llx, lly, coreIntensity,
        urx, lly, coreIntensity,
        urx, ury, coreIntensity,
        llx, lly, coreIntensity,
        urx, ury, coreIntensity,
        llx, ury, coreIntensity,
      );

      const glowRings = 3;
      for (let ring = 1; ring <= glowRings; ring++) {
        const factor = 1.0 + ring * 0.5;
        const rll = cx - hw * factor;
        const rlr = cx + hw * factor;
        const rbl = cy - hh * factor;
        const rtr = cy + hh * factor;
        const innerFade = 1.0 - (ring / (glowRings + 1));
        const outerFade = 1.0 - ((ring - 0.5) / (glowRings + 1));
        const rll2 = cx - hw * (1 + (ring - 0.5) * 0.5);
        const rlr2 = cx + hw * (1 + (ring - 0.5) * 0.5);
        const rbl2 = cy - hh * (1 + (ring - 0.5) * 0.5);
        const rtr2 = cy + hh * (1 + (ring - 0.5) * 0.5);

        glowVerts.push(
          rll2, rbl2, innerFade,
          rlr2, rbl2, innerFade,
          rlr2, rtr2, innerFade,
          rll2, rbl2, innerFade,
          rlr2, rtr2, innerFade,
          rll2, rtr2, innerFade,
          rll, rbl, outerFade,
          rlr, rbl, outerFade,
          rlr, rtr, outerFade,
          rll, rbl, outerFade,
          rlr, rtr, outerFade,
          rll, rtr, outerFade,
        );
      }

      const heatRadius = Math.max(hw, hh) * 1.2;
      const heatSteps = 8;
      const heatIntensity = isSevere ? 0.22 : 0.12;
      for (let i = 0; i < heatSteps; i++) {
        const a1 = (i / heatSteps) * Math.PI * 2;
        const a2 = ((i + 1) / heatSteps) * Math.PI * 2;
        const x1 = cx + Math.cos(a1) * heatRadius;
        const y1 = cy + Math.sin(a1) * heatRadius;
        const x2 = cx + Math.cos(a2) * heatRadius;
        const y2 = cy + Math.sin(a2) * heatRadius;
        heatmapVerts.push(
          cx, cy, heatIntensity,
          x1, y1, 0.0,
          x2, y2, 0.0,
        );
      }
    }

    this._drcGlowVerts = glowVerts.length > 0 ? new Float32Array(glowVerts) : null;
    this._drcHeatmapVerts = heatmapVerts.length > 0 ? new Float32Array(heatmapVerts) : null;

    if (this._drcGlowVerts) {
      gl.bindBuffer(gl.ARRAY_BUFFER, this._drcGlowBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, this._drcGlowVerts, gl.DYNAMIC_DRAW);
    }
    if (this._drcHeatmapVerts) {
      gl.bindBuffer(gl.ARRAY_BUFFER, this._drcHeatmapBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, this._drcHeatmapVerts, gl.DYNAMIC_DRAW);
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
  }

  setGrid(bounds, spacingX, spacingY) {
    const verts = [];
    const minX = bounds.llx;
    const maxX = bounds.urx;
    const minY = bounds.lly;
    const maxY = bounds.ury;
    for (let x = minX; x <= maxX; x += spacingX) {
      verts.push(x, minY, x, maxY);
    }
    for (let y = minY; y <= maxY; y += spacingY) {
      verts.push(minX, y, maxX, y);
    }
    this._gridVerts = new Float32Array(verts);
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this._gridBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, this._gridVerts, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    this.dirty = true;
  }

  setDieRect(rect) {
    const verts = new Float32Array([
      rect.llx, rect.lly,
      rect.urx, rect.lly,
      rect.urx, rect.ury,
      rect.llx, rect.ury,
    ]);
    this._dieRectVerts = verts;
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this._dieRectBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, verts, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    this.dirty = true;
  }

  setBackgroundColor(r, g, b, a = 1.0) {
    this.backgroundColor = [r, g, b, a];
    this.dirty = true;
  }

  setDirty() {
    this.dirty = true;
  }

  render() {
    if (!this.gl) return;
    const gl = this.gl;
    this.resize();

    this.drawCalls = 0;
    this.vertexCount = 0;
    this.layersDrawn = 0;

    gl.clearColor(
      this.backgroundColor[0],
      this.backgroundColor[1],
      this.backgroundColor[2],
      this.backgroundColor[3]
    );
    gl.clear(gl.COLOR_BUFFER_BIT);

    if (this._gridVerts && this.gridEnabled) {
      this._drawGrid();
    }

    if (this._dieRectVerts) {
      this._drawDieRect();
    }

    gl.useProgram(this.program);
    const mvpLoc = gl.getUniformLocation(this.program, 'u_mvp');
    const colorLoc = gl.getUniformLocation(this.program, 'u_color');
    const posLoc = gl.getAttribLocation(this.program, 'a_position');
    gl.uniformMatrix4fv(mvpLoc, false, this.mvpMatrix);

    for (const [layerName, entry] of this.layers) {
      if (!entry.visible || entry.count === 0) continue;
      gl.uniform4f(colorLoc, entry.color[0], entry.color[1], entry.color[2], entry.color[3]);
      gl.bindBuffer(gl.ARRAY_BUFFER, entry.buffer);
      gl.enableVertexAttribArray(posLoc);
      gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);
      gl.drawArrays(gl.TRIANGLES, 0, entry.count);
      this.drawCalls++;
      this.vertexCount += entry.count;
      this.layersDrawn++;
    }

    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    gl.disableVertexAttribArray(0);
    gl.useProgram(null);

    if (this._drcVisible && this._drcHeatmapVerts) {
      this._drawDRCHeatmap();
    }

    if (this._drcVisible && this._drcGlowVerts) {
      this._drawDRCGlow();
    }

    this.dirty = false;
  }

  _drawDRCHeatmap() {
    const gl = this.gl;
    gl.useProgram(this.glowProgram);
    const mvpLoc = gl.getUniformLocation(this.glowProgram, 'u_mvp');
    const glowColorLoc = gl.getUniformLocation(this.glowProgram, 'u_glowColor');
    const posLoc = gl.getAttribLocation(this.glowProgram, 'a_position');
    const intensityLoc = gl.getAttribLocation(this.glowProgram, 'a_intensity');

    gl.uniformMatrix4fv(mvpLoc, false, this.mvpMatrix);
    gl.uniform4f(glowColorLoc, 1.0, 0.1, 0.05, 0.22);

    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    gl.bindBuffer(gl.ARRAY_BUFFER, this._drcHeatmapBuffer);
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 12, 0);
    gl.enableVertexAttribArray(intensityLoc);
    gl.vertexAttribPointer(intensityLoc, 1, gl.FLOAT, false, 12, 8);

    const vertCount = this._drcHeatmapVerts.length / 3;
    gl.drawArrays(gl.TRIANGLES, 0, vertCount);

    gl.disableVertexAttribArray(posLoc);
    gl.disableVertexAttribArray(intensityLoc);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.useProgram(null);
    this.drawCalls++;
  }

  _drawDRCGlow() {
    const gl = this.gl;
    gl.useProgram(this.glowProgram);
    const mvpLoc = gl.getUniformLocation(this.glowProgram, 'u_mvp');
    const glowColorLoc = gl.getUniformLocation(this.glowProgram, 'u_glowColor');
    const posLoc = gl.getAttribLocation(this.glowProgram, 'a_position');
    const intensityLoc = gl.getAttribLocation(this.glowProgram, 'a_intensity');

    gl.uniformMatrix4fv(mvpLoc, false, this.mvpMatrix);
    gl.uniform4f(glowColorLoc, 1.0, 0.15, 0.05, 0.85);

    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    gl.bindBuffer(gl.ARRAY_BUFFER, this._drcGlowBuffer);
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 12, 0);
    gl.enableVertexAttribArray(intensityLoc);
    gl.vertexAttribPointer(intensityLoc, 1, gl.FLOAT, false, 12, 8);

    const vertCount = this._drcGlowVerts.length / 3;
    gl.drawArrays(gl.TRIANGLES, 0, vertCount);

    gl.disableVertexAttribArray(posLoc);
    gl.disableVertexAttribArray(intensityLoc);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.useProgram(null);
    this.drawCalls++;
  }

  _drawGrid() {
    const gl = this.gl;
    gl.useProgram(this.outlineProgram);
    const mvpLoc = gl.getUniformLocation(this.outlineProgram, 'u_mvp');
    const colorLoc = gl.getUniformLocation(this.outlineProgram, 'u_color');
    const posLoc = gl.getAttribLocation(this.outlineProgram, 'a_position');
    gl.uniformMatrix4fv(mvpLoc, false, this.mvpMatrix);
    gl.uniform4f(colorLoc, 0.18, 0.18, 0.25, 0.7);
    gl.lineWidth(1);
    gl.bindBuffer(gl.ARRAY_BUFFER, this._gridBuffer);
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);
    gl.drawArrays(gl.LINES, 0, this._gridVerts.length / 2);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    gl.disableVertexAttribArray(posLoc);
    this.drawCalls++;
  }

  _drawDieRect() {
    const gl = this.gl;
    gl.useProgram(this.outlineProgram);
    const mvpLoc = gl.getUniformLocation(this.outlineProgram, 'u_mvp');
    const colorLoc = gl.getUniformLocation(this.outlineProgram, 'u_color');
    const posLoc = gl.getAttribLocation(this.outlineProgram, 'a_position');
    gl.uniformMatrix4fv(mvpLoc, false, this.mvpMatrix);
    gl.uniform4f(colorLoc, 0.95, 0.25, 0.25, 0.9);
    gl.lineWidth(2);
    gl.bindBuffer(gl.ARRAY_BUFFER, this._dieRectBuffer);
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);
    const count = this._dieRectVerts.length / 2;
    gl.drawArrays(gl.LINE_LOOP, 0, count);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    gl.disableVertexAttribArray(posLoc);
    this.drawCalls++;
  }

  getStats() {
    return {
      drawCalls: this.drawCalls,
      vertexCount: this.vertexCount,
      layersDrawn: this.layersDrawn,
      drcViolations: this._drcViolations.length,
    };
  }

  dispose() {
    if (!this.gl) return;
    const gl = this.gl;
    if (this.program) gl.deleteProgram(this.program);
    if (this.outlineProgram) gl.deleteProgram(this.outlineProgram);
    if (this.glowProgram) gl.deleteProgram(this.glowProgram);
    if (this.vertexBuffer) gl.deleteBuffer(this.vertexBuffer);
    if (this._outlineBuffer) gl.deleteBuffer(this._outlineBuffer);
    if (this._gridBuffer) gl.deleteBuffer(this._gridBuffer);
    if (this._dieRectBuffer) gl.deleteBuffer(this._dieRectBuffer);
    if (this._drcGlowBuffer) gl.deleteBuffer(this._drcGlowBuffer);
    if (this._drcHeatmapBuffer) gl.deleteBuffer(this._drcHeatmapBuffer);
    for (const entry of this.layers.values()) {
      if (entry.buffer) gl.deleteBuffer(entry.buffer);
    }
    this.layers.clear();
  }
}

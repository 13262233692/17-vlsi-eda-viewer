import { mat4, vec2, vec4 } from 'gl-matrix';

export class Camera {
  constructor() {
    this.viewMatrix = mat4.create();
    this.projMatrix = mat4.create();
    this.invViewMatrix = mat4.create();
    this.position = vec2.fromValues(0, 0);
    this.scale = 1.0;
    this.canvasWidth = 1;
    this.canvasHeight = 1;
    this.worldBounds = { llx: -1000, lly: -1000, urx: 1000, ury: 1000 };
    this.dpr = window.devicePixelRatio || 1;
    this.minScale = 0.001;
    this.maxScale = 100000;
  }

  setCanvasSize(w, h) {
    this.canvasWidth = w;
    this.canvasHeight = h;
    this._updateMatrices();
  }

  setWorldBounds(bounds) {
    this.worldBounds = {
      llx: bounds.llx ?? bounds.llx,
      lly: bounds.lly ?? bounds.lly,
      urx: bounds.urx ?? bounds.urx,
      ury: bounds.ury ?? bounds.ury,
    };
    const w = this.worldBounds.urx - this.worldBounds.llx;
    const h = this.worldBounds.ury - this.worldBounds.lly;
    this.minScale = Math.min(1 / w, 1 / h) * 0.1;
  }

  fitToBounds(bounds, paddingPct = 0.08) {
    const w = bounds.urx - bounds.llx;
    const h = bounds.ury - bounds.lly;
    const aspectCanvas = this.canvasWidth / this.canvasHeight;
    const aspectWorld = w / h;

    let scale;
    if (aspectCanvas > aspectWorld) {
      scale = this.canvasHeight / (h * (1 + paddingPct));
    } else {
      scale = this.canvasWidth / (w * (1 + paddingPct));
    }
    this.scale = scale;

    const cx = (bounds.llx + bounds.urx) / 2;
    const cy = (bounds.lly + bounds.ury) / 2;
    this.position[0] = cx;
    this.position[1] = cy;
    this._updateMatrices();
  }

  _updateMatrices() {
    const sx = (2 * this.scale) / this.canvasWidth;
    const sy = (2 * this.scale) / this.canvasHeight;

    mat4.identity(this.projMatrix);
    mat4.orthoNO(this.projMatrix, -this.canvasWidth / 2, this.canvasWidth / 2, -this.canvasHeight / 2, this.canvasHeight / 2, -1, 1);

    mat4.identity(this.viewMatrix);
    mat4.scale(this.viewMatrix, this.viewMatrix, [this.scale, this.scale, 1]);
    mat4.translate(this.viewMatrix, this.viewMatrix, [-this.position[0], -this.position[1], 0]);

    mat4.invert(this.invViewMatrix, this.viewMatrix);
  }

  update() {
    this.scale = Math.max(this.minScale, Math.min(this.maxScale, this.scale));
    this._updateMatrices();
  }

  screenToWorld(screenX, screenY) {
    const ndcX = (screenX - this.canvasWidth / 2);
    const ndcY = -(screenY - this.canvasHeight / 2);
    const worldX = ndcX / this.scale + this.position[0];
    const worldY = ndcY / this.scale + this.position[1];
    return [worldX, worldY];
  }

  worldToScreen(worldX, worldY) {
    const sx = (worldX - this.position[0]) * this.scale + this.canvasWidth / 2;
    const sy = this.canvasHeight / 2 - (worldY - this.position[1]) * this.scale;
    return [sx, sy];
  }

  getViewportWorld() {
    const [x0, y0] = this.screenToWorld(0, this.canvasHeight);
    const [x1, y1] = this.screenToWorld(this.canvasWidth, 0);
    return {
      llx: Math.min(x0, x1),
      lly: Math.min(y0, y1),
      urx: Math.max(x0, x1),
      ury: Math.max(y0, y1),
    };
  }

  pan(dx, dy) {
    this.position[0] -= dx / this.scale;
    this.position[1] += dy / this.scale;
    this._updateMatrices();
  }

  zoomAt(screenX, screenY, factor) {
    const worldBefore = this.screenToWorld(screenX, screenY);
    this.scale *= factor;
    this.scale = Math.max(this.minScale, Math.min(this.maxScale, this.scale));
    this._updateMatrices();
    const worldAfter = this.screenToWorld(screenX, screenY);
    this.position[0] += worldBefore[0] - worldAfter[0];
    this.position[1] += worldBefore[1] - worldAfter[1];
    this._updateMatrices();
  }

  getZoomPercent() {
    const baseScale = Math.min(
      this.canvasWidth / (this.worldBounds.urx - this.worldBounds.llx),
      this.canvasHeight / (this.worldBounds.ury - this.worldBounds.lly),
    );
    return Math.round((this.scale / baseScale) * 100);
  }

  setScale(newScale) {
    this.scale = Math.max(this.minScale, Math.min(this.maxScale, newScale));
    this._updateMatrices();
  }

  resetView() {
    this.position = vec2.fromValues(0, 0);
    this.scale = 1;
    this.fitToBounds(this.worldBounds);
  }
}

if (!mat4.orthoNO) {
  mat4.orthoNO = function (out, left, right, bottom, top, near, far) {
    const lr = 1 / (left - right);
    const bt = 1 / (bottom - top);
    const nf = 1 / (near - far);
    out[0] = -2 * lr;
    out[1] = 0;
    out[2] = 0;
    out[3] = 0;
    out[4] = 0;
    out[5] = -2 * bt;
    out[6] = 0;
    out[7] = 0;
    out[8] = 0;
    out[9] = 0;
    out[10] = 2 * nf;
    out[11] = 0;
    out[12] = (left + right) * lr;
    out[13] = (top + bottom) * bt;
    out[14] = (far + near) * nf;
    out[15] = 1;
    return out;
  };
}

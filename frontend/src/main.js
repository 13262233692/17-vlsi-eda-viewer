import { WebGLRenderer } from './renderer.js';
import { Camera } from './camera.js';
import { TileManager } from './tile_manager.js';

class EdaViewerApp {
  constructor() {
    this.renderer = null;
    this.camera = null;
    this.tileManager = new TileManager();

    this.isLoaded = false;
    this.designLoaded = false;
    this.chipBbox = null;
    this.layers = [];
    this.visibleLayers = new Set();

    this.lefFile = null;
    this.defFile = null;
    this.parseTaskId = null;
    this.progressPollInterval = null;

    this.lastFrameTime = 0;
    this.fps = 0;
    this.frameCount = 0;
    this.fpsTime = 0;

    this.isDragging = false;
    this.lastMouse = { x: 0, y: 0 };
    this.needTileRefresh = true;
    this.needRender = true;
    this.tileRefreshTimer = null;
    this.viewportChangedAt = 0;
    this.lastTiledViewport = null;

    this.elements = {};
    this._cacheElements();
  }

  _cacheElements() {
    const ids = [
      'glCanvas', 'miniMapCanvas', 'miniMapViewport',
      'lefFile', 'defFile', 'btnParse', 'btnDemo',
      'btnFit', 'btnReset', 'btnZoomIn', 'btnZoomOut',
      'zoomLevel', 'layerList', 'btnAllOn', 'btnAllOff',
      'statusIndicator', 'statusText',
      'diStatus', 'diDesign', 'diInstances', 'diPins', 'diNets', 'diWires',
      'diX', 'diY', 'diCursor',
      'rsFps', 'rsDraws', 'rsVerts', 'rsLayers', 'rsTiles', 'rsPending',
      'progressFill', 'progressText', 'progressBar', 'helpHint', 'viewportOverlay',
    ];
    for (const id of ids) {
      this.elements[id] = document.getElementById(id);
    }
  }

  async init() {
    try {
      this.renderer = new WebGLRenderer(this.elements.glCanvas);
      this.renderer.init();
    } catch (e) {
      this._setStatus('error', 'WebGL initialization failed: ' + e.message);
      alert('Failed to initialize WebGL: ' + e.message);
      return;
    }

    this.camera = new Camera();
    const rect = this.elements.glCanvas.getBoundingClientRect();
    this.camera.setCanvasSize(rect.width, rect.height);

    this.tileManager.baseUrl = '/api';
    this.tileManager.onTilesLoaded = () => {
      this._combineLayerData();
      this.needRender = true;
    };

    this._bindEvents();
    this._setStatus('ready', 'Ready');
    this._loop();
    this._startHealthCheck();

    setTimeout(() => {
      this.elements.helpHint?.classList.add('hidden');
    }, 8000);
  }

  _bindEvents() {
    const canvas = this.elements.glCanvas;

    window.addEventListener('resize', () => this._onResize());

    canvas.addEventListener('mousedown', (e) => this._onMouseDown(e));
    window.addEventListener('mouseup', (e) => this._onMouseUp(e));
    window.addEventListener('mousemove', (e) => this._onMouseMove(e));
    canvas.addEventListener('wheel', (e) => this._onWheel(e), { passive: false });
    canvas.addEventListener('dblclick', (e) => this._onDoubleClick(e));

    canvas.addEventListener('touchstart', (e) => this._onTouchStart(e), { passive: false });
    canvas.addEventListener('touchmove', (e) => this._onTouchMove(e), { passive: false });
    canvas.addEventListener('touchend', (e) => this._onTouchEnd(e));

    this.elements.lefFile.addEventListener('change', (e) => {
      this.lefFile = e.target.files[0];
      this._checkParseReady();
    });
    this.elements.defFile.addEventListener('change', (e) => {
      this.defFile = e.target.files[0];
      this._checkParseReady();
    });
    this.elements.btnParse.addEventListener('click', () => this._onParse());
    this.elements.btnDemo.addEventListener('click', () => this._onLoadDemo());
    this.elements.btnFit.addEventListener('click', () => this._fitToChip());
    this.elements.btnReset.addEventListener('click', () => this.camera.resetView());
    this.elements.btnZoomIn.addEventListener('click', () => {
      const r = this.elements.glCanvas.getBoundingClientRect();
      this.camera.zoomAt(r.width / 2, r.height / 2, 1.5);
      this._onViewportChanged();
    });
    this.elements.btnZoomOut.addEventListener('click', () => {
      const r = this.elements.glCanvas.getBoundingClientRect();
      this.camera.zoomAt(r.width / 2, r.height / 2, 1 / 1.5);
      this._onViewportChanged();
    });

    this.elements.btnAllOn.addEventListener('click', () => this._setAllLayers(true));
    this.elements.btnAllOff.addEventListener('click', () => this._setAllLayers(false));
  }

  _checkParseReady() {
    this.elements.btnParse.disabled = !(this.lefFile && this.defFile);
  }

  _setStatus(state, text) {
    const ind = this.elements.statusIndicator;
    if (ind) {
      ind.className = 'status-indicator ' + (state || '');
    }
    if (this.elements.statusText) {
      this.elements.statusText.textContent = text || '';
    }
  }

  _onResize() {
    const rect = this.elements.glCanvas.getBoundingClientRect();
    this.camera.setCanvasSize(rect.width, rect.height);
    if (this.renderer) {
      this.renderer.setMatrices(this.camera.projMatrix, this.camera.viewMatrix);
      this.renderer.setDirty();
    }
    this._onViewportChanged(true);
  }

  _onMouseDown(e) {
    this.isDragging = true;
    this.lastMouse.x = e.clientX;
    this.lastMouse.y = e.clientY;
    this.elements.glCanvas.classList.add('grabbing');
  }

  _onMouseUp() {
    this.isDragging = false;
    this.elements.glCanvas.classList.remove('grabbing');
  }

  _onMouseMove(e) {
    const rect = this.elements.glCanvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    if (this.isLoaded && this.chipBbox) {
      const [wx, wy] = this.camera.screenToWorld(mx, my);
      if (this.elements.diCursor) {
        this.elements.diCursor.textContent = `${wx.toFixed(0)}, ${wy.toFixed(0)}`;
      }
    }

    if (this.isDragging) {
      const dx = e.clientX - this.lastMouse.x;
      const dy = e.clientY - this.lastMouse.y;
      this.camera.pan(dx, dy);
      this.lastMouse.x = e.clientX;
      this.lastMouse.y = e.clientY;
      this._onViewportChanged();
    }
  }

  _onWheel(e) {
    e.preventDefault();
    const rect = this.elements.glCanvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY > 0 ? (1 / 1.2) : 1.2;
    this.camera.zoomAt(mx, my, factor);
    this._onViewportChanged();
  }

  _onDoubleClick(e) {
    const rect = this.elements.glCanvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    this.camera.zoomAt(mx, my, e.shiftKey ? (1 / 2) : 2);
    this._onViewportChanged();
  }

  _onTouchStart(e) {
    e.preventDefault();
    if (e.touches.length === 1) {
      this.isDragging = true;
      this.lastMouse.x = e.touches[0].clientX;
      this.lastMouse.y = e.touches[0].clientY;
    }
  }

  _onTouchMove(e) {
    e.preventDefault();
    if (this.isDragging && e.touches.length === 1) {
      const dx = e.touches[0].clientX - this.lastMouse.x;
      const dy = e.touches[0].clientY - this.lastMouse.y;
      this.camera.pan(dx, dy);
      this.lastMouse.x = e.touches[0].clientX;
      this.lastMouse.y = e.touches[0].clientY;
      this._onViewportChanged();
    }
  }

  _onTouchEnd() {
    this.isDragging = false;
  }

  _onViewportChanged(immediate = false) {
    this.needRender = true;
    this.viewportChangedAt = performance.now();
    this.needTileRefresh = true;

    if (this.tileRefreshTimer) {
      clearTimeout(this.tileRefreshTimer);
    }

    const delay = immediate ? 0 : 80;
    this.tileRefreshTimer = setTimeout(() => {
      this._refreshTiles();
    }, delay);

    this._updateMiniMapViewport();
    this._updateZoomLevel();
  }

  _updateZoomLevel() {
    if (this.elements.zoomLevel) {
      const pct = this.camera.getZoomPercent();
      this.elements.zoomLevel.textContent = `${pct}%`;
    }
  }

  async _startHealthCheck() {
    try {
      const resp = await fetch('/api/health');
      if (resp.ok) {
        const data = await resp.json();
        if (data.is_loaded) {
          await this._refreshChipInfo();
        }
      }
    } catch (e) {
      console.warn('Health check failed:', e.message);
    }
  }

  async _onParse() {
    if (!this.lefFile || !this.defFile) return;

    this.elements.btnParse.disabled = true;
    this.elements.btnDemo.disabled = true;
    this._setStatus('loading', 'Uploading files...');
    this._setProgress(0, 'Uploading LEF/DEF files...');

    try {
      const formData = new FormData();
      formData.append('lef_file', this.lefFile, this.lefFile.name);
      formData.append('def_file', this.defFile, this.defFile.name);

      const resp = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      if (!resp.ok) throw new Error('Upload failed: ' + resp.status);
      const data = await resp.json();
      this.parseTaskId = data.task_id;
      this._setStatus('loading', 'Parsing LEF/DEF files...');
      this._startProgressPolling();
    } catch (e) {
      this._setStatus('error', 'Upload failed: ' + e.message);
      this._setProgress(0, 'Error: ' + e.message);
      this.elements.btnParse.disabled = false;
      this.elements.btnDemo.disabled = false;
    }
  }

  async _onLoadDemo() {
    this.elements.btnDemo.disabled = true;
    this.elements.btnParse.disabled = true;
    this._setStatus('loading', 'Generating demo design...');
    this._setProgress(1, 'Generating demo design...');

    try {
      const resp = await fetch('/api/demo', { method: 'POST' });
      if (!resp.ok) throw new Error('Demo API failed: ' + resp.status);
      const data = await resp.json();
      this.parseTaskId = data.task_id;
      this._setStatus('loading', 'Building demo design index...');
      this._startProgressPolling();
    } catch (e) {
      this._setStatus('error', 'Failed to start demo: ' + e.message);
      this.elements.btnDemo.disabled = false;
      this.elements.btnParse.disabled = false;
    }
  }

  _startProgressPolling() {
    if (this.progressPollInterval) clearInterval(this.progressPollInterval);
    this.progressPollInterval = setInterval(() => this._pollProgress(), 400);
    this._pollProgress();
  }

  async _pollProgress() {
    if (!this.parseTaskId) return;
    try {
      const resp = await fetch(`/api/progress/${this.parseTaskId}`);
      if (!resp.ok) {
        clearInterval(this.progressPollInterval);
        return;
      }
      const p = await resp.json();
      const msg = p.message || p.status;
      const pct = p.progress || 0;
      this._setProgress(pct, msg);

      if (p.status === 'completed') {
        clearInterval(this.progressPollInterval);
        this._setProgress(100, 'Loading design into view...');
        setTimeout(() => this._refreshChipInfo(), 200);
      } else if (p.status === 'error') {
        clearInterval(this.progressPollInterval);
        this._setStatus('error', 'Parse error: ' + (p.error || 'Unknown'));
        this._setProgress(0, 'Error: ' + (p.error || 'Unknown'));
        this.elements.btnParse.disabled = false;
        this.elements.btnDemo.disabled = false;
      }
    } catch (e) {
      console.warn('Progress poll error:', e.message);
    }
  }

  _setProgress(pct, text) {
    if (this.elements.progressFill) {
      this.elements.progressFill.style.width = `${pct}%`;
    }
    if (this.elements.progressText) {
      this.elements.progressText.textContent = text || `${pct}%`;
    }
  }

  async _refreshChipInfo() {
    try {
      const resp = await fetch('/api/chip');
      if (!resp.ok) throw new Error('Failed to load chip info');
      const info = await resp.json();
      if (!info.is_loaded) return;

      this.chipBbox = info.chip_bbox;
      this.layers = info.layers || [];
      this.isLoaded = true;
      this.designLoaded = true;

      this.camera.setWorldBounds(this.chipBbox);
      this._fitToChip();

      this.renderer.setDieRect({
        llx: this.chipBbox.llx,
        lly: this.chipBbox.lly,
        urx: this.chipBbox.urx,
        ury: this.chipBbox.ury,
      });

      const gridStep = this._computeGridStep();
      this.renderer.setGrid(this.chipBbox, gridStep.x, gridStep.y);

      this._renderLayerList();
      this._renderDesignInfo(info);
      this._renderMiniMap();

      this.tileManager.clear();
      this.visibleLayers.clear();
      for (const l of this.layers) {
        if (l.visible !== false) this.visibleLayers.add(l.name);
      }

      this._setStatus('active', 'Design loaded');
      this._setProgress(100, 'Ready');
      this._onViewportChanged(true);

      this.elements.btnParse.disabled = false;
      this.elements.btnDemo.disabled = false;
    } catch (e) {
      this._setStatus('error', 'Failed to load chip info: ' + e.message);
      console.error(e);
    }
  }

  _computeGridStep() {
    const w = this.chipBbox.urx - this.chipBbox.llx;
    const h = this.chipBbox.ury - this.chipBbox.lly;
    const targetLines = 50;
    let sx = Math.pow(10, Math.ceil(Math.log10(w / targetLines)));
    let sy = Math.pow(10, Math.ceil(Math.log10(h / targetLines)));
    if (w / sx < 20) sx /= 2;
    if (h / sy < 20) sy /= 2;
    if (w / sx > 100) sx *= 5;
    if (h / sy > 100) sy *= 5;
    return { x: sx, y: sy };
  }

  _fitToChip() {
    if (!this.chipBbox) return;
    this.camera.fitToBounds(this.chipBbox);
    this._onViewportChanged(true);
  }

  _renderLayerList() {
    const container = this.elements.layerList;
    container.innerHTML = '';

    if (!this.layers.length) {
      container.innerHTML = '<div class="empty-hint">No layers</div>';
      return;
    }

    for (const layer of this.layers) {
      const div = document.createElement('div');
      div.className = 'layer-item';
      div.dataset.layer = layer.name;
      const isVisible = layer.visible !== false;

      const colorRgba = layer.color || [0.5, 0.5, 0.5, 0.8];
      const colorCss = `rgba(${(colorRgba[0]*255)|0}, ${(colorRgba[1]*255)|0}, ${(colorRgba[2]*255)|0}, ${colorRgba[3] || 0.8})`;

      div.innerHTML = `
        <div class="layer-checkbox ${isVisible ? 'active' : ''}"></div>
        <div class="layer-swatch" style="background:${colorCss}"></div>
        <div class="layer-name" title="${layer.name}">${layer.name}</div>
        <div class="layer-count">${layer.count != null ? layer.count.toLocaleString() : ''}</div>
      `;

      div.addEventListener('click', (e) => {
        e.stopPropagation();
        const checkbox = div.querySelector('.layer-checkbox');
        const isOn = checkbox.classList.toggle('active');
        if (isOn) this.visibleLayers.add(layer.name);
        else this.visibleLayers.delete(layer.name);
        this.renderer.setLayerVisible(layer.name, isOn);
        this.needRender = true;
        this._onViewportChanged(true);
      });

      container.appendChild(div);
    }
  }

  _setAllLayers(visible) {
    const items = document.querySelectorAll('.layer-item');
    for (const item of items) {
      const lname = item.dataset.layer;
      const checkbox = item.querySelector('.layer-checkbox');
      if (visible) {
        checkbox.classList.add('active');
        this.visibleLayers.add(lname);
      } else {
        checkbox.classList.remove('active');
        this.visibleLayers.delete(lname);
      }
      this.renderer.setLayerVisible(lname, visible);
    }
    this.needRender = true;
    this._onViewportChanged(true);
  }

  _renderDesignInfo(info) {
    const s = info.stats || {};
    if (this.elements.diStatus) this.elements.diStatus.textContent = 'Loaded';
    if (this.elements.diInstances) this.elements.diInstances.textContent = (s.total_components || 0).toLocaleString();
    if (this.elements.diPins) this.elements.diPins.textContent = (s.total_pins || 0).toLocaleString();
    if (this.elements.diNets) this.elements.diNets.textContent = (s.total_nets || 0).toLocaleString();
    if (this.elements.diWires) this.elements.diWires.textContent = (s.total_routing_segments || 0).toLocaleString();
    if (this.chipBbox) {
      if (this.elements.diX) this.elements.diX.textContent = `${(this.chipBbox.urx - this.chipBbox.llx).toFixed(0)}`;
      if (this.elements.diY) this.elements.diY.textContent = `${(this.chipBbox.ury - this.chipBbox.lly).toFixed(0)}`;
    }
  }

  _refreshTiles() {
    if (!this.isLoaded || !this.chipBbox) return;
    const viewport = this.camera.getViewportWorld();

    if (this.lastTiledViewport && this._viewportsSimilar(viewport, this.lastTiledViewport, 0.02)) {
      this._combineLayerData();
      return;
    }
    this.lastTiledViewport = { ...viewport };

    const tiles = this.tileManager.computeTilesForViewport(viewport, 0.25);
    const layerList = this.visibleLayers.size > 0 ? Array.from(this.visibleLayers) : null;

    const visibleRatio = this._visibleTileRatio(viewport);
    let maxPerLayer = 20000;
    if (visibleRatio < 0.01) maxPerLayer = 8000;
    else if (visibleRatio < 0.05) maxPerLayer = 15000;
    else if (visibleRatio > 0.5) maxPerLayer = 30000;

    this.tileManager.requestTiles(tiles, layerList, maxPerLayer);
    this._combineLayerData();
  }

  _visibleTileRatio(viewport) {
    const chipW = this.chipBbox.urx - this.chipBbox.llx;
    const chipH = this.chipBbox.ury - this.chipBbox.lly;
    const chipArea = chipW * chipH;
    if (chipArea <= 0) return 1;
    const vw = viewport.urx - viewport.llx;
    const vh = viewport.ury - viewport.lly;
    return (vw * vh) / chipArea;
  }

  _viewportsSimilar(a, b, tol = 0.05) {
    const aw = a.urx - a.llx;
    const ah = a.ury - a.lly;
    const bw = b.urx - b.llx;
    const bh = b.ury - b.lly;
    const dx = Math.abs(a.llx - b.llx);
    const dy = Math.abs(a.lly - b.lly);
    return (dx / Math.max(aw, bw) < tol) && (dy / Math.max(ah, bh) < tol);
  }

  _combineLayerData() {
    const viewport = this.camera.getViewportWorld();
    const visibleList = this.visibleLayers.size > 0 ? Array.from(this.visibleLayers) : null;
    const { layerVerts, layerColors } = this.tileManager.collectLayerDataFromVisible(viewport, visibleList);

    for (const [lname, verts] of layerVerts) {
      const color = layerColors.get(lname);
      this.renderer.setLayerData(lname, verts, color);
    }

    for (const layer of this.layers) {
      if (!layerVerts.has(layer.name)) {
        this.renderer.clearLayer(layer.name);
      }
    }

    this.needRender = true;
  }

  _renderMiniMap() {
    const canvas = this.elements.miniMapCanvas;
    if (!canvas || !this.chipBbox) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    ctx.fillStyle = '#0f0f14';
    ctx.fillRect(0, 0, rect.width, rect.height);

    const pad = 8;
    const plotW = rect.width - pad * 2;
    const plotH = rect.height - pad * 2;
    const chipW = this.chipBbox.urx - this.chipBbox.llx;
    const chipH = this.chipBbox.ury - this.chipBbox.lly;
    const sx = plotW / chipW;
    const sy = plotH / chipH;
    const s = Math.min(sx, sy);
    const offX = pad + (plotW - chipW * s) / 2;
    const offY = pad + (plotH - chipH * s) / 2;
    this._mmScale = { s, offX, offY, rect, pad, chipW, chipH };

    ctx.strokeStyle = '#f87171';
    ctx.lineWidth = 1;
    ctx.strokeRect(
      offX,
      offY,
      chipW * s,
      chipH * s,
    );

    ctx.fillStyle = 'rgba(74, 158, 255, 0.15)';
    ctx.fillRect(offX, offY, chipW * s, chipH * s);

    this._updateMiniMapViewport();
  }

  _updateMiniMapViewport() {
    const el = this.elements.miniMapViewport;
    if (!el || !this.chipBbox || !this._mmScale) return;
    const { s, offX, offY, rect, chipW, chipH } = this._mmScale;
    const vp = this.camera.getViewportWorld();

    const llx = Math.max(this.chipBbox.llx, vp.llx);
    const lly = Math.max(this.chipBbox.lly, vp.lly);
    const urx = Math.min(this.chipBbox.urx, vp.urx);
    const ury = Math.min(this.chipBbox.ury, vp.ury);

    if (urx <= llx || ury <= lly) {
      el.style.display = 'none';
      return;
    }

    const x = offX + (llx - this.chipBbox.llx) * s;
    const y = rect.height - offY - (ury - this.chipBbox.lly) * s;
    const w = Math.max(1, (urx - llx) * s);
    const h = Math.max(1, (ury - lly) * s);

    el.style.display = 'block';
    el.style.left = x + 'px';
    el.style.top = y + 'px';
    el.style.width = w + 'px';
    el.style.height = h + 'px';
  }

  _renderStats() {
    const stats = this.renderer.getStats();
    const tileStats = this.tileManager.getStats();
    if (this.elements.rsFps) this.elements.rsFps.textContent = this.fps.toFixed(0);
    if (this.elements.rsDraws) this.elements.rsDraws.textContent = stats.drawCalls;
    if (this.elements.rsVerts) this.elements.rsVerts.textContent = stats.vertexCount.toLocaleString();
    if (this.elements.rsLayers) this.elements.rsLayers.textContent = stats.layersDrawn;
    if (this.elements.rsTiles) this.elements.rsTiles.textContent = `${tileStats.cached} (${tileStats.loaded})`;
    if (this.elements.rsPending) this.elements.rsPending.textContent = tileStats.pending + tileStats.queued;
  }

  _loop() {
    const now = performance.now();
    const dt = now - this.lastFrameTime;
    this.lastFrameTime = now;

    this.frameCount++;
    this.fpsTime += dt;
    if (this.fpsTime >= 500) {
      this.fps = (this.frameCount * 1000) / this.fpsTime;
      this.frameCount = 0;
      this.fpsTime = 0;
      this._renderStats();
    }

    if (this.camera) {
      this.renderer.setMatrices(this.camera.projMatrix, this.camera.viewMatrix);
    }

    if (this.needRender || this.renderer.dirty) {
      this.renderer.render();
      this.needRender = false;
    }

    requestAnimationFrame(() => this._loop());
  }
}

const app = new EdaViewerApp();
window.__edaApp = app;
window.addEventListener('DOMContentLoaded', () => {
  app.init();
});

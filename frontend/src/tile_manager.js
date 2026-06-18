export class TileManager {
  constructor() {
    this.cache = new Map();
    this.pendingRequests = new Map();
    this.lruOrder = [];
    this.maxCacheSize = 2000;
    this.maxPending = 8;
    this.requestQueue = [];
    this.tilesRequested = 0;
    this.tilesLoaded = 0;
    this.baseUrl = '/api';
    this.onTilesLoaded = null;
  }

  clear() {
    this.cache.clear();
    this.pendingRequests.forEach(ctrl => ctrl.abort());
    this.pendingRequests.clear();
    this.lruOrder = [];
    this.requestQueue = [];
    this.tilesRequested = 0;
    this.tilesLoaded = 0;
  }

  getStats() {
    return {
      cached: this.cache.size,
      pending: this.pendingRequests.size,
      queued: this.requestQueue.length,
      requested: this.tilesRequested,
      loaded: this.tilesLoaded,
    };
  }

  setBaseUrl(url) {
    this.baseUrl = url;
  }

  _makeKey(x, y, w, h) {
    return `${x.toFixed(0)}_${y.toFixed(0)}_${w.toFixed(0)}_${h.toFixed(0)}`;
  }

  _touchCache(key) {
    const idx = this.lruOrder.indexOf(key);
    if (idx !== -1) {
      this.lruOrder.splice(idx, 1);
    }
    this.lruOrder.push(key);
    if (this.lruOrder.length > this.maxCacheSize) {
      const removed = this.lruOrder.splice(0, this.lruOrder.length - this.maxCacheSize);
      for (const k of removed) {
        this.cache.delete(k);
      }
    }
  }

  computeTilesForViewport(viewport, overlap = 0.3) {
    const vw = viewport.urx - viewport.llx;
    const vh = viewport.ury - viewport.lly;

    let tileW = vw / 2;
    let tileH = vh / 2;

    const minTileSize = 100;
    tileW = Math.max(minTileSize, tileW);
    tileH = Math.max(minTileSize, tileH);

    const overlapW = tileW * overlap;
    const overlapH = tileH * overlap;
    const stepW = tileW - overlapW;
    const stepH = tileH - overlapH;

    const tiles = [];
    const startX = viewport.llx - overlapW;
    const startY = viewport.lly - overlapH;
    const endX = viewport.urx + overlapW;
    const endY = viewport.ury + overlapH;

    for (let x = startX; x < endX; x += stepW) {
      for (let y = startY; y < endY; y += stepH) {
        tiles.push({
          x: Math.floor(x),
          y: Math.floor(y),
          w: Math.ceil(tileW),
          h: Math.ceil(tileH),
        });
      }
    }
    return tiles;
  }

  requestTiles(tiles, layers = null, maxPerLayer = 15000) {
    const layerStr = layers && layers.length ? layers.join(',') : null;
    let loadedThisRound = 0;
    const promises = [];

    for (const tile of tiles) {
      const key = this._makeKey(tile.x, tile.y, tile.w, tile.h);

      if (this.cache.has(key)) {
        this._touchCache(key);
        loadedThisRound++;
        continue;
      }

      if (this.pendingRequests.has(key)) {
        continue;
      }

      const params = new URLSearchParams();
      params.set('x', String(tile.x));
      params.set('y', String(tile.y));
      params.set('w', String(tile.w));
      params.set('h', String(tile.h));
      params.set('max_per_layer', String(maxPerLayer));
      if (layerStr) {
        params.set('layers', layerStr);
      }

      const url = `${this.baseUrl}/tile?${params.toString()}`;
      const queueItem = { tile, key, url };
      this.requestQueue.push(queueItem);
    }

    this._processQueue();

    return {
      fromCache: loadedThisRound,
      requested: this.requestQueue.length + this.pendingRequests.size,
    };
  }

  _processQueue() {
    while (this.pendingRequests.size < this.maxPending && this.requestQueue.length > 0) {
      const item = this.requestQueue.shift();
      this._fetchTile(item);
    }
  }

  async _fetchTile({ tile, key, url }) {
    const controller = new AbortController();
    this.pendingRequests.set(key, controller);
    this.tilesRequested++;

    try {
      const response = await fetch(url, {
        signal: controller.signal,
        credentials: 'same-origin',
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (!this.pendingRequests.has(key)) {
        return;
      }

      this.cache.set(key, { tile, data, time: Date.now() });
      this._touchCache(key);
      this.tilesLoaded++;

      if (this.onTilesLoaded) {
        this.onTilesLoaded(tile, data);
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.warn('Tile fetch failed:', url, err.message);
      }
    } finally {
      this.pendingRequests.delete(key);
      this._processQueue();
    }
  }

  collectLayerDataFromVisible(viewport, visibleLayers = null) {
    const layerVerts = new Map();
    const layerCounts = new Map();
    const layerColors = new Map();

    for (const [key, cached] of this.cache) {
      const { tile, data } = cached;
      const tileRect = {
        llx: tile.x,
        lly: tile.y,
        urx: tile.x + tile.w,
        ury: tile.y + tile.h,
      };
      if (!rectsOverlap(tileRect, viewport)) continue;
      if (!data || !data.layers) continue;

      for (const layer of data.layers) {
        const lname = layer.name;
        if (visibleLayers && visibleLayers.length && !visibleLayers.includes(lname)) continue;

        let verts = layerVerts.get(lname);
        if (!verts) {
          verts = [];
          layerVerts.set(lname, verts);
          layerColors.set(lname, layer.color);
          layerCounts.set(lname, 0);
        }

        if (layer.vertices && layer.vertices.length) {
          verts.push(...layer.vertices);
        }
        layerCounts.set(lname, (layerCounts.get(lname) || 0) + (layer.count || 0));
      }
    }

    return { layerVerts, layerColors, layerCounts };
  }
}

function rectsOverlap(a, b) {
  return !(a.urx < b.llx || a.llx > b.urx || a.ury < b.lly || a.lly > b.ury);
}

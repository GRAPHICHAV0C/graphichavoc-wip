(() => {
  'use strict';

  const status = document.getElementById('status');
  const moduleBase = new URL('../', document.currentScript.src);
  const warn = (message) => {
    status.hidden = false;
    status.textContent = message;
    console.error(message);
  };

  if (!window.OpenSeadragon) {
    warn('OpenSeadragon could not load. Check your internet connection and refresh.');
    return;
  }

  const OSD = window.OpenSeadragon;

  function regionSource(region, tileSize, regionSize) {
    const prefix = new URL(`tiles/x${region.x}_y${region.y}_`, moduleBase).href;
    return {
      width: regionSize,
      height: regionSize,
      tileSize,
      tileOverlap: 0,
      minLevel: 0,
      maxLevel: 2,
      getTileUrl(level, col, row) {
        if (level === 0) return `${prefix}a.webp`;
        const gridSize = 2 ** level;
        const sequence = String(row * gridSize + col + 1).padStart(2, '0');
        return `${prefix}${level === 1 ? 'b' : 'c'}${sequence}.webp`;
      }
    };
  }

  const viewer = OSD({
    id: 'viewer',
    showNavigationControl: false,
    showNavigator: false,
    animationTime: 0.65,
    blendTime: 0.12,
    constrainDuringPan: false,
    visibilityRatio: 0,
    minZoomImageRatio: 0.1,
    maxZoomPixelRatio: 2,
    gestureSettingsMouse: {
      clickToZoom: false,
      dblClickToZoom: false,
      dragToPan: true,
      scrollToZoom: false
    },
    gestureSettingsTouch: {
      clickToZoom: false,
      dblClickToZoom: false,
      dragToPan: true,
      pinchToZoom: true,
      flickEnabled: false
    },
    gestureSettingsPen: { clickToZoom: false, dblClickToZoom: false, dragToPan: true },
    tileSources: []
  });

  fetch(new URL('config/map.json', moduleBase), { cache: 'no-store' })
    .then(response => {
      if (!response.ok) throw new Error(`Map configuration HTTP ${response.status}`);
      return response.json();
    })
    .then(async config => {
      if (!Array.isArray(config.regions) || !config.regions.length) {
        throw new Error('No regions found in config/map.json');
      }
      const regions = config.regions;
      const seen = new Set();
      for (const region of regions) {
        if (!Number.isInteger(region.x) || !Number.isInteger(region.y)) {
          throw new Error('All region coordinates must be integers.');
        }
        const id = `${region.x},${region.y}`;
        if (seen.has(id)) throw new Error(`Duplicate region: ${id}`);
        seen.add(id);
      }
      const minX = Math.min(...regions.map(r => r.x));
      const minY = Math.min(...regions.map(r => r.y));
      const maxX = Math.max(...regions.map(r => r.x + 1));
      const maxY = Math.max(...regions.map(r => r.y + 1));
      const margin = Math.max(0, Number(config.regionMargin) || 0);
      // No outer artwork padding for this framing experiment.
      const fitMargin = 0;
      const bounds = new OSD.Rect(minX, minY, maxX - minX, maxY - minY);
      const viewingArea = new OSD.Rect(minX - margin, minY - margin,
        maxX - minX + 2 * margin, maxY - minY + 2 * margin);
      const initialBounds = new OSD.Rect(minX - fitMargin, minY - fitMargin,
        maxX - minX + 2 * fitMargin, maxY - minY + 2 * fitMargin);

      // Add each independently tiled 4096px region in permanent world coordinates.
      // One region occupies a 1x1 unit square, including negative coordinates.
      for (const region of regions) {
        await new Promise((resolve, reject) => {
          viewer.addTiledImage({
            tileSource: regionSource(region, config.tileSize, config.regionSize),
            x: region.x,
            y: region.y,
            width: 1,
            success: resolve,
            error: event => reject(new Error(event?.message || `Failed to add x${region.x}_y${region.y}`))
          });
        });
      }

      // Keep the full-map scale available as the minimum zoom, even though
      // the visitor starts on the origin region at a closer scale.
      viewer.viewport.fitBounds(initialBounds, true);
      const homeZoom = viewer.viewport.getZoom(true);
      viewer.viewport.minZoomLevel = homeZoom;

      // Initial composition: origin region x0_y0 fills viewport HEIGHT.
      // It is okay for its width to crop on a portrait phone.
      const initialRegion = config.initialRegion || {x: 0, y: 0};
      const initialCenter = new OSD.Point(initialRegion.x + 0.5, initialRegion.y + 0.5);
      const heightScale = elementHeightZoom();
      function elementHeightZoom() {
        const container = viewer.viewport.getContainerSize();
        return container.y > 0 ? container.y / container.x : homeZoom;
      }
      // The introduction starts 4.5% wider and settles at this scale.
      const introEndZoom = Math.max(homeZoom, heightScale);
      const introStartZoom = Math.max(homeZoom, introEndZoom / 1.045);
      viewer.viewport.panTo(initialCenter, true);
      viewer.viewport.zoomTo(introStartZoom, null, true);
      viewer.viewport.maxZoomLevel = Math.max(homeZoom, viewer.viewport.imageToViewportZoom(
        Number(config.maxZoomPixelRatio) || 2));

      // Keep the viewport from drifting into unlimited empty space.
      // A view larger than the permitted extent stays centered on that axis.
      let correcting = false;
      function enforceBounds() {
        if (correcting) return;
        const view = viewer.viewport.getBounds(true);
        const center = view.getCenter();
        function clampAxis(value, extentStart, extentSize, viewportSize) {
          const lo = extentStart + viewportSize / 2;
          const hi = extentStart + extentSize - viewportSize / 2;
          return lo > hi ? extentStart + extentSize / 2 : Math.max(lo, Math.min(hi, value));
        }
        const x = clampAxis(center.x, viewingArea.x, viewingArea.width, view.width);
        const y = clampAxis(center.y, viewingArea.y, viewingArea.height, view.height);
        if (Math.abs(x - center.x) > 0.00001 || Math.abs(y - center.y) > 0.00001) {
          correcting = true;
          viewer.viewport.panTo(new OSD.Point(x, y), true);
          correcting = false;
        }
      }
      viewer.addHandler('animation', enforceBounds);
      viewer.addHandler('pan', enforceBounds);
      viewer.addHandler('zoom', enforceBounds);

      // Desired direction: wheel UP zooms IN, wheel DOWN zooms OUT.
      // Anchor zoom to pointer position on the screen.
      const element = viewer.element;
      element.addEventListener('wheel', event => {
        event.preventDefault();
        event.stopPropagation();
        const rect = element.getBoundingClientRect();
        const pointer = new OSD.Point(event.clientX - rect.left, event.clientY - rect.top);
        const worldPoint = viewer.viewport.pointFromPixel(pointer, true);
        const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? rect.height : 1);
        const delta = Math.max(-180, Math.min(180, pixels));
        const factor = Math.exp(-delta * 0.0015);
        viewer.viewport.zoomBy(factor, worldPoint);
        viewer.viewport.applyConstraints();
      }, { passive: false, capture: true });

      // Press 0 or Home to return to the entire composition; no visible control.
      document.addEventListener('keydown', event => {
        if ((event.key === '0' || event.key === 'Home') && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) {
          viewer.viewport.fitBounds(initialBounds);
        }
      });
      window.addEventListener('resize', () => {
        viewer.viewport.resize(new OSD.Point(element.clientWidth, element.clientHeight));
        enforceBounds();
      });

      // Developer reference, not a user-facing UI control.
      window.mapViewer = { viewer, config, bounds, viewingArea, homeZoom, introEndZoom, introStartZoom, initialCenter };
      window.dispatchEvent(new CustomEvent('map-ready', {detail: window.mapViewer}));
    })
    .catch(error => warn(`Map could not be initialized: ${error.message}`));
})();

from __future__ import annotations
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
import uuid
import asyncio

from ..core.database_service import DatabaseService


router = APIRouter(prefix="/api", tags=["layout"])


def get_db() -> DatabaseService:
    return DatabaseService.get_instance()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    db = get_db()
    return {
        "status": "ok",
        "is_loaded": db.is_loaded,
        "chip_bbox": db.get_chip_bbox(),
    }


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    db = get_db()
    result = {
        "is_loaded": db.is_loaded,
        "chip_bbox": db.get_chip_bbox(),
        "layers": db.get_layer_info(),
    }
    if db.is_loaded:
        d = db.db
        result["stats"] = {
            "total_components": d.total_components,
            "total_pins": d.total_pins,
            "total_nets": d.total_nets,
            "total_routing_segments": d.total_routing_segments,
        }
    return result


@router.post("/upload")
async def upload_files(
    lef_file: UploadFile = File(...),
    def_file: UploadFile = File(...),
) -> Dict[str, Any]:
    db = get_db()
    task_id = uuid.uuid4().hex

    lef_data = await lef_file.read()
    def_data = await def_file.read()

    lef_path = db.save_uploaded_file(lef_file.filename or "design.lef", lef_data)
    def_path = db.save_uploaded_file(def_file.filename or "design.def", def_data)

    asyncio.create_task(db.parse_lef_def_async(lef_path, def_path, task_id))

    return {
        "task_id": task_id,
        "message": "Parsing started",
        "lef_size": len(lef_data),
        "def_size": len(def_data),
    }


@router.get("/progress/{task_id}")
async def get_parse_progress(task_id: str) -> Dict[str, Any]:
    db = get_db()
    progress = db.get_progress(task_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Task not found")
    return progress


@router.post("/demo")
async def generate_demo_design() -> Dict[str, Any]:
    db = get_db()
    task_id = uuid.uuid4().hex

    from ..demo import generate_demo_lef_def
    lef_path, def_path = generate_demo_lef_def()

    asyncio.create_task(db.parse_lef_def_async(lef_path, def_path, task_id))

    return {
        "task_id": task_id,
        "message": "Demo design generation started",
    }


@router.get("/layers")
async def get_layers() -> Dict[str, Any]:
    db = get_db()
    if not db.is_loaded:
        return {"layers": [], "is_loaded": False}
    return {
        "is_loaded": True,
        "layers": db.get_layer_info(),
        "chip_bbox": db.get_chip_bbox(),
    }


@router.get("/chip")
async def get_chip_info() -> Dict[str, Any]:
    db = get_db()
    if not db.is_loaded:
        return {"is_loaded": False}
    return {
        "is_loaded": True,
        "chip_bbox": db.get_chip_bbox(),
        "layers": db.get_layer_info(),
        "stats": {
            "total_components": db.db.total_components,
            "total_pins": db.db.total_pins,
            "total_nets": db.db.total_nets,
            "total_routing_segments": db.db.total_routing_segments,
        },
    }


@router.get("/tile")
async def get_tile(
    x: float = Query(..., description="Tile left X coordinate"),
    y: float = Query(..., description="Tile bottom Y coordinate"),
    w: float = Query(..., description="Tile width"),
    h: float = Query(..., description="Tile height"),
    layers: Optional[str] = Query(None, description="Comma-separated layer names to include"),
    max_per_layer: Optional[int] = Query(20000, ge=1, le=100000),
) -> Dict[str, Any]:
    db = get_db()
    if not db.is_loaded:
        raise HTTPException(status_code=404, detail="No design loaded")

    layer_list = None
    if layers:
        layer_list = [l.strip() for l in layers.split(",") if l.strip()]

    result = db.get_tile_flattened(x, y, w, h, layer_list, max_per_layer)
    return result


@router.get("/tile-raw")
async def get_tile_raw(
    x: float = Query(...),
    y: float = Query(...),
    w: float = Query(...),
    h: float = Query(...),
    layers: Optional[str] = Query(None),
    max_results: Optional[int] = Query(None, ge=1, le=100000),
) -> Dict[str, Any]:
    db = get_db()
    if not db.is_loaded:
        raise HTTPException(status_code=404, detail="No design loaded")

    layer_list = None
    if layers:
        layer_list = [l.strip() for l in layers.split(",") if l.strip()]

    result = db.get_tile(x, y, w, h, layer_list, max_results)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/drc/run")
async def run_drc() -> Dict[str, Any]:
    db = get_db()
    if not db.is_loaded:
        raise HTTPException(status_code=404, detail="No design loaded")

    try:
        result = await asyncio.to_thread(db.run_drc)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drc/violations")
async def get_drc_violations(
    x: float = Query(..., description="Viewport left X"),
    y: float = Query(..., description="Viewport bottom Y"),
    w: float = Query(..., description="Viewport width"),
    h: float = Query(..., description="Viewport height"),
    max_results: Optional[int] = Query(5000, ge=1, le=50000),
) -> Dict[str, Any]:
    db = get_db()
    if not db.is_loaded:
        raise HTTPException(status_code=404, detail="No design loaded")

    if not db.get_drc_result():
        return {"violations": [], "total": 0, "in_viewport": 0, "needs_run": True}

    return db.get_drc_violations_tile(x, y, w, h, max_results)


@router.get("/drc/status")
async def get_drc_status() -> Dict[str, Any]:
    db = get_db()
    result = db.get_drc_result()
    if not result:
        return {"has_result": False, "is_loaded": db.is_loaded}
    return {
        "has_result": True,
        "is_loaded": db.is_loaded,
        "total_violations": len(result.violations),
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
    }


@router.post("/clear")
async def clear_design() -> Dict[str, Any]:
    db = get_db()
    db.clear()
    return {"status": "cleared"}

# Demo Backend API
import json
import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile

from src.trust_engine.pipeline import load_from_data_team, run_pipeline


app = FastAPI(
    title="OBS Trust Engine Demo API",
    version="0.1.0"
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    接收数据组输出的 result.json，
    送入 Trust Engine，
    返回 ReliabilityResult。
    """

    try:
        contents = await file.read()
        raw = json.loads(contents.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON file"
        )

    temp_path = None

    try:
        # pipeline.py 目前通过文件路径读取 JSON，
        # 所以先临时保存上传的 JSON
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8"
        ) as temp_file:
            json.dump(raw, temp_file)
            temp_path = temp_file.name

        # 使用现有 pipeline 的读取逻辑
        data = load_from_data_team(temp_path)

        # 调用完整 Trust Engine
        result = run_pipeline(
            metadata=data["metadata"],
            quality=data["quality"],
            profiles=data["profiles"],
            predictions=data["predictions"],
            adapter_statuses=data["adapter_statuses"],
        )

        # 返回 JSON 给前端
        return json.loads(result.to_json())

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

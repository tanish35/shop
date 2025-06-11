import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from utils.generate_report import REPORTS, generate_report

# from app.routes.tasks import homepage as task_homepage

router = APIRouter(tags=["common"])


# @router.get("/", response_class=HTMLResponse)
# async def homepage(request: Request):
# return await task_homepage(request=request)


@router.get("/")
async def homepage():
    return "Server is running"


@router.post("/trigger-report")
async def trigger_report():
    report_id = str(uuid.uuid4())
    REPORTS[report_id] = {"status": "Running"}
    # Background task to avoid blocking
    import asyncio

    asyncio.create_task(generate_report(report_id))
    return {"report_id": report_id}


@router.get("/get-report")
async def get_report(report_id: str):
    report = REPORTS.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report["status"] == "Running":
        return {"status": "Running"}

    return FileResponse(path=report["path"], filename=f"store_report_{report_id}.csv", media_type="text/csv")

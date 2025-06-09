from fastapi import APIRouter

# from app.routes.tasks import homepage as task_homepage

router = APIRouter(tags=["common"])


# @router.get("/", response_class=HTMLResponse)
# async def homepage(request: Request):
    # return await task_homepage(request=request)

@router.get("/")
async def homepage():
    return "Server is running"

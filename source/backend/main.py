from fastapi import FastAPI

from routers import (
    debts,
    dops,
    groups,
    schedules,
    subjects,
    users,
    user_subjects,
    auth_router
)

app = FastAPI(title="My API", version="0.1.0")


@app.get("/", tags=["Health"], summary="Проверка работы API")
async def root():
    return {"status": "OK"}


app.include_router(debts.router, prefix="/debts", tags=["Debts"])
app.include_router(dops.router, prefix="/dops", tags=["Dops"])
app.include_router(groups.router, prefix="/groups", tags=["Groups"])
app.include_router(schedules.router, prefix="/schedules", tags=["Schedules"])
app.include_router(subjects.router, prefix="/subjects", tags=["Subjects"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(user_subjects.router, prefix="/user-subjects", tags=["User-Subjects"])
app.include_router(auth_router.router, prefix="/auth", tags=["Auth"])
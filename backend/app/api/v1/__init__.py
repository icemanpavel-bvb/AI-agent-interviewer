"""Сборка роутеров v1."""

from fastapi import APIRouter

from . import applications, auth, demo, interview, reports, vacancies

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(vacancies.router, prefix="/vacancies", tags=["vacancies"])
router.include_router(applications.router, prefix="/applications", tags=["applications"])
router.include_router(reports.router, prefix="/applications", tags=["reports"])
router.include_router(interview.router, prefix="/interview", tags=["interview"])
# Эндпоинты демо сами проверяют DEMO_MODE (require_demo) и при выключенном режиме отвечают 404.
router.include_router(demo.router, prefix="/demo", tags=["demo"])

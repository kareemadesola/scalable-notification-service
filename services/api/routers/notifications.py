from fastapi import APIRouter

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("")
async def create_notification():
    # Phase 2
    pass


@router.get("/{notification_id}")
async def get_notification(notification_id: int):
    # Phase 2
    pass


@router.patch("/{notification_id}")
async def update_notification(notification_id: int):
    # Phase 2
    pass

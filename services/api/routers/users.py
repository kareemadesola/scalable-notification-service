from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/{user_id}/notifications")
async def get_user_notifications(user_id: str):
    # Phase 2
    pass


@router.get("/{user_id}/preferences")
async def get_user_preferences(user_id: str):
    # Phase 2
    pass


@router.put("/{user_id}/preferences")
async def update_user_preferences(user_id: str):
    # Phase 2
    pass

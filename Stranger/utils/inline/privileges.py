from typing import Dict, List
from pyrogram.types import InlineKeyboardButton
from config import ACCESS_TOKEN_PLAN_1, ACCESS_TOKEN_PLAN_2, DOWNLOAD_PLAN_1, DOWNLOAD_PLAN_2
from Stranger.utils.helper import get_readable_time


def privileges_panel(user: Dict[str, str], user_id: int) -> List[List[InlineKeyboardButton]]:
    def create_plan_button(plan_type: str, plan_duration: int, current_plan: str, plan_name: str) -> InlineKeyboardButton:
        is_selected = current_plan == plan_name
        duration_text = get_readable_time(plan_duration) if plan_duration else "None"
        text = f"{duration_text}{'✅' if is_selected else ''}"
        callback = "dummy" if is_selected else f"update_up|{user_id}|{plan_type}|{plan_name}"
        return InlineKeyboardButton(text, callback_data=callback)

    btn = [
        [InlineKeyboardButton("𝖠𝖢𝖢𝖤𝖲𝖲𝖪𝖤𝖸 ", callback_data="dummy")],
        [
            create_plan_button("token", 0, user['token_plan'],'None'),
            create_plan_button("token", ACCESS_TOKEN_PLAN_1, user['token_plan'], "plan1"),
            create_plan_button("token", ACCESS_TOKEN_PLAN_2, user['token_plan'], "plan2")
        ],
        [InlineKeyboardButton("𝖣𝖮𝖶𝖭𝖫𝖮𝖠𝖣 ", callback_data="dummy")],
        [
            create_plan_button("download", 0, user["download_plan"], "None"),
            create_plan_button("download", DOWNLOAD_PLAN_1, user['download_plan'], "plan1"),
            create_plan_button("download", DOWNLOAD_PLAN_2, user['download_plan'], "plan2")
        ],
        [
            InlineKeyboardButton(
                "𝘉𝘈𝘕" if not user['is_banned'] else "𝘜𝘕𝘉𝘈𝘕",
                callback_data=f"update_up|{user_id}|{'ban' if not user['is_banned'] else 'unban'}"
            )
        ],
        [InlineKeyboardButton(text="𝘊𝘭𝘰𝘴𝘦 ", callback_data="pv_close")]
    ]
    
    return btn

from typing import Union

from pyrogram.types import InlineKeyboardButton

def setting_markup(data: dict):
    buttons = [
        [
            InlineKeyboardButton(
                text="𝖠𝗎𝗍𝗈 𝖠𝗉𝗉𝗋𝗈𝗏𝖺𝗅 ", callback_data="auto_approval_setting"
            ),
            InlineKeyboardButton(
                text="✅" if data['auto_approval'] else "❌", callback_data="auto_approval_toggle"
            ),
        ],
        [
            InlineKeyboardButton(
                text="𝖤𝖺𝗋𝗂𝗇𝗀 𝖬𝗈𝖽𝖾", callback_data="access_token_setting"
            ),
            InlineKeyboardButton(
                text="✅" if data['access_token'] else "❌", callback_data="access_token_toggle"
            ),
        ],
        [
            InlineKeyboardButton(
                text="𝖫𝖮𝖦𝖲 𝖢𝗁𝖺𝗇𝗇𝖾𝗅", callback_data="logs_panel"
                ),
            InlineKeyboardButton(
                text="✅" if data['logs'] else "❌", callback_data="logs_channel_toggle"
            )
        ],
        [
            InlineKeyboardButton(
                text="𝖳𝗁𝗎𝗆𝖻𝗇𝖺𝗂𝗅", callback_data="thumbnail_panel"
            ),
            InlineKeyboardButton(
                text="✅" if data['thumbnail'] else "❌", callback_data="thumbnail_toggle"
            )
        ],
        [
            InlineKeyboardButton("Promotion", callback_data="set_promotion"),
            InlineKeyboardButton(
                text="✅" if data['promotion'] else "❌", callback_data="promotion_toggle"
            )
        ],
        [
            InlineKeyboardButton(
                text="𝖬𝗎𝗅𝗍𝗂𝗉𝗅𝖾 𝖡𝗈𝗍𝗌", callback_data="bot_management"
            ),
        ],
        [
            InlineKeyboardButton(
                text="𝖢𝗅𝗈𝗌𝖾",
                callback_data="close"
            )
        ]
    ]
    return buttons


def bot_management_panel(bots:list):
    btn = []
    row = []
    for bot in bots:
        row.append(InlineKeyboardButton(text=f"@{bot['username']}", callback_data=f"bot_setting|{bot['username']}"))
        if len(row) == 2:
            btn.append(row)
            row = []
    if row:
        btn.append(row)
    btn.append(
        [InlineKeyboardButton(text="𝖡𝖺𝖼𝗄", callback_data=f"settings_back_helper"),
        InlineKeyboardButton(text="𝖢𝗅𝗈𝗌𝖾",callback_data="close")]
    )
    return btn

def bot_setting_panel(bot_info):
    
    btn = [
            [InlineKeyboardButton(
                text="Enabled {}".format("✅") if bot_info['is_active'] else "Enabled", 
                callback_data=f"bot_status | {bot_info['username']} |active" if not bot_info['is_active'] else "dummy")
                ],
            [InlineKeyboardButton(
                text="Disabled {}".format("✅") if not bot_info['is_active'] else "Disabled", 
                callback_data=f"bot_status | {bot_info['username']} | inactive" if bot_info['is_active'] else "dummy")
                ],
            [InlineKeyboardButton(
                text="Delete This Bot", 
                callback_data=f"bot_status | {bot_info['username']} | delete" )
                ],
            [InlineKeyboardButton(text="𝖡𝖺𝖼𝗄", callback_data=f"bot_management"),
            InlineKeyboardButton(text="𝖢𝗅𝗈𝗌𝖾",callback_data="close")]
        ]
    
    return btn

def auto_approval_setting_panel(data:dict):
    btn = [
        [InlineKeyboardButton(text="𝖶𝖾𝗅𝖼𝗈𝗆𝖾 𝖬𝖲𝖦",callback_data="dummy"),
         InlineKeyboardButton(text="✅" if data['welcome'] else "❌",callback_data="ap_setting_toggle | welcome")],
         [InlineKeyboardButton(text="𝖫𝖾𝖺𝗏𝖾 𝖬𝖲𝖦", callback_data="dummy"),
          InlineKeyboardButton(text="✅" if data['leave'] else "❌" ,callback_data="ap_setting_toggle | leave")]
         ]
    btn.append(
        [InlineKeyboardButton(text="𝖡𝖺𝖼𝗄", callback_data=f"settings_back_helper"),
         InlineKeyboardButton(text="𝖢𝗅𝗈𝗌𝖾",callback_data="close")]
    )
    return btn

def access_token_setting_panel(data:dict):
    btn = [
        [InlineKeyboardButton(text="𝖯𝖺𝗒𝗆𝖾𝗇𝗍 𝖦𝖾𝗍𝖺𝗐𝖺𝗒 ",callback_data="dummy"),
        InlineKeyboardButton(text="✅" if data['payment_gateway'] else "❌",callback_data="at_setting_toggle | payment_gateway")],
        [InlineKeyboardButton(text="𝖣𝗈𝗐𝗇𝗅𝗈𝖺𝖽 ",callback_data="dummy"),
        InlineKeyboardButton(text="✅" if data['downloads'] else "❌",callback_data="at_setting_toggle | downloads")],
        [InlineKeyboardButton(text="𝖶𝖺𝗍𝖼𝗁 𝖠𝖣𝖲",callback_data="dummy"),
        InlineKeyboardButton(text="✅" if data['url_shortner'] else "❌" ,callback_data="at_setting_toggle | url_shortner")]
        ]
    btn.append(
        [InlineKeyboardButton(text="𝖡𝖺𝖼𝗄", callback_data=f"settings_back_helper"),
         InlineKeyboardButton(text="𝖢𝗅𝗈𝗌𝖾",callback_data="close")]
    )
    return btn

def thumbnail_panel_markup(data):
    btn = [
        [
            InlineKeyboardButton(text="𝖯𝗂𝖼𝗍𝗎𝗋𝖾 1 ✅" if data=="type1" else "𝖯𝗂𝖼𝗍𝗎𝗋𝖾 1", callback_data="thumbnail_type | type1" if data != "type1" else "dummy"),
            InlineKeyboardButton(text="𝖯𝗂𝖼𝗍𝗎𝗋𝖾 2 ✅" if data=="type2" else "𝖯𝗂𝖼𝗍𝗎𝗋𝖾 2", callback_data="thumbnail_type | type2" if data != "type2" else "dummy"),
        ],
        [
            InlineKeyboardButton(text="𝖠𝗎𝗍𝗈 ✅" if data=="auto" else "𝖠𝗎𝗍𝗈", callback_data="thumbnail_type | auto" if data != "auto" else "dummy"),
        ]
    ]
    btn.append(
        [
            InlineKeyboardButton(text="𝖡𝖺𝖼𝗄", callback_data=f"settings_back_helper"),
            InlineKeyboardButton(text="𝖢𝗅𝗈𝗌𝖾", callback_data="close")
            ]
            )
    return btn

def logs_panel_markup(data):
    btn = [
        [
            InlineKeyboardButton(text="𝖫𝖮𝖦𝖲 1 ✅" if data=='logs1' else "LOGS1",
            callback_data="logs_setting_toggle | logs1" if data != 'logs1' else "dummy"),
            InlineKeyboardButton(text="𝖫𝖮𝖦𝖲 2 ✅" if data=='logs2' else "LOGS2",
            callback_data="logs_setting_toggle | logs2" if data != 'logs2' else "dummy"),
            InlineKeyboardButton(text="𝖡𝖮𝖳𝖧 ✅" if data=='both' else "BOTH",
            callback_data="logs_setting_toggle | both" if data != 'both' else "dummy"),
        ]
    ]
    btn.append(
        [
            InlineKeyboardButton(text="𝖡𝖺𝖼𝗄", callback_data=f"settings_back_helper"),
            InlineKeyboardButton(text="𝖢𝗅𝗈𝗌𝖾", callback_data="close")
            ]
            )
    return btn

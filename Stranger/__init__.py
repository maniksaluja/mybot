from .logger import LOGGER

# Initialize components when the module is imported
from .core.bot import StrangerBot
from .core.shortner import Shortner
from .core.userbot import Userbot
from .misc import sudo
from config import SHORTLINK_API, SHORTLINK_URL

# loading sudoers from database
sudo()

# starting bot 
app = StrangerBot()
userbot = Userbot()
shotner = Shortner(api_key=SHORTLINK_API, base_site=SHORTLINK_URL)

# Export for other modules to import
__all__ = ['app', 'userbot', 'shotner', 'LOGGER']
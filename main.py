import glob
import json
import os
import re
import time
from configparser import *

from discord.ext import commands
from loguru import logger

from cogs.utils.checks import is_bot_owner_check

#initiate logger test
logger.add(f"file_{str(time.strftime('%Y%m%d-%H%M%S'))}.log", rotation="500 MB")

auth = ConfigParser()
auth.read('auth.ini')  # All my usernames and passwords for the api

def load_cogs(folder):
    os.chdir(folder)
    files = []
    for file in glob.glob("*.py"):
        file = re.search('^([A-Za-z1-9]{1,})(?:.py)$', file).group(1)
        files.append(file)
    return files


def config():
    with open('config.json', 'r') as f:
        config = json.load(f)
        return config
# bot_config = config()
bot = commands.Bot(command_prefix=auth.get('discord', 'PREFIX'))

@bot.event
async def on_ready():
    """
    When bot is ready and online it prints that its online
    :return:
    """
    logger.debug("Bot is ready!")


@bot.command()
@is_bot_owner_check()
async def load(ctx, extension):
    try:
        bot.load_extension('cogs.' + extension)
        logger.debug(f'Loaded {extension}')
        await ctx.send(f'Loaded {extension}')
    except Exception as error:
        logger.exception(f"Extension {extension} could not be loaded. [{error}]")


@bot.command()
@is_bot_owner_check()
async def reload(ctx, extension):
    try:
        bot.unload_extension('cogs.' + extension)
        bot.load_extension('cogs.' + extension)
        logger.debug(f'Reloaded {extension}')
        await ctx.send(f'Reloaded {extension}')
    except Exception as error:
        logger.exception(f"Extension {extension} could not be reloaded. [{error}]")


@bot.command()
@is_bot_owner_check()
async def unload(ctx, extension):
    try:
        bot.unload_extension('cogs.' + extension)
        logger.debug(f'Unloaded {extension}')
        await ctx.send(f'{extension} successfully unloaded')
    except Exception as error:
        logger.exception(f"Extension {extension} could not be unloaded. [{error}]")


if __name__ == "__main__":
    bot.remove_command('help')
    extensions = load_cogs('cogs')
    for extension in extensions:
        try:
            bot.load_extension('cogs.'+extension)
            logger.debug(f'Loaded {extension} cog.')
        except Exception as error:
            logger.exception(f"Extension {extension} could not be loaded. [{error}]")
    logger.info(str(bot.guilds) + "Peribot is apart of")
    bot.run(auth.get('discord', 'TOKEN'))

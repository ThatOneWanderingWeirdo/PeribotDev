from discord.ext import commands
import discord
import json
from loguru import logger

class Welcome():
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setwelcome", pass_context=True)
    async def setwelcome(self, ctx):
        """
        Sets the channel where welcome messages are sent
        :param ctx:
        :return:
        """
        try:
            channel = ctx.message.channel.id
            with open('data/welcome/info.json', 'r+') as f:
                data = json.load(f)
                data['channel_id'] = str(channel)  # <--- add `id` value.
                f.seek(0)  # <--- should reset file position to the beginning.
                json.dump(data, f, indent=4)
                f.truncate()  # remove remaining part
            await self.bot.send_message(channel ,"Welcome channel set!")
        except Exception as e:
            logger.error(e)
            pass

    async def on_member_join(self, member):
        with open('data/welcome/info.json', 'r') as f:
            data = json.load(f)
            channel = data['channel_id']
        try:
            await self.bot.send_message(channel ,f":balloon: Hey! Listen! {member} is here! :100:")
        except Exception as e:
            await self.bot.send_message(member.server.owner,
                                        "There is an error with a newcomer, please report this to the creator.\n {}".format(
                                            e))


def setup(bot):
    bot.add_cog(Welcome(bot))
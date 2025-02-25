import os

import discord
from discord.ext import commands

from .utils.dataIO import dataIO


class Star(commands.Cog):
    """Quote board"""

    def __init__(self, bot):
        self.bot = bot
        self.settings = dataIO.load_json("data/star/settings.json")

    async def save_settings(self):
        return dataIO.save_json("data/star/settings.json", self.settings)

    async def cog_before_invoke(self, ctx):
        if not os.path.exists('data/star'):
            os.mkdir('data/star')
        data = {}
        f = 'data/star/settings.json'
        if not os.path.exists(f):
            dataIO.save_json(f, data)

    @commands.group()
    @commands.has_permissions(manage_channels=True)
    async def starboard(self, ctx):
        """Commands for managing the starboard"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Thats not how you use this command. Use !help starboard for more info")

    @starboard.group(name="role", aliases=["roles"])
    async def _roles(self, ctx):
        """Add or remove roles allowed to add to the starboard"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Thats not how you use this command. Use !help roles for more info")

    async def get_everyone_role(self, guild):
        for role in guild.roles:
            if role.is_default():
                return role

    async def check_guild_emojis(self, guild, emoji):
        guild_emoji = None
        for emojis in guild.emojis:
            if str(emojis.id) in emoji:
                guild_emoji = emojis
        return guild_emoji

    @starboard.command(name="setup", aliases=["set"])
    async def setup_starboard(self, ctx, channel: discord.TextChannel = None, emoji="⭐",
                              role: discord.Role = None):
        """Sets the starboard channel, emoji and role"""
        guild = ctx.guild
        guild_id = str(guild.id)
        if channel is None:
            channel = ctx.channel
        if "<" in emoji and ">" in emoji:
            emoji = await self.check_guild_emojis(guild, emoji)
            if emoji is None:
                await ctx.send("That emoji is not on this server!")
                return
            else:
                emoji = ":" + emoji.name + ":" + emoji.id

        if role is None:
            role = await self.get_everyone_role(guild)
        self.settings[guild_id] = {"emoji": emoji,
                                    "channel": str(channel.id),
                                    "role": [str(role.id)],
                                    "threshold": 0,
                                    "messages": [],
                                    "ignore": []}
        await self.save_settings()
        await ctx.send("Starboard set to {}".format(channel.mention))

    @starboard.command(name="clear")
    async def clear_post_history(self, ctx):
        """Clears the database of previous starred messages"""
        self.settings[str(ctx.guild.id)]["messages"] = []
        await self.save_settings()
        await ctx.send("Done! I will no longer track starred messages older than right now.")

    @starboard.command(name="ignore")
    async def toggle_channel_ignore(self, ctx, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel
        if str(channel.id) in self.settings[str(ctx.guild.id)]["ignore"]:
            self.settings[str(ctx.guild.id)]["ignore"].remove(channel.id)
            await ctx.send("{} removed from the ignored channel list!".format(
                                            channel.mention))
        else:
            self.settings[str(ctx.guild.id)]["ignore"].append(str(channel.id))
            await ctx.send("{} added to the ignored channel list!".format(
                                            channel.mention))
        await self.save_settings()

    @starboard.command(name="emoji")
    async def set_emoji(self, ctx, emoji="⭐"):
        """Set the emoji for the starboard defaults to ⭐"""
        guild = ctx.guild
        if str(guild.id) not in self.settings:
            await ctx.send("I am not setup for the starboard on this server!\
                                         \nuse starboard set to set it up.")
            return
        is_guild_emoji = False
        if "<" in emoji and ">" in emoji:
            emoji = await self.check_guild_emojis(guild, emoji)
            if emoji is None:
                await ctx.send("That emoji is not on this server!")
                return
            else:
                is_guild_emoji = True
                emoji = ":" + emoji.name + ":" + emoji.id
        self.settings[str(guild.id)]["emoji"] = emoji
        await self.save_settings()
        if is_guild_emoji:
            await ctx.send("Starboard emoji set to <{}>.".format(emoji))
        else:
            await ctx.send("Starboard emoji set to {}.".format(emoji))

    @starboard.command(name="channel")
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel for the starboard"""
        guild = ctx.guild
        if str(guild.id) not in self.settings:
            await ctx.send("I am not setup for the starboard on this server!\
                                         \nuse starboard set to set it up.")
            return
        if channel is None:
            channel = ctx.channel
        self.settings[str(guild.id)]["channel"] = channel.id
        await self.save_settings()
        await ctx.send(f"Starboard channel set to {channel.mention}.")

    @starboard.command(name="threshold")
    async def set_threshold(self, ctx, threshold: int = 0):
        """Set the threshold before posting to the starboard"""
        guild = ctx.guild
        if str(guild.id) not in self.settings:
            await ctx.send(
                                        "I am not setup for the starboard on this server!\
                                         \nuse starboard set to set it up.")
            return
        self.settings[str(guild.id)]["threshold"] = threshold
        await self.save_settings()
        await ctx.send(f"Starboard threshold set to {threshold}.")

    @_roles.command(name="add")
    async def add_role(self, ctx, role: discord.Role = None):
        """Add a role allowed to add messages to the starboard defaults to @everyone"""
        guild = ctx.guild
        if str(guild.id) not in self.settings:
            await ctx.send(
                                        "I am not setup for the starboard on this server!\
                                         \nuse starboard set to set it up.")
            return
        everyone_role = await self.get_everyone_role(guild)
        if role is None:
            role = everyone_role
        if role.id in self.settings[str(guild.id)]["role"]:
            await ctx.send(
                                        "{} can already add to the starboard!".format(role.name))
            return
        if everyone_role.id in self.settings[str(guild.id)]["role"] and role != everyone_role:
            self.settings[str(guild.id)]["role"].remove(everyone_role.id)
        self.settings[str(guild.id)]["role"].append(role.id)
        await self.save_settings()
        await ctx.send(
                                    "Starboard role set to {}.".format(role.name))

    @_roles.command(name="remove", aliases=["del", "rem"])
    async def remove_role(self, ctx, role: discord.Role):
        """Remove a role allowed to add messages to the starboard"""
        guild = ctx.guild
        everyone_role = await self.get_everyone_role(guild)
        if str(role.id) in self.settings[str(guild.id)]["role"]:
            self.settings[str(guild.id)]["role"].remove(role.id)
        if self.settings[str(guild.id)]["role"] == []:
            self.settings[str(guild.id)]["role"].append(everyone_role.id)
        await self.save_settings()
        await ctx.send(
                                    "{} removed from starboard.".format(role.name))

    async def check_roles(self, user, author, guild):
        """Checks if the user is allowed to add to the starboard
           Allows bot owner to always add messages for testing
           disallows users from adding their own messages"""
        has_role = False
        for role in user.roles:
            if str(role.id) in self.settings[str(guild.id)]["role"]:
                has_role = True
        if user is author:
            has_role = False
        if user.id == 204792579881959424:
            has_role = True
        return has_role

    async def check_is_posted(self, guild, message):
        """
        Check if message is in the starboard
        :param guild: Discord server
        :param message: message that was stared
        :return:
        """
        is_posted = False
        for past_message in self.settings[str(guild.id)]["messages"]:
            if int(message.id) == past_message["original_message"] and past_message["new_message"] is not None:
                is_posted = True
        return is_posted

    async def check_is_added(self, guild, message):
        """
        Check if message is being tracked
        :param guild: 
        :param message: 
        :return: 
        """
        is_posted = False
        for past_message in self.settings[str(guild.id)]["messages"]:
            if str(message.id) == past_message["original_message"]:
                is_posted = True
        return is_posted

    async def get_count(self, guild, message):
        """
        get the number of stars on this message as stored in file
        :param guild:
        :param message:
        :return:
        """
        count = 0
        for past_message in list(self.settings[str(guild.id)]["messages"]):
            if int(message.id) == past_message["original_message"]:
                count = past_message["count"]
        return count

    async def get_posted_message(self, guild, message):
        """
        Get the message ID and count of the starboard embed or return None
        Also increment the count and save the count
        :param guild: Discord Server
        :param message: Message that was reacted to
        :return:
        """
        msg_list = self.settings[str(guild.id)]["messages"]
        for past_message in msg_list:
            if int(message.id) == past_message["original_message"]:
                msg = past_message
                msg_list.remove(msg)
                msg["count"] += 1
                msg_list.append(msg)
                self.settings[str(guild.id)]["messages"] = msg_list
                await self.save_settings()
                return past_message["new_message"], past_message["count"]
        return None, None

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        guild = reaction.message.guild
        msg = reaction.message
        guid_id = str(guild.id)
        if guid_id not in self.settings:
            return
        if str(msg.channel.id) in self.settings[guid_id]["ignore"]:
            return
        if not await self.check_roles(user, msg.author, guild):
            return
        react = self.settings[guid_id]["emoji"]
        if react in str(reaction.emoji):
            threshold = self.settings[guid_id]["threshold"]
            count = await self.get_count(guild, msg) + 1 # add one here in case its not posted to starboard
            if await self.check_is_posted(guild, msg): # check if stared message is in starboard
                channel = reaction.message.guild.get_channel(int(self.settings[guid_id]["channel"]))
                msg_id, count = await self.get_posted_message(guild, msg) # Count has been incremented
                if msg_id is not None:
                    msg_edit = await channel.fetch_message(id=int(msg_id))
                    await msg_edit.edit(content=f"{reaction.emoji} **#{count}**")
                    return
            if count < threshold and threshold != 0:
                store = {"original_message": msg.id, "new_message": None, "count": count}
                has_message = None
                for message in self.settings[guid_id]["messages"]:
                    if msg.id == message["original_message"]:
                        has_message = message
                if has_message is not None:
                    self.settings[guid_id]["messages"].remove(has_message)
                    self.settings[guid_id]["messages"].append(store)
                    await self.save_settings()
                else:
                    self.settings[guid_id]["messages"].append(store)
                    await self.save_settings()
                return
            author = reaction.message.author
            channel = reaction.message.channel
            starboard_channel = self.bot.get_channel(int(self.settings[guid_id]["channel"]))
            if reaction.message.embeds != []:
                embed = reaction.message.embeds[0]  # .to_dict()
                # print(embed)
                em = discord.Embed(timestamp=reaction.message.timestamp)
                if "title" in embed:
                    em.title = embed["title"]
                if "thumbnail" in embed:
                    em.set_thumbnail(url=embed["thumbnail"]["url"])
                if "description" in embed:
                    em.description = msg.clean_content + "\n\n" + embed["description"]
                if "description" not in embed:
                    em.description = msg.clean_content
                if "url" in embed:
                    em.url = embed["url"]
                if "footer" in embed:
                    em.set_footer(text=embed["footer"]["text"])
                if "author" in embed:
                    postauthor = embed["author"]
                    if "icon_url" in postauthor:
                        if author.nick != None:
                            em.set_author(name=author.nick, icon_url=author.avatar_url)
                        else:
                            em.set_author(name=author.name, icon_url=author.avatar_url)
                    else:
                        if author.nick != None:
                            em.set_author(name=author.nick)
                        else:
                            em.set_author(name=author.name)
                if "author" not in embed:
                    if author.nick != None:
                        em.set_author(name=author.nick, icon_url=author.avatar_url)
                    else:
                        em.set_author(name=author.name, icon_url=author.avatar_url)
                if "color" in embed:
                    em.color = embed["color"]
                if "color" not in embed:
                    em.color = author.top_role.color
                if "image" in embed:
                    em.set_image(url=embed["image"]["url"])
                if embed["type"] == "image":
                    em.type = "image"
                    if ".png" in embed["url"] or ".jpg" in embed["url"]:
                        em.set_thumbnail(url="")
                        em.set_image(url=embed["url"])
                    else:
                        em.set_thumbnail(url=embed["url"])
                        em.set_image(
                            url=embed["url"] + "." + embed["thumbnail"]["url"].rsplit(".")[-1])
                if embed["type"] == "gifv":
                    em.type = "gifv"
                    em.set_thumbnail(url=embed["url"])
                    em.set_image(url=embed["url"] + ".gif")
            else:
                em = discord.Embed(timestamp=reaction.message.created_at)
                em.color = author.top_role.color
                em.description = msg.content
                if author.nick != None:
                    em.set_author(name=author.nick, icon_url=author.avatar_url)
                else:
                    em.set_author(name=author.name, icon_url=author.avatar_url)
                if reaction.message.attachments != []:
                    em.set_image(url=reaction.message.attachments[0].url)
            em.set_footer(text='{} | {}'.format(channel.guild.name, channel.name))
            post_msg = await starboard_channel.send("{} **#{}**".format(reaction.emoji, count),
                                                   embed=em)
            past_message_list = self.settings[guid_id]["messages"]
            past_message_list.append({"original_message": msg.id, "new_message": post_msg.id, "count": count})
            await self.save_settings()
        else:
            return

    # @commands.Cog.listener()
    # async def on_reaction_remove(self, reaction, user):
    #     guild = reaction.message.guild
    #     msg = reaction.message
    #     guid_id = str(guild.id)
    #     if guid_id not in self.settings:
    #         return # server not setup
    #     if str(msg.channel.id) in self.settings[guid_id]["ignore"]:
    #         return # ignored channel
    #     react = self.settings[guid_id]["emoji"]
    #     if react not in str(reaction.emoji):
    #         return
    #     threshold = self.settings[guid_id]["threshold"]
    #     if await self.check_is_posted(guild, msg):
    #         starboard_channel = self.bot.get_channel(int(self.settings[guid_id]["channel"]))
    #         starboard_msg_id, count = await self.get_posted_message(guild, msg)
    #         count -= 1 # counter the increment done by self.get_posted_message
    #         if starboard_msg_id is not None and starboard_channel is not None: # msg is in the starboard
    #             msg = await starboard_channel.fetch_message(id=int(starboard_msg_id)) # get message from starboard
    #             count -= 1
    #             if count < threshold: # this should remove the message from starboard but keep it in the file
    #                 has_message = None
    #                 for message in self.settings[guid_id]["messages"]: # find msg stored in list
    #                     if reaction.message.id == message["original_message"]:
    #                         has_message = message
    #                         break
    #                 if has_message is not None:
    #                     self.settings[guid_id]["messages"].remove(has_message)
    #                     message['count'] = count
    #                     message['new_message'] = None
    #                     self.settings[guid_id]["messages"].append(message)
    #                     await self.save_settings()
    #                     await msg.delete()
    #             else:
    #                 await msg.edit(content=f"{reaction.emoji} **#{count}**")
    #                 store = {"original_message": reaction.message.id, "new_message": msg.id, "count": count}
    #                 has_message = None
    #                 for message in self.settings[guid_id]["messages"]:
    #                     if reaction.message.id == message["original_message"]:
    #                         has_message = message
    #                 if has_message is not None:
    #                     self.settings[guid_id]["messages"].remove(has_message)
    #                     self.settings[guid_id]["messages"].append(store)
    #                     await self.save_settings()


def setup(bot):
    bot.add_cog(Star(bot))

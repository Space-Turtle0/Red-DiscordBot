import discord
from discord.ext import commands

from redbot.core import checks, modlog, RedContext
from redbot.core.bot import Red
from redbot.core.i18n import CogI18n
from redbot.core.utils.chat_formatting import box, warning

_ = CogI18n('ModLog', __file__)


class ModLog:
    """Log for mod actions"""

    def __init__(self, bot: Red):
        self.bot = bot

    @commands.group()
    @checks.guildowner_or_permissions(administrator=True)
    async def modlogset(self, ctx: RedContext):
        """Settings for the mod log"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @modlogset.command()
    @commands.guild_only()
    async def modlog(self, ctx: RedContext, channel: discord.TextChannel = None):
        """Sets a channel as mod log

        Leaving the channel parameter empty will deactivate it"""
        guild = ctx.guild
        if channel:
            if channel.permissions_for(guild.me).send_messages:
                await modlog.set_modlog_channel(guild, channel)
                await ctx.send(
                    _("Mod events will be sent to {}").format(
                        channel.mention
                    )
                )
            else:
                await ctx.send(
                    _("I do not have permissions to "
                      "send messages in {}!").format(channel.mention)
                )
        else:
            try:
                await modlog.get_modlog_channel(guild)
            except RuntimeError:
                await ctx.send_help()
            else:
                await modlog.set_modlog_channel(guild, None)
                await ctx.send(_("Mod log deactivated."))

    @modlogset.command(name='cases')
    @commands.guild_only()
    async def set_cases(self, ctx: RedContext, action: str = None):
        """Enables or disables case creation for each type of mod action"""
        guild = ctx.guild

        if action is None:  # No args given
            casetypes = await modlog.get_all_casetypes(guild)
            await ctx.send_help()
            title = _("Current settings:")
            msg = ""
            for ct in casetypes:
                enabled = await ct.is_enabled()
                value = 'enabled' if enabled else 'disabled'
                msg += '%s : %s\n' % (ct.name, value)

            msg = title + "\n" + box(msg)
            await ctx.send(msg)
            return
        casetype = await modlog.get_casetype(action, guild)
        if not casetype:
            await ctx.send(_("That action is not registered"))
        else:

            enabled = await casetype.is_enabled()
            await casetype.set_enabled(True if not enabled else False)

            msg = (
                _('Case creation for {} actions is now {}.').format(
                    action, 'enabled' if not enabled else 'disabled'
                )
            )
            await ctx.send(msg)

    @modlogset.command()
    @commands.guild_only()
    async def resetcases(self, ctx: RedContext):
        """Resets modlog's cases"""
        guild = ctx.guild
        await modlog.reset_cases(guild)
        await ctx.send(_("Cases have been reset."))

    @commands.command()
    @commands.guild_only()
    async def case(self, ctx: RedContext, number: int):
        """Shows the specified case"""
        try:
            case = await modlog.get_case(number, ctx.guild, self.bot)
        except RuntimeError:
            await ctx.send(_("That case does not exist for that guild"))
            return
        else:
            await ctx.send(embed=await case.get_case_msg_content())

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def casemod(self, ctx: RedContext, case: int, moderator: discord.abc.User):
        """
        Lets you specify the moderator for a mod log case.

        Useful for setting a mod for cases resulting from a manual
        action (such as right-clicking a user and clicking "Ban")
        so they can use the reason command to edit the case.
        """
        guild = ctx.guild
        try:
            case_before = await modlog.get_case(case, guild, self.bot)
        except RuntimeError:
            await ctx.send(_("That case does not exist!"))
            return
        else:
            if case_before.moderator is not None:
                await ctx.send(_("That case already has a moderator set!"))
                return
            to_modify = {"moderator": moderator}
            await case_before.edit(to_modify)
            await ctx.send(_(
                "{} has been set as the moderator for case {}."
            ).format(moderator.mention, case))

    @commands.command()
    @commands.guild_only()
    async def reason(self, ctx: RedContext, case: int, *, reason: str = ""):
        """Lets you specify a reason for mod-log's cases
        Please note that you can only edit cases you are
        the owner of unless you are a mod/admin or the guild owner"""
        author = ctx.author
        guild = ctx.guild
        if not reason:
            await ctx.send_help()
            return
        try:
            case_before = await modlog.get_case(case, guild, self.bot)
        except RuntimeError:
            await ctx.send(_("That case does not exist!"))
            return
        else:
            if case_before.moderator is None:
                await ctx.send(
                    warning(_(
                        "This mod log case has no moderator set! One can be "
                        "set with {}"
                    ).format("`{}casemod <case_number> <moderator>`".format(
                        ctx.prefix)
                    ))
                )
            is_guild_owner = author == guild.owner
            is_case_author = author == case_before.moderator
            author_is_mod = await ctx.bot.is_mod(author)
            if not (is_guild_owner or is_case_author or author_is_mod):
                await ctx.send(_("You are not authorized to modify that case!"))
                return
            to_modify = {
                "reason": reason,
            }
            if case_before.moderator != author:
                to_modify["amended_by"] = author
            to_modify["modified_at"] = ctx.message.created_at.timestamp()
            await case_before.edit(to_modify)
            await ctx.send(_("Reason has been updated."))

Track custom emojis and view usage statistics.

This cog tracks reactions added to other users' messages, including reactions within Threads.
It ignores:
- Reactions from bots.
- Standard Unicode emojis (only custom emojis are tracked).
- Self-reactions (optional/toggleable, ignores users reacting to their own messages).
- Spam (only one count per emoji per message for each user).

# [p]ignoreguild
Add/Remove a server from the blacklist. Enter a Guild ID to add it to the blacklist, to remove, simply enter it again.
 - Usage: `[p]ignoreguild <guild_id>`
 - Restricted to: `BOT_OWNER`
 - Aliases: `ignoreserver`

# [p]viewblacklist
View EmojiTracker Blacklist.
 - Usage: `[p]viewblacklist`
 - Restricted to: `BOT_OWNER`

# [p]resetreacts
Reset reaction data for this server.
 - Usage: `[p]resetreacts`
 - Checks: `server_only`

# [p]selfcount
Toggle whether users reacting to their own messages increases the count.
 - Usage: `[p]selfcount`
 - Checks: `server_only`
 - Restricted to: `manage_guild` (Administrators/Moderators)

# [p]emojilb
View the emoji leaderboard (includes unused custom emojis with a count of 0).
 - Usage: `[p]emojilb`
 - Checks: `server_only`

# [p]emojipurge
Find emojis with the lowest usage to free up slots. Useful for finding dead weight emojis.
 - Usage: `[p]emojipurge`
 - Checks: `server_only`
 - Restricted to: `manage_guild` (Administrators/Moderators)
 - Aliases: `leastused`

# [p]reactlb
View user leaderboard for most custom emojis added.
 - Usage: `[p]reactlb`
 - Checks: `server_only`

# [p]emojitrackercache
Get the size of EmojiTracker cache.
 - Usage: `[p]emojitrackercache`
 - Restricted to: `BOT_OWNER`
 - Aliases: `etc`

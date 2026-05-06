TEXTS: dict[str, str] = {
    'main_menu': 'Main menu',
    'welcome': 'Welcome. Use the menu below.',
    'language_saved': 'Language saved.',
    'choose_language': 'Choose language:',
    'contact_admin': 'Contact admin: {admin_contact}',
     'help': (
        '❓ Help — How to use this bot\n\n'
        'This bot helps you connect Telegram channels into one link loop.\n'
        'Example: if Pair 1 has Channel A, B, and C, a new post from A can be sent to B, then from B to C with source links added under each post.\n\n'
        '✅ First setup\n'
        '1. Add this bot as Admin in every channel you want to use.\n'
        '2. Give the bot Post Messages permission.\n'
        '3. For public channels, you can send @username or https://t.me/username.\n'
        '4. For private channels, send the -100... channel ID or a post link like https://t.me/c/1234567890/15.\n'
        '5. Private invite links like https://t.me/+... cannot be checked by the bot.\n\n'
        '➕ Add Pair\n'
        'Use this to create a new channel group.\n'
        'You will choose:\n'
        '- Pair number, or Auto\n'
        '- Repost Style\n'
        '- Channel list\n'
        '- Movie Rule ON/OFF\n\n'
        '🔁 Repost Style\n'
        'Random: the bot sends to the other channels in random order.\n'
        'By Order: the bot follows the order numbers you set.\n\n'
        '🎬 Movie Rule\n'
        'OFF: every new post is looped.\n'
        'ON: when a video appears, the bot does not loop the video itself. It loops the post immediately above that video if that post was already captured by the bot.\n\n'
        '📋 My Pairs\n'
        'Shows your saved pairs and their settings.\n\n'
        '🗑 Remove Pair\n'
        'Use this when you no longer want a pair to work. Removed/inactive pairs will not trigger admin warning reports.\n\n'
        '⚠️ Common problems\n'
        '- If the bot says admin permission is missing, check that it is Admin and can Post Messages.\n'
        '- After fixing permissions, press 🔄 Recheck.\n'
        '- Albums are sent as albums, with the footer on the first media item only.\n'
        '- Do not add the same channel twice in one pair.\n\n'
        '☎️ Need help? Use Contact Admin from the menu.'
    ),
    'generic_error': 'Something went wrong. Please try again or contact admin.',
    'something_went_wrong': 'Something went wrong. Please try again or contact admin.',
    'add_pair': 'Add Pair',
    'remove_pair': 'Remove Pair',
    'edit_repost_style': 'Edit Repost Style',
    'edit_movie_rule': 'Edit Movie Rule',
    'language': 'Language',
    'cancelled': 'Cancelled. Returned to main menu.',
    'back': '⬅️ Back',
    'cancel': '❌ Cancel',
    'confirm': '✅ Confirm',
    'recheck': '🔄 Recheck',
    'auto': 'Auto',
    'on': 'ON',
    'off': 'OFF',
    'random': 'Random',
    'by_order': 'By Order',
    'movie_rule_on': 'Movie Rule ON',
    'movie_rule_off': 'Movie Rule OFF',
    'repost_style_random': 'Random',
    'repost_style_by_order': 'By Order',
    'add_pair_step_pair_no': 'Step 1/5: Send pair number or press Auto.\n\nExisting pair numbers cannot be reused.',
    'pair_limit_reached': 'Pair limit reached. Your current pair limit is {limit}.',
    'pair_no_exists': 'Pair {pair_no} already exists. Please choose another number.',
    'invalid_pair_no': 'Invalid pair number. Please send a positive number or press Auto.',
    'add_pair_step_style': 'Step 2/5: Choose repost style.',
    'add_pair_step_channels_random': (
        'Step 3/5: Send channel links or IDs separated by comma.\n\n'
        'Example:\nhttps://t.me/channelA, https://t.me/channelB, -1001234567890'
    ),
    'add_pair_step_channels_order': (
        'Step 3/5: Send channel links or IDs with order numbers.\n\n'
        'Example:\n1-https://t.me/channelA, 2-https://t.me/channelB, 3--1001234567890\n\n'
        'If numbers are missing, the given order will be used.'
    ),
    'channel_count_error': 'Channel count must be between 2 and {limit}.',
    'duplicate_channels': 'Duplicate channels are not allowed.',
    'unsupported_channel_input': (
        'This private invite link cannot be checked by Bot API:\n{value}\n\n'
        'The bot may already be admin, but invite links like https://t.me/+... are not valid chat IDs for getChat/getChatMember.\n\n'
        'Please send one of these instead:\n'
        '1. Public @username or https://t.me/username\n'
        '2. Numeric private channel ID like -1001234567890\n'
        '3. Private post link like https://t.me/c/1234567890/15\n\n'
        'Tip: copy a message/post link from that private channel, or use @raw_data_bot to get the -100... ID.'
    ),
    'missing_admin_title': 'These channels are missing admin permission:',
    'admin_missing': 'Admin permission is missing.',
    'missing_admin_footer': 'Please add the bot as admin with Post Messages permission, then press Recheck.',
    'add_pair_step_movie': 'Step 4/5: Choose Movie Rule.',
    'add_pair_confirm': (
        'Step 5/5: Confirm pair.\n\n'
        'Pair No: {pair_no}\n'
        'Repost Style: {style}\n'
        'Movie Rule: {movie_rule}\n\n'
        'Channels:\n{channels}\n\n'
        'Admin Check: OK'
    ),
    'pair_created': 'Pair {pair_no} created successfully.',
    'no_pairs': 'You have no pairs yet.',
    'my_pairs': 'Your pairs:\n\n{pairs}',
    'select_pair_remove': 'Select a pair to remove:',
    'remove_pair_confirm': 'Remove this pair?\n\n{details}',
    'pair_removed': 'Pair {pair_no} removed.',
    'select_pair_style': 'Select a pair to edit repost style:',
    'select_new_style': 'Choose new repost style for Pair {pair_no}:',
    'send_new_order': 'Send new channel order.\n\nExample:\n1-Channel A, 2-Channel B, 3-Channel C\n\nCurrent channels:\n{channels}',
    'style_saved': 'Repost style saved for Pair {pair_no}.',
    'select_pair_movie': 'Select a pair to edit Movie Rule:',
    'movie_saved': 'Movie Rule saved for Pair {pair_no}: {value}',
    'admin_only': 'Admin only.',
    'status_empty': 'No users found.',
    'user_not_found': 'User not found.',
    'banned_ok': 'User banned.',
    'unbanned_ok': 'User unbanned.',
    'limit_saved': 'Limit saved.',
    'status_report_sent': 'Status report sent to report group.',
    'status_report_failed': 'Could not send status report to report group. Please check logs.',
    'usage_error': 'Invalid command usage.',
    'footer': 'Source Channel: {channel_title}\nChannel Link: {channel_link}\nPost Link: {post_link}',
    'permission_removed_user': (
        '⚠️ Bot admin permission was removed from {channel_title}.\n'
        'Pairs using this channel have been paused.\n'
        'Please add the bot back as admin with Post Messages permission.'
    ),
    'permission_restored_user': '✅ Bot admin permission was restored in {channel_title}. Paused pairs were rechecked.',
}

BUTTONS: dict[str, str] = {
    'add_pair': '➕ Add Pair',
    'remove_pair': '🗑 Remove Pair',
    'edit_style': '🔁 Edit Repost Style',
    'edit_movie': '🎬 Edit Movie Rule',
    'my_pairs': '📋 My Pairs',
    'language': '🌐 Language',
    'contact_admin': '☎️ Contact Admin',
    'help': '❓ Help',
}

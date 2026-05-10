TEXTS: dict[str, str] = {
    'main_menu': 'ပင်မစာမျက်နှာ',
    'welcome': 'ကြိုဆိုပါသည်။ အောက်က menu ကိုအသုံးပြုပါ။',
    'language_saved': 'ဘာသာစကား သိမ်းပြီးပါပြီ။',
    'choose_language': 'ဘာသာစကား ရွေးပါ:',
    'contact_admin': 'Admin ဆက်သွယ်ရန်: {admin_contact}',
    'help': (
        '❓ အကူအညီ — Bot သုံးနည်း\n\n'
        'ဒီ Bot က Telegram Channel တွေကို Pair အနေနဲ့ချိတ်ပြီး post တွေကို loop ပတ်ပေးတဲ့ Bot ပါ။\n'
        'ဥပမာ Pair 1 ထဲမှာ Channel A, B, C ရှိရင် A မှာ post အသစ်တက်တာကို B ထဲပို့မယ်၊ ပြီးရင် B ကနေ C ထဲဆက်ပို့မယ်။ Post အောက်မှာ မူရင်း channel link နဲ့ post link ကို ထည့်ပေးပါတယ်။\n\n'
        '✅ အရင်ဆုံး Setup လုပ်ရန်\n'
        '1. အသုံးပြုမယ့် channel တိုင်းမှာ ဒီ Bot ကို Admin ပေးပါ။\n'
        '2. Post Messages permission ကို ဖွင့်ပေးပါ။\n'
        '3. Public channel ဆိုရင် @username သို့မဟုတ် https://t.me/username ပို့လို့ရပါတယ်။\n'
        '4. Private channel ဆိုရင် invite link + -100... channel ID နှစ်ခုစလုံးပို့ပါ။\n'
        ' ဥပမာ: https://t.me/+invite1(-1001234567890)\n'
        '5. invite link တစ်ခုတည်း သို့မဟုတ် channel ID တစ်ခုတည်းပို့ရင် Bot က လိုတဲ့ ID/link ကို ထပ်တောင်းပါမယ်။\n\n'
        '➕ Pair ထည့်မယ်\n'
        'Channel group အသစ်တစ်ခုထည့်ဖို့သုံးပါ။\n'
        'ထည့်တဲ့အခါ ဒီအဆင့်တွေ ရွေးရပါမယ်။\n'
        '- Pair number သို့မဟုတ် Auto\n'
        '- Repost Style\n'
        '- Channel list\n'
        '- Movie Rule ဖွင့်/ပိတ်\n\n'
        ' Repost Style ဆိုတာ\n'
        'Always Random: post အသစ်တက်တိုင်း route ကို အသစ်ကျပန်းစီမယ်။ မူရင်း post တက်လာတဲ့ channel ကတော့ အမြဲ ပထမဆုံးမှာရှိမယ်။\n'
        'By Order: သင်သတ်မှတ်ထားတဲ့ order number အတိုင်းပို့မယ်။\n\n'
        ' Movie Rule ဆိုတာ\n'
        'OFF: post အသစ်တက်တိုင်း loop ပတ်မယ်။\n'
        'ON: video post တက်လာရင် video ကိုမပို့ဘဲ အဲဒီ video အပေါ်က post ကို Bot cache ထဲမှာရှိရင် loop ပတ်ပေးမယ်။\n\n'
        ' ကျွန်ုပ်၏ Pair များ\n'
        'သင်ထည့်ထားတဲ့ Pair တွေနဲ့ setting တွေကိုကြည့်ရန်သုံးပါ။\n\n'
        ' Pair ဖျက်မယ်\n'
        'မသုံးချင်တော့တဲ့ Pair ကိုဖျက်ရန်သုံးပါ။ ဖျက်ပြီးသား/inactive Pair တွေအတွက် admin warning report မပို့တော့ပါ။\n\n'
        '⚠️ ဖြစ်တတ်တဲ့ပြဿနာများ\n'
        '- Admin permission မပြည့်စုံပါလို့ပြရင် Bot ကို Admin ပေးထားလား၊ Post Messages permission ဖွင့်ထားလား စစ်ပါ။\n'
        '- Permission ပြင်ပြီးရင် ပြန်စစ်မယ် ကိုနှိပ်ပါ။\n'
        '- Album post တွေကို album အတိုင်းပို့ပြီး footer ကို ပထမ media မှာပဲထည့်ပါတယ်။\n'
        '- Pair တစ်ခုထဲမှာ channel တစ်ခုကို နှစ်ခါထည့်လို့မရပါ။\n\n'
        '☎️ မရှင်းလင်းသေးရင် Menu ထဲက Admin ဆက်သွယ်ရန် ကိုနှိပ်ပါ။'
    ),
    'generic_error': 'အမှားတစ်ခု ဖြစ်သွားပါသည်။ ပြန်စမ်းကြည့်ပါ သို့မဟုတ် Admin ကိုဆက်သွယ်ပါ။',
    'something_went_wrong': 'အမှားတစ်ခု ဖြစ်သွားပါသည်။ ပြန်စမ်းကြည့်ပါ သို့မဟုတ် Admin ကိုဆက်သွယ်ပါ။',
    'add_pair': 'Pair ထည့်မယ်',
    'remove_pair': 'Pair ဖျက်မယ်',
    'edit_repost_style': 'Repost Style ပြင်မယ်',
    'edit_movie_rule': 'Movie Rule ပြင်မယ်',
    'language': 'ဘာသာစကား',
    'cancelled': '❌ လုပ်ဆောင်မှုကို ပယ်ဖျက်ပြီး ပင်မစာမျက်နှာသို့ ပြန်သွားပါပြီ။',
    'back': '⬅️ နောက်သို့',
    'cancel': '❌ ပယ်ဖျက်မယ်',
    'confirm': '✅ အတည်ပြုမယ်',
    'recheck': ' ပြန်စစ်မယ်',
    'auto': '⚙️ အလိုအလျောက်',
    'on': '✅ ဖွင့်မယ်',
    'off': '❌ ပိတ်မယ်',
    'random': ' အမြဲ ကျပန်း',
    'by_order': ' အစဉ်လိုက်',
    'movie_rule_on': '✅ Movie Rule ဖွင့်ထားသည်',
    'movie_rule_off': '❌ Movie Rule ပိတ်ထားသည်',
    'repost_style_random': ' အမြဲ ကျပန်း',
    'repost_style_by_order': ' အစဉ်လိုက်',
    'add_pair_step_pair_no': 'အဆင့် 1/5: Pair number ပို့ပါ သို့မဟုတ် Auto နှိပ်ပါ။\n\nရှိပြီးသား pair number ကို ပြန်သုံးလို့မရပါ။',
    'pair_limit_reached': 'Pair limit ပြည့်သွားပါပြီ။ သင့် limit သည် {limit} ဖြစ်သည်။',
    'pair_no_exists': 'Pair {pair_no} ရှိပြီးသားဖြစ်သည်။ တခြား number ရွေးပါ။',
    'invalid_pair_no': 'Pair number မမှန်ပါ။ Positive number ပို့ပါ သို့မဟုတ် Auto နှိပ်ပါ။',
    'add_pair_step_style': 'အဆင့် 2/5: Repost style ရွေးပါ။',
    'add_pair_step_channels_random': (
        'အဆင့် 3/5: Channel link သို့မဟုတ် ID များကို comma ဖြင့်ခွဲပြီး ပို့ပါ။\n\n'
        'Public channel:\nhttps://t.me/channelB\n\n'
        'Private channel ဆိုရင် invite link + channel ID နှစ်ခုစလုံးထည့်ပါ:\n'
        'https://t.me/+invite1(-1001234567890)\n'
        '-1001234568798(https://t.me/+invite2)\n'
        'https://t.me/+invite3 = -1001234567777\n\n'
        'ဥပမာ:\nhttps://t.me/+invite1(-1001234567890), https://t.me/channelB, -1001234568798(https://t.me/+invite2)'
    ),
    'add_pair_step_channels_order': (
        'အဆင့် 3/5: Channel link သို့မဟုတ် ID များကို order number ဖြင့် ပို့ပါ။\n\n'
        'Public channel:\n1-https://t.me/channelB\n\n'
        'Private channel ဆိုရင် invite link + channel ID နှစ်ခုစလုံးထည့်ပါ:\n'
        '2-https://t.me/+invite1(-1001234567890)\n'
        '3--1001234568798(https://t.me/+invite2)\n'
        '4-https://t.me/+invite3 = -1001234567777\n\n'
        'Number မပါလျှင် ပို့ထားသောအစဉ်အတိုင်း သတ်မှတ်မည်။'
    ),
    'invalid_channel_input_title': 'အောက်ပါ channel input များ မမှန်ပါ:',
    'channel_input_format_help': (
        'Public channel ကို https://t.me/channelName ပုံစံပို့ပါ။\n'
        'Private channel ကို invite link + channel ID နှစ်ခုစလုံးနဲ့ ပို့ပါ။ ဥပမာ:\n'
        'https://t.me/+invite1(-1001234567890)\n'
        '-1001234567890(https://t.me/+invite1)\n'
        'https://t.me/+invite1 = -1001234567890'
    ),
    'missing_chat_id_title': 'အောက်ပါ invite link များ၏ channel ID ကို ပို့ပါ:',
    'missing_chat_id_example': (
        'ဥပမာ:\n'
        'https://t.me/+invite1(-1001234567890)\n'
        'သို့မဟုတ်\n'
        'https://t.me/+invite1 = -1001234567890'
    ),
    'missing_invite_link_title': 'အောက်ပါ channel ID များ၏ invite link ကို ပို့ပါ:',
    'missing_invite_link_example': (
        'ဥပမာ:\n'
        '-1001234567890(https://t.me/+invite1)\n'
        'သို့မဟုတ်\n'
        '-1001234567890 = https://t.me/+invite1'
    ),
    'channel_count_error': 'Channel အရေအတွက်သည် 2 မှ {limit} အတွင်း ဖြစ်ရမည်။',
    'duplicate_channels': 'Channel တစ်ခုကို ထပ်ထည့်လို့မရပါ။',
    'unsupported_channel_input': (
        'ဒီ private invite link ကို Bot API နဲ့ စစ်လို့မရပါ:\n{value}\n\n'
        'Bot ကို admin ပေးထားပြီးသားဖြစ်နိုင်ပေမဲ့ https://t.me/+... invite link က getChat/getChatMember အတွက် chat ID မဟုတ်ပါ။\n\n'
        'အောက်ပါတစ်ခုခုကို ပြန်ပို့ပါ:\n'
        '1. Public @username သို့မဟုတ် https://t.me/username\n'
        '2. Private channel numeric ID ဥပမာ -1001234567890\n'
        '3. Private post link ဥပမာ https://t.me/c/1234567890/15\n\n'
        'Tip: private channel ထဲက post တစ်ခုကို Copy Link လုပ်ပါ သို့မဟုတ် @raw_data_bot ဖြင့် -100... ID ယူပါ။'
    ),
    'missing_admin_title': 'အောက်ပါ channel များတွင် admin permission မပြည့်စုံပါ:',
    'admin_missing': '⚠️ Admin permission မပြည့်စုံပါ။',
    'missing_admin_footer': 'Bot ကို Post Messages permission ဖြင့် admin ပေးပြီး ပြန်စစ်မယ် ခလုတ်ကို နှိပ်ပါ။',
    'add_pair_step_movie': 'အဆင့် 4/5: Movie Rule ရွေးပါ။',
    'add_pair_confirm': (
        'အဆင့် 5/5: Pair အတည်ပြုပါ။\n\n'
        'Pair No: {pair_no}\n'
        'Repost Style: {style}\n'
        'Movie Rule: {movie_rule}\n\n'
        'Channels:\n{channels}\n\n'
        'Admin Check: OK'
    ),
    'pair_created': 'Pair {pair_no} ထည့်ပြီးပါပြီ။',
    'no_pairs': 'Pair မရှိသေးပါ။',
    'my_pairs': 'သင်၏ Pair များ:\n\n{pairs}',
    'select_pair_remove': 'ဖျက်မည့် Pair ကို ရွေးပါ:',
    'remove_pair_confirm': 'ဒီ Pair ကို ဖျက်မလား?\n\n{details}',
    'pair_removed': 'Pair {pair_no} ဖျက်ပြီးပါပြီ။',
    'select_pair_style': 'Repost style ပြင်မည့် Pair ကို ရွေးပါ:',
    'select_new_style': 'Pair {pair_no} အတွက် repost style အသစ် ရွေးပါ:',
    'send_new_order': 'Channel order အသစ် ပို့ပါ။\n\nဥပမာ:\n1-Channel A, 2-Channel B, 3-Channel C\n\nလက်ရှိ channels:\n{channels}',
    'style_saved': 'Pair {pair_no} အတွက် Repost style သိမ်းပြီးပါပြီ။',
    'select_pair_movie': 'Movie Rule ပြင်မည့် Pair ကို ရွေးပါ:',
    'movie_saved': 'Pair {pair_no} အတွက် Movie Rule သိမ်းပြီးပါပြီ: {value}',
    'admin_only': 'Admin သီးသန့်ဖြစ်သည်။',
    'status_empty': 'User မရှိသေးပါ။',
    'user_not_found': 'User မတွေ့ပါ။',
    'banned_ok': 'User ကို ban ပြီးပါပြီ။',
    'unbanned_ok': 'User ကို unban ပြီးပါပြီ။',
    'limit_saved': 'Limit သိမ်းပြီးပါပြီ။',
    'status_report_sent': 'Status report ကို report group သို့ ပို့ပြီးပါပြီ။',
    'status_report_failed': 'Status report ကို report group သို့ မပို့နိုင်ပါ။ Log ကိုစစ်ပါ။',
    'usage_error': 'Command အသုံးပြုပုံ မမှန်ပါ။',
    'footer': 'channel join - {channel_link}\n\nကြည့်ရန်လင့် - {post_link}',
    'permission_removed_user': (
        '⚠️ {channel_title} တွင် Bot admin permission ဖြုတ်ထားသည်။\n'
        'ဤ channel ပါသော Pair များကို ယာယီရပ်ထားပါသည်။\n'
        'Bot ကို Post Messages permission ဖြင့် admin ပြန်ပေးပါ။'
    ),
    'permission_restored_user': '✅ {channel_title} တွင် Bot admin permission ပြန်ရပါပြီ။ ရပ်ထားသော Pair များကို ပြန်စစ်ပြီးပါပြီ။',
}

BUTTONS: dict[str, str] = {
    'add_pair': '➕ Pair ထည့်မယ်',
    'remove_pair': '🗑 Pair ဖျက်မယ်',
    'edit_style': '🔁 Repost Style ပြင်မယ်',
    'edit_movie': '🎬 Movie Rule ပြင်မယ်',
    'my_pairs': '📋 ကျွန်ုပ်၏ Pair များ',
    'language': '🌐 ဘာသာစကား',
    'contact_admin': '☎️ Admin ဆက်သွယ်ရန်',
    'help': '❓ အကူအညီ',
}

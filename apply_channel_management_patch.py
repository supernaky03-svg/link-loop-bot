#!/usr/bin/env python3
"""Apply the per-pair channel-management overlay to the repository main branch.

Run this from the repository root after checking out main. The script is
idempotent and refuses to continue if expected source anchors are missing,
so it will not silently patch an unrelated revision.
"""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def patch(path: str, old: str, new: str, label: str) -> None:
    file_path = ROOT / path
    if not file_path.exists():
        raise SystemExit(f"Missing required source file: {path}")
    source = file_path.read_text(encoding="utf-8")
    if new in source:
        print(f"[already applied] {label}")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Cannot safely patch {path}: expected one anchor for {label}, found {count}.")
    file_path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print(f"[patched] {label}")


def patch_locale(path: str, language: str) -> None:
    file_path = ROOT / path
    if not file_path.exists():
        raise SystemExit(f"Missing required source file: {path}")
    source = file_path.read_text(encoding="utf-8")
    marker = "    'manage_channels':"
    if marker in source:
        print(f"[already applied] {language} translations")
        return

    if language == "en":
        text_entries = """    'manage_select_pair': 'Select a pair to manage its channels:',
    'manage_pair_summary': 'Pair {pair_no} · {count} active channels\\n\\n{channels}\\n\\nChoose an action:',
    'manage_no_active_channels': 'No active channels. Add at least two channels to resume reposting.',
    'manage_add_channel': '➕ Add channel',
    'manage_remove_channel': '➖ Remove channel',
    'manage_add_prompt': 'Send one channel link or ID to add to this pair.\\n\\nPublic: @username or https://t.me/name\\nPrivate: https://t.me/+invite(-1001234567890)',
    'manage_select_channel_remove': 'Select the channel to remove from this pair:',
    'manage_confirm_remove': 'Remove channel {chat_id} from this pair? This keeps its history but stops using it for new routes.',
    'manage_channel_added': 'Channel added to this pair.',
    'manage_channel_removed': 'Channel removed from this pair.',
    'manage_operation_error': '{error}',
    'manage_channels_paused': 'Pair paused: at least two active channels are required. Add another channel to resume.',
"""
        button_entry = "    'manage_channels': '🧩 Manage Pair Channels',\n"
    else:
        text_entries = """    'manage_select_pair': 'Channel စီမံမည့် Pair ကို ရွေးပါ:',
    'manage_pair_summary': 'Pair {pair_no} · Active Channel {count} ခု\\n\\n{channels}\\n\\nလုပ်ဆောင်ချက် ရွေးပါ:',
    'manage_no_active_channels': 'Active Channel မရှိပါ။ Repost ပြန်စရန် အနည်းဆုံး Channel ၂ ခု ထည့်ပါ။',
    'manage_add_channel': '➕ Channel ထည့်မယ်',
    'manage_remove_channel': '➖ Channel ဖယ်မယ်',
    'manage_add_prompt': 'ဒီ Pair ထဲ ထည့်မည့် Channel တစ်ခု၏ Link သို့မဟုတ် ID ကို ပို့ပါ။\\n\\nPublic: @username သို့မဟုတ် https://t.me/name\\nPrivate: https://t.me/+invite(-1001234567890)',
    'manage_select_channel_remove': 'ဒီ Pair ထဲမှ ဖယ်ရှားမည့် Channel ကို ရွေးပါ:',
    'manage_confirm_remove': 'Channel {chat_id} ကို ဒီ Pair ထဲမှ ဖယ်ရှားမလား? History ကို ထိန်းထားပြီး နောက်ထပ် route တွေမှာ အသုံးမပြုတော့ပါ။',
    'manage_channel_added': 'Channel ကို Pair ထဲ ထည့်ပြီးပါပြီ။',
    'manage_channel_removed': 'Channel ကို Pair ထဲမှ ဖယ်ရှားပြီးပါပြီ။',
    'manage_operation_error': '{error}',
    'manage_channels_paused': 'Active Channel အနည်းဆုံး ၂ ခု လိုအပ်သောကြောင့် Pair ကို ခေတ္တရပ်ထားသည်။ Channel တစ်ခု ထပ်ထည့်ပါ။',
"""
        button_entry = "    'manage_channels': '🧩 Pair Channel စီမံမယ်',\n"

    # Insert management text keys inside TEXTS, immediately before admin_only.
    text_start = source.find("TEXTS: dict[str, str] = {")
    buttons_start = source.find("BUTTONS: dict[str, str] = {")
    if text_start < 0 or buttons_start < 0 or buttons_start <= text_start:
        raise SystemExit(f"Cannot identify TEXTS/BUTTONS dictionaries in {path}")
    text_part = source[text_start:buttons_start]
    admin_key = "    'admin_only':"
    if text_part.count(admin_key) != 1:
        raise SystemExit(f"Cannot safely insert {language} TEXTS entries in {path}")
    text_part = text_part.replace(admin_key, text_entries + admin_key, 1)
    source = source[:text_start] + text_part + source[buttons_start:]

    buttons_start = source.find("BUTTONS: dict[str, str] = {")
    button_anchor = "    'my_pairs':"
    before_buttons, buttons = source[:buttons_start], source[buttons_start:]
    if buttons.count(button_anchor) != 1:
        raise SystemExit(f"Cannot safely insert {language} menu button in {path}")
    buttons = buttons.replace(button_anchor, button_entry + button_anchor, 1)
    file_path.write_text(before_buttons + buttons, encoding="utf-8")
    print(f"[patched] {language} translations and menu label")


def main() -> None:
    git_dir = ROOT / ".git"
    if git_dir.exists():
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise SystemExit(f"Could not inspect Git checkout: {exc}") from exc
        if branch != "main":
            raise SystemExit(
                f"Expected branch main, found {branch!r}. "
                "Switch to main before applying this overlay."
            )

    # Bot router registration.
    patch(
        "app/bot/handlers/__init__.py",
        "from . import admin, channel_posts, menu, pair_add, pair_edit, pair_remove, permissions, start",
        "from . import admin, channel_management, channel_posts, menu, pair_add, pair_edit, pair_remove, permissions, start",
        "import channel-management router",
    )
    patch(
        "app/bot/handlers/__init__.py",
        "    dp.include_router(menu.router)\n    dp.include_router(pair_add.router)",
        "    dp.include_router(menu.router)\n    dp.include_router(channel_management.router)\n    dp.include_router(pair_add.router)",
        "register channel-management router",
    )

    # Reply menu entry.
    patch(
        "app/bot/keyboards/reply.py",
        "        [KeyboardButton(text=b(language, 'edit_style')), KeyboardButton(text=b(language, 'edit_movie'))],\n        [KeyboardButton(text=b(language, 'my_pairs')), KeyboardButton(text=b(language, 'language'))],",
        "        [KeyboardButton(text=b(language, 'edit_style')), KeyboardButton(text=b(language, 'edit_movie'))],\n        [KeyboardButton(text=b(language, 'manage_channels'))],\n        [KeyboardButton(text=b(language, 'my_pairs')), KeyboardButton(text=b(language, 'language'))],",
        "add manage-channel button to Bot menu",
    )
    patch_locale("app/bot/locales/en.py", "en")
    patch_locale("app/bot/locales/my.py", "my")

    # Keep the Bot's My Pairs summary consistent with soft-removal.
    patch(
        "app/bot/services/pair_service.py",
        "    for ch in sorted(pair.channels, key=lambda c: c.order_no):\n        lines.append(f'{ch.order_no}. {ch.title} ({ch.chat_id})')",
        "    for ch in sorted((item for item in pair.channels if item.is_active), key=lambda c: c.order_no):\n        lines.append(f'{ch.order_no}. {ch.title} ({ch.chat_id})')",
        "hide soft-removed channels from My Pairs summary",
    )

    # Restoring permissions must not resume a pair which has fewer than two channels.
    patch(
        "app/db/repository.py",
        "            if all(ch.bot_admin_ok for ch in pair.channels if ch.is_active):\n                pair.is_paused = False\n                pair.paused_reason = None",
        "            active_channels = [ch for ch in pair.channels if ch.is_active]\n            if len(active_channels) < 2:\n                pair.is_paused = True\n                pair.paused_reason = \"insufficient_channels\"\n            elif all(ch.bot_admin_ok for ch in active_channels):\n                pair.is_paused = False\n                pair.paused_reason = None",
        "prevent permission restoration from resuming undersized pairs",
    )

    # Mini App API handlers and routes.
    patch(
        "app/webapp.py",
        "from app.webapp_auth import InitDataError, validate_telegram_init_data\n",
        "from app.webapp_auth import InitDataError, validate_telegram_init_data\nfrom app.web_channel_management import api_add_pair_channel, api_remove_pair_channel\n",
        "import Mini App channel endpoints",
    )
    patch(
        "app/webapp.py",
        "    app.router.add_post(\"/api/pairs\", api_create_pair)\n",
        "    app.router.add_post(\"/api/pairs\", api_create_pair)\n    app.router.add_post(r\"/api/pairs/{pair_no:\\d+}/channels\", api_add_pair_channel)\n    app.router.add_delete(r\"/api/pairs/{pair_no:\\d+}/channels/{chat_id:-?\\d+}\", api_remove_pair_channel)\n",
        "register Mini App channel add/remove routes",
    )
    patch(
        "app/webapp.py",
        "    failures = []\n    for channel in pair.channels:\n        checked = await resolve_and_check_channel(request.app[\"bot\"], str(channel.chat_id), channel.order_no)\n        channel.bot_admin_ok = bool(checked.ok)\n        channel.last_admin_check_at = datetime.now(timezone.utc)\n        if not checked.ok:\n            failures.append(channel.title)\n    pair.is_paused = bool(failures)\n    pair.paused_reason = \"bot_admin_missing\" if failures else None\n",
        "    active_channels = [channel for channel in pair.channels if channel.is_active]\n    failures = []\n    for channel in active_channels:\n        checked = await resolve_and_check_channel(request.app[\"bot\"], str(channel.chat_id), channel.order_no)\n        channel.bot_admin_ok = bool(checked.ok)\n        channel.last_admin_check_at = datetime.now(timezone.utc)\n        if not checked.ok:\n            failures.append(channel.title)\n    if len(active_channels) < 2:\n        pair.is_paused = True\n        pair.paused_reason = \"insufficient_channels\"\n    else:\n        pair.is_paused = bool(failures)\n        pair.paused_reason = \"bot_admin_missing\" if failures else None\n",
        "recheck active channels only and preserve minimum-channel pause",
    )

    patch(
        "app/webapp.py",
        '    message = "Permission is still missing: " + ", ".join(failures) if failures else "All channel permissions are OK. Pair resumed."',
        '    if len(active_channels) < 2:\n        message = "Pair remains paused: at least two active channels are required."\n    elif failures:\n        message = "Permission is still missing: " + ", ".join(failures)\n    else:\n        message = "All channel permissions are OK. Pair resumed."',
        "show accurate recheck result for undersized pairs",
    )

    # Mini App: active-channel rows with per-channel remove and single-channel add.
    old = "const channels=p.channels.map(ch=>`<div class=\"channel\"><b>${ch.order_no}. ${esc(ch.title)}</b> <span class=\"muted\">(${esc(ch.chat_id)})</span><br><span class=\"${ch.bot_admin_ok?'pill ok':'pill bad'}\">${ch.bot_admin_ok?'Bot can post':'Permission check needed'}</span></div>`).join('');const order=p.channels.map(ch=>ch.chat_id).join(',');"
    new = "const activeChannels=p.channels.filter(ch=>ch.is_active);const channels=activeChannels.map(ch=>`<div class=\"channel\"><div class=\"rowhead\"><b>${ch.order_no}. ${esc(ch.title)}</b><button type=\"button\" class=\"danger\" data-action=\"remove-channel\" data-no=\"${p.pair_no}\" data-channel=\"${ch.chat_id}\">${tr('Remove','ဖယ်ရှား')}</button></div><span class=\"muted\">(${esc(ch.chat_id)})</span><br><span class=\"${ch.bot_admin_ok?'pill ok':'pill bad'}\">${ch.bot_admin_ok?'Bot can post':'Permission check needed'}</span></div>`).join('');const order=activeChannels.map(ch=>ch.chat_id).join(',');"
    patch("app/web/index.html", old, new, "render active channels with individual remove buttons")
    patch(
        "app/web/index.html",
        "${p.channels.length} channels · ${p.repost_style==='random'?'Always Random':'By Order'} · Movie Rule ${p.movie_rule?'ON':'OFF'}",
        "${activeChannels.length} active channels · ${p.repost_style==='random'?'Always Random':'By Order'} · Movie Rule ${p.movie_rule?'ON':'OFF'}",
        "show active channel count",
    )
    patch(
        "app/web/index.html",
        "${p.is_paused?`<div class=\"notice error\">${esc(p.paused_reason||'This pair is paused. Check channel permissions.')}</div>`:''}",
        "${p.is_paused?`<div class=\"notice error\">${esc(p.paused_reason==='insufficient_channels'?tr('At least two active channels are required. Add another channel to resume.','Active Channel အနည်းဆုံး ၂ ခု လိုအပ်သည်။ Channel ထပ်ထည့်ပါ။'):(p.paused_reason||'This pair is paused. Check channel permissions.'))}</div>`:''}",
        "explain minimum-channel pause in Mini App",
    )
    patch(
        "app/web/index.html",
        "${channels}<details><summary>Edit route and Movie Rule</summary>",
        "${channels}<form class=\"channel-add-form\" data-pair=\"${p.pair_no}\"><label>${tr('Add one channel to this pair','ဒီ Pair ထဲ Channel တစ်ခု ထည့်ရန်')}</label><input name=\"channel\" required maxlength=\"2048\" placeholder=\"@username or https://t.me/name\"><div class=\"hint\">${tr('Private channel: include invite link and numeric -100… ID. Bot must have Post Messages permission.','Private Channel အတွက် Invite Link နှင့် -100… ID နှစ်ခုလုံး ထည့်ပါ။ Bot ကို Post Messages permission ပေးထားပါ။')}</div><button type=\"submit\">${tr('Add channel','Channel ထည့်မယ်')}</button></form><details><summary>Edit route and Movie Rule</summary>",
        "add single-channel form to each Pair card",
    )
    patch(
        "app/web/index.html",
        "switch(a.dataset.action){case'delete-pair':",
        "switch(a.dataset.action){case'remove-channel':{if(!confirm(tr('Remove this channel from Pair '+no+'?','ဒီ Channel ကို Pair '+no+' ထဲမှ ဖယ်ရှားမလား?')))return;await api(`/api/pairs/${no}/channels/${encodeURIComponent(a.dataset.channel)}`,{method:'DELETE'});notice(tr('Channel removed.','Channel ကို ဖယ်ရှားပြီးပါပြီ။'),'success');await refresh();break}case'delete-pair':",
        "handle per-channel remove action",
    )
    patch(
        "app/web/index.html",
        "if(f.id==='add-form'){",
        "if(f.classList.contains('channel-add-form')){const d=new FormData(f);await api(`/api/pairs/${f.dataset.pair}/channels`,{method:'POST',body:JSON.stringify({channel:d.get('channel')})});notice(tr('Channel added.','Channel ထည့်ပြီးပါပြီ။'),'success');await refresh()}else if(f.id==='add-form'){",
        "handle per-channel add form",
    )

    print("\nChannel management patch applied. Next: python -m compileall -q app tests")


if __name__ == "__main__":
    main()

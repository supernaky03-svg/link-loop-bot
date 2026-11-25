# Pair တစ်ခုချင်း Channel Add / Remove Update

ဒီ ZIP က **full repository ZIP မဟုတ်ပါ**။ GitHub ရဲ့ လက်ရှိ `main` branch ပေါ်မှာ ထပ်တင်ရန် လိုအပ်တဲ့ feature overlay ဖြစ်ပါတယ်။ ZIP ကို အဲဒီ branch ကို clone လုပ်ထားတဲ့ repository root ထဲ extract လုပ်ပြီး `python apply_channel_management_patch.py` ကို run ပါ။

## Source compatibility

- Repository: `https://github.com/supernaky03-svg/link-loop-bot`
- Target branch: `main`
- Base commit checked: `6b0dacee9e5817c85cd152a7e5811c489d4bd491`
- Overlay patch က expected source anchors မတွေ့ရင် မတိတ်တဆိတ် patch မလုပ်ဘဲ ရပ်ပါမယ်။

## ပါဝင်တဲ့ Feature

### Telegram Bot

1. Main Menu ထဲက `Manage Pair Channels` / `Pair Channel စီမံမယ်` ကိုနှိပ်ပါ။
2. ပြင်ချင်တဲ့ Pair ကိုရွေးပါ။
3. `Add channel` သို့မဟုတ် `Remove channel` ရွေးပါ။
4. Add လုပ်ရင် channel တစ်ခုချင်းစီ ထည့်ပါ။ Public channel ကို `@username` သို့မဟုတ် `https://t.me/name` နဲ့၊ private channel ကို invite link + `-100...` ID နဲ့ ပို့ပါ။
5. Remove လုပ်ရင် channel ကိုရွေးပြီး confirmation ပေးပါ။

### Telegram Mini App

- Pair card တစ်ခုစီမှာ `Add one channel to this pair` form ပါမယ်။
- Active channel တစ်ခုချင်းစီမှာ `Remove` button ပါမယ်။
- Remove မလုပ်ခင် confirmation တောင်းမယ်။
- Bot နဲ့ Mini App နှစ်ခုစလုံးက တူညီတဲ့ backend service ကို သုံးတယ်။

## လုပ်ဆောင်ပုံ / Safety rules

- User ပိုင်တဲ့ Pair ကိုသာ ပြင်ခွင့်ရှိတယ်။ Backend API က Telegram Mini App `initData` authentication ကို လက်ရှိ middleware အတိုင်း ဆက်သုံးပြီး Pair ownership ကို user ID နဲ့စစ်တယ်။ Bot handler မှာလည်း `db_user.id` အလိုက် Pair ကို ရှာတယ်။
- Add လုပ်ရာမှာ Bot က channel admin ဖြစ်ပြီး `Post Messages` permission ရှိကြောင်း Bot API နဲ့စစ်ဆေးတယ်။
- Request တစ်ခုမှာ channel တစ်ခုတည်းသာ add လုပ်နိုင်တယ်။ Duplicate active channel ကို ပယ်ချတယ်။ User ရဲ့ `channel_per_pair_limit` ကိုလည်း စစ်တယ်။
- အရင်က soft-remove လုပ်ထားတဲ့ channel ကို ပြန်ထည့်ရင် DB row အသစ်မဖန်တီးဘဲ ရှိပြီးသား row ကို reactivate လုပ်တယ်။
- Remove လုပ်ရာမှာ `PairChannel` row ကို hard-delete မလုပ်ဘဲ `is_active=False` ထားတယ်။ Repost/history reference မပျောက်စေဖို့ပါ။
- Active channel ၂ ခုအောက်ကျသွားရင် Pair ကို `insufficient_channels` အကြောင်းပြချက်နဲ့ auto-pause လုပ်တယ်။ Bot ကို repost route အတွက် အနည်းဆုံး source/destination channel ၂ ခုလိုအပ်တယ်။
- Active channel ၂ ခု ပြန်ပြည့်ပြီး active channel အားလုံးရဲ့ `bot_admin_ok=True` ဖြစ်မှ `insufficient_channels` သို့မဟုတ် အဲဒီ channel ဖယ်ရှားမှုကြောင့် ကျန်ခဲ့တဲ့ `bot_admin_missing` pause ကိုသာ auto-resume လုပ်တယ်။ အခြား pause reason ကို မထိဘူး။
- Permission ပြန်ရလာတဲ့ event ကလည်း active channel ၂ ခုအောက်ရှိတဲ့ Pair ကို ပြန်မဖွင့်အောင် `Repository.mark_channel_admin_restored()` ကို update လုပ်တယ်။
- By Order route မှာ active channel တွေကိုပဲ အစဉ်ပြန်စီတယ်။

## Apply & Test

```bash
python apply_channel_management_patch.py
python -m compileall -q app tests
python -m pytest -q tests/test_pair_channel_management.py
python -m pytest -q
git diff --check
```

`tests/test_pair_channel_management.py` မှာ service behavior အတွက် unit tests ပါတယ်။ Full integration test အတွက် aiogram, PostgreSQL နဲ့ Telegram Bot token လိုအပ်ပါတယ်။

## API endpoints အသစ်

- `POST /api/pairs/{pair_no}/channels` — JSON body: `{"channel":"@username"}`
- `DELETE /api/pairs/{pair_no}/channels/{chat_id}` — ဥပမာ `/api/pairs/1/channels/-1001234567890`

Endpoint နှစ်ခုလုံးက လက်ရှိ Telegram auth middleware အောက်မှာ run ပါတယ်။

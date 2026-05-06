from app.bot.services.channel_service import parse_channel_list
from app.bot.services.link_service import normalize_channel_input, post_link, strip_visible_links


def test_normalize_public_link():
    assert normalize_channel_input('https://t.me/example_channel') == '@example_channel'


def test_normalize_private_c_link():
    assert normalize_channel_input('https://t.me/c/1234567890/5') == '-1001234567890'


def test_post_links():
    assert post_link(-1001234567890, 9, 'abc') == 'https://t.me/abc/9'
    assert post_link(-1001234567890, 9, None) == 'https://t.me/c/1234567890/9'


def test_order_parse():
    parsed = parse_channel_list('1-https://t.me/channel_a, 2--1001234567890(https://t.me/+x), 3-@channel_c', True)
    assert parsed[0].order_no == 1
    assert parsed[0].username == 'channel_a'
    assert parsed[1].order_no == 2
    assert parsed[1].chat_id == -1001234567890
    assert parsed[1].invite_link == 'https://t.me/+x'
    assert parsed[2].order_no == 3
    assert parsed[2].username == 'channel_c'


def test_private_mapping_formats():
    samples = [
        'https://t.me/+invite1(-1001234567890)',
        '-1001234567890(https://t.me/+invite1)',
        'https://t.me/+invite1 = -1001234567890',
        '-1001234567890 = https://t.me/+invite1',
    ]
    for raw in samples:
        parsed = parse_channel_list(raw, False)[0]
        assert parsed.chat_id == -1001234567890
        assert parsed.invite_link == 'https://t.me/+invite1'
        assert parsed.missing is None
        assert parsed.error is None


def test_private_missing_formats():
    invite_only = parse_channel_list('https://t.me/+invite1', False)[0]
    assert invite_only.missing == 'chat_id'
    id_only = parse_channel_list('-1001234567890', False)[0]
    assert id_only.missing == 'invite_link'


def test_strip_visible_links():
    assert strip_visible_links('hello https://example.com/test world') == 'hello world'

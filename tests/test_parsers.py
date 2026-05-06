from app.bot.services.channel_service import parse_channel_list
from app.bot.services.link_service import normalize_channel_input, post_link


def test_normalize_public_link():
    assert normalize_channel_input('https://t.me/example_channel') == '@example_channel'


def test_normalize_private_c_link():
    assert normalize_channel_input('https://t.me/c/1234567890/5') == '-1001234567890'


def test_post_links():
    assert post_link(-1001234567890, 9, 'abc') == 'https://t.me/abc/9'
    assert post_link(-1001234567890, 9, None) == 'https://t.me/c/1234567890/9'


def test_order_parse():
    parsed = parse_channel_list('1-https://t.me/a, 2--100123, 3-@c', True)
    assert parsed == [(1, 'https://t.me/a'), (2, '-100123'), (3, '@c')]

"""Redeem BD2 coupon codes through the official web form's API.

The official page (https://redeem.bd2.pmang.cloud/bd2/) posts
``{appId, userId, code}`` to the endpoint below; ``userId`` is the in-game
nickname on the profile card.  Rewards arrive in the in-game mailbox, so run
MailRewardTask afterwards.

    python tools/redeem_coupons.py BBZBBZ 2026BD2OCT BD2RADIODEMON
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

API_ENDPOINT = "https://loj2urwaua.execute-api.ap-northeast-1.amazonaws.com/prod/coupon"
APP_ID = "bd2-live"
# Without the page's Origin and a browser User-Agent every request answers a
# bare BadRequest (checked 2026-10-23).
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://redeem.bd2.pmang.cloud",
    "Referer": "https://redeem.bd2.pmang.cloud/",
    "User-Agent": "Mozilla/5.0",
}

# The page's own messages for each error name.
ERROR_MESSAGES = {
    "ValidationFailed": "兑换码无效",
    "InvalidCode": "兑换码无效",
    "ExpiredCode": "兑换码已过期",
    "AlreadyUsed": "已经兑换过",
    "ExceededUses": "兑换次数已用完",
    "UnavailableCode": "兑换码当前不可用",
    "IncorrectUser": "昵称不存在",
}


def redeem(user_id: str, code: str, timeout: float = 20.0) -> tuple[bool, str]:
    body = json.dumps({"appId": APP_ID, "userId": user_id, "code": code}).encode()
    request = urllib.request.Request(API_ENDPOINT, data=body, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode() or "{}")
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return False, f"请求失败：{error}"
    if result.get("success"):
        return True, "兑换成功，奖励在邮箱"
    name = str(result.get("error") or "")
    return False, ERROR_MESSAGES.get(name, name or json.dumps(result, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("nickname", help="游戏内昵称（个人资料卡上的名字）")
    parser.add_argument("codes", nargs="+", help="兑换码，可以一次给多个")
    args = parser.parse_args(argv)
    redeemed = 0
    for code in dict.fromkeys(c.strip() for c in args.codes if c.strip()):
        ok, message = redeem(args.nickname.strip(), code)
        redeemed += ok
        print(f"{code}: {message}")
    print(f"成功 {redeemed} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import pytest
from bot.services.subscription_service import SubscriptionService

class S: admin_ids=frozenset({1})
class D:
    def channels(self,enabled_only=False): return [{'channel_id':-100,'title':'قناة','username':'chan','invite_link':'https://t.me/chan'}]
class Member:
    def __init__(self,status): self.status=status
class B:
    async def get_chat_member(self,cid,uid): return Member('member' if uid==2 else 'left')

@pytest.mark.asyncio
async def test_admin_bypass_and_member():
    s=SubscriptionService(D(),S()); b=B()
    assert await s.missing(b,1)==[]
    assert await s.missing(b,2)==[]
    assert len(await s.missing(b,3))==1

from telegram.error import TelegramError

class SubscriptionService:
    def __init__(self, db, settings): self.db=db; self.s=settings
    def is_admin(self,user_id): return user_id in self.s.admin_ids
    async def missing(self, bot, user_id):
        if self.is_admin(user_id): return []
        missing=[]
        for c in self.db.channels(enabled_only=True):
            try:
                member=await bot.get_chat_member(c['channel_id'],user_id)
                if member.status not in ('member','administrator','creator'): missing.append(c)
            except TelegramError:
                missing.append(c)
        return missing

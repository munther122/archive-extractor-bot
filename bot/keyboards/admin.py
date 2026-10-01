from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def admin_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton('👥 المستخدمون',callback_data='adm:users'),InlineKeyboardButton('📊 الإحصائيات',callback_data='adm:stats')],[InlineKeyboardButton('📢 القنوات المطلوبة',callback_data='adm:channels'),InlineKeyboardButton('🧹 تنظيف النظام',callback_data='adm:clean')],[InlineKeyboardButton('📢 إذاعة Broadcast',callback_data='adm:broadcast'),InlineKeyboardButton('⚙️ الإعدادات',callback_data='adm:settings')],[InlineKeyboardButton('🏠 الرئيسية',callback_data='home')]])

def channel_menu(rows):
    buttons=[[InlineKeyboardButton('➕ إضافة قناة',callback_data='channel:add')]]
    for r in rows:
        state='🟢' if r['enabled'] else '⏸️'; buttons.append([InlineKeyboardButton(f"{state} {r['title'] or r['username'] or r['channel_id']}",callback_data=f'channel:view:{r["id"]}')])
    buttons.append([InlineKeyboardButton('⬅️ رجوع',callback_data='admin')]); return InlineKeyboardMarkup(buttons)

def channel_actions(cid,enabled): return InlineKeyboardMarkup([[InlineKeyboardButton('⏸️ تعطيل' if enabled else '▶️ تفعيل',callback_data=f'channel:toggle:{cid}'),InlineKeyboardButton('🗑️ حذف',callback_data=f'channel:delete:{cid}')],[InlineKeyboardButton('⬅️ رجوع',callback_data='adm:channels')]])

def user_list(rows):
    buttons=[]
    for r in rows:
        label=('🚫 ' if r['is_banned'] else '👤 ')+str(r['user_id'])+' '+(r['first_name'] or '')
        buttons.append([InlineKeyboardButton(label[:60],callback_data=f'adm:user:{r["user_id"]}')])
    buttons.append([InlineKeyboardButton('⬅️ رجوع',callback_data='admin')])
    return InlineKeyboardMarkup(buttons)

def user_actions(uid,banned):
    return InlineKeyboardMarkup([[InlineKeyboardButton('✅ إلغاء الحظر' if banned else '🚫 حظر',callback_data=f'adm:ban:{uid}:{0 if banned else 1}')],[InlineKeyboardButton('⬅️ رجوع',callback_data='adm:users')]])

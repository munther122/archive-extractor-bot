from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu(is_admin=False):
    rows=[[InlineKeyboardButton('📦 إدارة الملفات',callback_data='files'),InlineKeyboardButton('❓ شرح البوت',callback_data='help')],[InlineKeyboardButton('🧹 تنظيف الملفات',callback_data='cleanup'),InlineKeyboardButton('📋 ملفاتي',callback_data='myfiles')],[InlineKeyboardButton('🎬 تحويل الفيديو',callback_data='video'),InlineKeyboardButton('🎵 استخراج الصوت',callback_data='audio')]]
    if is_admin: rows.append([InlineKeyboardButton('⚙️ لوحة الإدارة',callback_data='admin')])
    return InlineKeyboardMarkup(rows)

def home(): return InlineKeyboardMarkup([[InlineKeyboardButton('🏠 الرئيسية',callback_data='home')]])
def back_home(): return InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ رجوع',callback_data='files'),InlineKeyboardButton('🏠 الرئيسية',callback_data='home')]])
def file_actions(aid): return InlineKeyboardMarkup([[InlineKeyboardButton('🔎 تصفح',callback_data=f'browse:{aid}'),InlineKeyboardButton('📥 استخراج الكل',callback_data=f'extractall:{aid}')],[InlineKeyboardButton('🔍 بحث',callback_data=f'search:{aid}'),InlineKeyboardButton('🗑️ حذف الأرشيف',callback_data=f'delarchive:{aid}')], [InlineKeyboardButton('🏠 الرئيسية',callback_data='home')]])
